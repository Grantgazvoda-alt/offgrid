#!/usr/bin/env python3
"""OffGrid — self-hosted batch AI media engine.

Escape the hosted per-output pricing: bring your own keys / your own backend,
and OffGrid owns the queue, batching, retries and resume. One REST API, a tiny
web dashboard, docker-compose up. No placeholders.

Licensing: an HMAC-signed key (license.py) gates tier features — concurrency,
queue depth, priority lane, backups. No key = Community tier (3 concurrent,
500 queued). See license.py gen.

Budget guardrails: per-batch USD budget, enforced at enqueue time against
per-job cost estimates, so "no per-output surprises" is a hard feature, not a
slogan.

Stack: FastAPI + stdlib sqlite3. Workers are a pool of background threads.
"""
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

import license as lic
import providers

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("OFFGRID_DATA", BASE_DIR / "data"))
BATCH_DIR = Path(os.environ.get("OFFGRID_BATCH_DIR", BASE_DIR / "batches"))
DB_PATH = DATA_DIR / "offgrid.db"
BACKUP_DIR = DATA_DIR / "backups"
TOKEN = os.environ.get("OFFGRID_API_TOKEN")  # unset -> no auth (self-hosted)

DATA_DIR.mkdir(parents=True, exist_ok=True)
BATCH_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

LOCK = threading.Lock()
STOP = threading.Event()
_workers = []


class QueueLimitExceeded(Exception):
    pass


class BudgetExceeded(Exception):
    pass


class PriorityLaneRequired(Exception):
    pass


# ------------------------------------------------------------------ db


def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  batch TEXT,
  provider TEXT NOT NULL,
  payload TEXT NOT NULL,
  meta TEXT,
  priority INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  status TEXT NOT NULL DEFAULT 'queued',
  progress INTEGER NOT NULL DEFAULT 0,
  progress_note TEXT,
  result TEXT,
  error TEXT,
  cost_est REAL NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  started REAL,
  finished REAL
);
CREATE INDEX IF NOT EXISTS idx_status ON jobs(status);
CREATE TABLE IF NOT EXISTS batches (
  name TEXT PRIMARY KEY,
  budget_usd REAL
);
"""


def init_db():
    with LOCK:
        with db() as c:
            c.executescript(SCHEMA)
            # migration: cost_est on an existing jobs table (adds column if absent)
            cols = [r["name"] for r in c.execute("PRAGMA table_info(jobs)").fetchall()]
            if "cost_est" not in cols:
                c.execute("ALTER TABLE jobs ADD COLUMN cost_est REAL NOT NULL DEFAULT 0")
            # crash recovery: jobs stuck 'running' from a dead run -> queued
            c.execute("UPDATE jobs SET status='queued' WHERE status='running'")
            c.commit()


# ------------------------------------------------------------------ budget


def get_budget(name):
    with db() as c:
        r = c.execute("SELECT budget_usd FROM batches WHERE name=?", (name,)).fetchone()
    return r["budget_usd"] if r else None


def set_budget(name, budget_usd):
    with db() as c:
        if budget_usd is None or budget_usd <= 0:
            c.execute("DELETE FROM batches WHERE name=?", (name,))
        else:
            c.execute(
                "INSERT INTO batches(name,budget_usd) VALUES(?,?) ON CONFLICT(name) "
                "DO UPDATE SET budget_usd=excluded.budget_usd",
                (name, budget_usd))
        c.commit()


def batch_spend(name):
    with db() as c:
        r = c.execute(
            "SELECT COALESCE(SUM(cost_est),0) s FROM jobs WHERE batch=? "
            "AND status IN ('done','running','queued')", (name,)).fetchone()
    return r["s"]


def batch_budget_state(name):
    budget = get_budget(name)
    spent = batch_spend(name) if budget else None
    return {"batch": name, "budget_usd": budget,
            "spent_est": spent,
            "remaining": round(budget - spent, 4) if budget is not None else None,
            "capped": budget is not None and spent >= budget - 1e-6}


# ------------------------------------------------------------------ queue


def enqueue(provider_name, payload, meta=None, priority=0, max_attempts=3,
            batch="default"):
    if provider_name not in providers.REGISTRY:
        raise ValueError("unknown provider '%s'; known: %s" % (
            provider_name, ", ".join(providers.REGISTRY)))
    ent = lic.effective()
    if not ent["priority_lane"] and priority:
        raise PriorityLaneRequired(
            "priority lane is a Pro/Studio feature (Community runs FIFO)")
    if ent["queued_limit"] is not None:
        with db() as c:
            n = c.execute("SELECT COUNT(*) n FROM jobs WHERE status='queued'").fetchone()["n"]
        if n >= ent["queued_limit"]:
            raise QueueLimitExceeded(
                "queue full (%d/%d queued) — Community caps queued jobs; "
                "Upgrade for an unlimited queue" % (n, ent["queued_limit"]))
    cost = providers.REGISTRY[provider_name].estimate_cost(payload)
    budget = get_budget(batch)
    if budget is not None:
        spent = batch_spend(batch)
        if spent + cost > budget + 1e-6:
            raise BudgetExceeded(
                "batch '%s' is capped at $%.2f; $%.2f already committed, this job "
                "~$%.2f would break the cap" % (batch, budget, spent, cost))
    jid = uuid.uuid4().hex[:12]
    with LOCK:
        with db() as c:
            c.execute(
                "INSERT INTO jobs (id,batch,provider,payload,meta,priority,max_attempts,"
                "status,cost_est,created) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (jid, batch, provider_name, json.dumps(payload), json.dumps(meta or {}),
                 priority, max_attempts, "queued", cost, time.time()))
            c.commit()
    return jid


def import_batch_file(filename, priority=0, max_attempts=3, budget=None):
    """Import one of your batch JSON files. File is a JSON array of job objects,
    or {"jobs": [...]}. Optionally caps the whole batch at `budget` (USD)."""
    path = BATCH_DIR / filename
    if not path.exists():
        raise FileNotFoundError("no batch file %s in %s" % (filename, BATCH_DIR))
    data = json.loads(path.read_text())
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    if budget is not None:
        set_budget(path.stem, budget)
    ids = []
    for j in jobs:
        ids.append(enqueue(
            j["provider"],
            j.get("payload", j.get("params", j)),
            meta=j.get("meta"),
            priority=j.get("priority", priority),
            max_attempts=j.get("max_attempts", max_attempts),
            batch=path.stem))
    return ids


def _row_to_dict(r):
    d = dict(r)
    for k in ("payload", "meta", "result"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except (ValueError, TypeError):
                pass
    return d


def set_progress(jid, pct, note):
    with db() as c:
        c.execute("UPDATE jobs SET progress=?, progress_note=? WHERE id=?",
                  (int(pct), note, jid))
        c.commit()


def _backoff(attempts_so_far):
    return min(2 ** attempts_so_far, 60)


def _process_one():
    """Claim one queued job, run its provider, update status. Returns True if a
    job was attempted (workers re-check immediately in that case)."""
    with LOCK:
        with db() as c:
            row = c.execute(
                "SELECT * FROM jobs WHERE status='queued' "
                "ORDER BY priority DESC, created ASC LIMIT 1").fetchone()
            if row is None:
                return False
            c.execute("UPDATE jobs SET status='running', started=? WHERE id=?",
                      (time.time(), row["id"]))
            c.commit()
    job = _row_to_dict(row)
    jid = job["id"]
    if job["provider"] not in providers.REGISTRY:
        with db() as c:
            c.execute(
                "UPDATE jobs SET status='failed', error=?, finished=? WHERE id=?",
                ("unknown provider '%s'" % job["provider"], time.time(), jid))
            c.commit()
        return True
    prov = providers.REGISTRY[job["provider"]]
    try:
        result = prov.run(job["payload"], job["meta"],
                          lambda p, n=None: set_progress(jid, p, n))
        with db() as c:
            c.execute(
                "UPDATE jobs SET status='done', progress=100, result=?,"
                "finished=?, error=NULL WHERE id=?",
                (json.dumps(result), time.time(), jid))
            c.commit()
    except Exception as e:
        error = str(e) or e.__class__.__name__
        attempts = job["attempts"] + 1
        with db() as c:
            if attempts >= job["max_attempts"]:
                c.execute(
                    "UPDATE jobs SET status='failed', attempts=?, error=?,"
                    "finished=? WHERE id=?",
                    (attempts, error, time.time(), jid))
            else:
                c.execute(
                    "UPDATE jobs SET status='queued', attempts=?, error=?,"
                    "started=NULL WHERE id=?",
                    (attempts, error, jid))
            c.commit()
        # let a flaky backend breathe before retrying
        time.sleep(_backoff(job["attempts"]))
    return True


def worker_loop():
    while not STOP.is_set():
        try:
            ran = _process_one()
        except Exception:
            traceback.print_exc()
            ran = True
        if not ran:
            STOP.wait(timeout=1.0)


def start_worker():
    """Spawn (up to) the tier's concurrency cap of worker threads."""
    n = lic.effective()["concurrent"]
    alive = [w for w in _workers if w and w.is_alive()]
    while len(alive) < n:
        t = threading.Thread(target=worker_loop, daemon=True,
                             name="offgrid-worker-%d" % len(alive))
        t.start()
        alive.append(t)
    _workers[:] = alive


# ------------------------------------------------------------------ app


@asynccontextmanager
async def lifespan(app_):
    init_db()
    start_worker()
    yield
    STOP.set()


app = FastAPI(title="OffGrid", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if TOKEN and request.url.path.startswith("/api/"):
        ok = (request.headers.get("x-offgrid-token") == TOKEN
              or request.headers.get("authorization") == "Bearer " + TOKEN)
        if not ok:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


class JobIn(BaseModel):
    provider: str
    payload: dict = Field(default_factory=dict)
    meta: dict | None = None
    priority: int = 0
    max_attempts: int = 3
    batch: str = "default"


class BatchIn(BaseModel):
    jobs: list[JobIn]


class BudgetIn(BaseModel):
    budget_usd: float


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE_DIR / "static" / "index.html").read_text()


@app.get("/api/health")
def health():
    return {"status": "ok", "product": "OffGrid", "version": app.version,
            "tier": lic.effective()["tier"]}


@app.get("/api/entitlement")
def entitlement():
    ent = lic.effective()
    return {"tier": ent["tier"], "label": ent["label"],
            "expires": ent.get("expires"),
            "license_valid": ent["license_valid"],
            "concurrent": ent["concurrent"],
            "queued_limit": ent["queued_limit"],
            "priority_lane": ent["priority_lane"],
            "backups": ent["backups"]}


@app.post("/api/admin/backup", status_code=201)
def admin_backup():
    ent = lic.effective()
    if not ent["backups"]:
        raise HTTPException(status_code=403,
                            detail="backups are a Pro/Studio feature")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / ("offgrid-%s.db" % stamp)
    with LOCK:
        with db() as c:
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.copy2(DB_PATH, dest)
    return {"backup": str(dest), "size": dest.stat().st_size}


@app.get("/api/providers")
def list_providers():
    return {"providers": providers.known_providers()}


@app.post("/api/jobs", status_code=201)
def create_job(j: JobIn):
    try:
        jid = enqueue(j.provider, j.payload, j.meta, j.priority, j.max_attempts, j.batch)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except (PriorityLaneRequired,) as e:
        raise HTTPException(status_code=403, detail=str(e))
    except (QueueLimitExceeded, BudgetExceeded) as e:
        raise HTTPException(status_code=429, detail=str(e))
    return {"id": jid, "batch": j.batch, "status": "queued"}


@app.post("/api/batch", status_code=201)
def create_batch(b: BatchIn):
    ids = []
    for j in b.jobs:
        try:
            jid = enqueue(j.provider, j.payload, j.meta, j.priority, j.max_attempts,
                          j.batch or "default")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except PriorityLaneRequired as e:
            raise HTTPException(status_code=403, detail=str(e))
        except (QueueLimitExceeded, BudgetExceeded) as e:
            raise HTTPException(status_code=429, detail=str(e))
        ids.append(jid)
    return {"count": len(ids), "ids": ids, "status": "queued"}


@app.post("/api/batch/import/{filename}")
def import_batch(filename: str, priority: int = 0, max_attempts: int = 3,
                 budget: float | None = None):
    if re.search(r"[/\\]", filename) or not filename.endswith(".json"):
        raise HTTPException(status_code=422, detail="filename must be a plain *.json")
    try:
        ids = import_batch_file(filename, priority, max_attempts, budget)
    except (FileNotFoundError, ValueError, BudgetExceeded, QueueLimitExceeded,
            PriorityLaneRequired, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"count": len(ids), "ids": ids, "batch": filename[:-5]}


@app.post("/api/batches/{name}/budget")
def set_batch_budget(name: str, b: BudgetIn):
    set_budget(name, b.budget_usd)
    return batch_budget_state(name)


@app.get("/api/batches/{name}/budget")
def get_batch_budget(name: str):
    return batch_budget_state(name)


@app.get("/api/batches")
def list_batches():
    out = []
    with db() as c:
        names = [r["name"] for r in
                 c.execute("SELECT name FROM batches").fetchall()]
    for n in names:
        st = batch_budget_state(n)
        out.append({"name": n, "budget_usd": st["budget_usd"],
                    "spent_est": st["spent_est"], "remaining": st["remaining"]})
    files = sorted(p.stem for p in BATCH_DIR.glob("*.json"))
    return {"batches": files, "budgets": out, "dir": str(BATCH_DIR)}


@app.get("/api/jobs")
def list_jobs(status: str | None = None, batch: str | None = None, limit: int = 200):
    q = "SELECT * FROM jobs WHERE 1=1"
    args = []
    if status:
        q += " AND status=?"
        args.append(status)
    if batch:
        q += " AND batch=?"
        args.append(batch)
    q += " ORDER BY created DESC LIMIT ?"
    args.append(min(limit, 1000))
    with db() as c:
        rows = c.execute(q, args).fetchall()
    return {"jobs": [_row_to_dict(r) for r in rows]}


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    with db() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="no such job")
    return _row_to_dict(r)


@app.post("/api/jobs/{jid}/retry")
def retry_job(jid: str):
    with db() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="no such job")
        c.execute("UPDATE jobs SET status='queued', attempts=0, error=NULL,"
                  "started=NULL, finished=NULL WHERE id=?", (jid,))
        c.commit()
    return {"id": jid, "status": "queued"}


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    with LOCK:
        with db() as c:
            r = c.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="no such job")
            if r["status"] == "done":
                raise HTTPException(status_code=409, detail="job already done")
            c.execute("UPDATE jobs SET status='cancelled' WHERE id=?", (jid,))
            c.commit()
    return {"id": jid, "status": "cancelled"}


@app.delete("/api/jobs/{jid}")
def delete_job(jid: str):
    with db() as c:
        c.execute("DELETE FROM jobs WHERE id=?", (jid,))
    return {"deleted": jid}


@app.get("/api/stats")
def stats():
    ent = lic.effective()
    with db() as c:
        rows = c.execute(
            "SELECT status, COUNT(*) n FROM jobs GROUP BY status").fetchall()
        spend = c.execute(
            "SELECT COALESCE(SUM(cost_est),0) s FROM jobs WHERE status IN "
            "('done','running','queued')").fetchone()["s"]
    return {"by_status": {r["status"]: r["n"] for r in rows},
            "queue_total": sum(r["n"] for r in rows),
            "spend_est": round(spend, 4),
            "tier": ent["tier"],
            "concurrent": ent["concurrent"]}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")