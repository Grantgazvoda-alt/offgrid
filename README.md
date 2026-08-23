# OffGrid — self-hosted batch AI media engine

Escape the hosted per-output pricing. **Bring your own keys, or your own backend
entirely** (`generic_http`), and OffGrid owns the queue, batching, retries and
resume — so a 430-shot film (or any heavy AI run) becomes one JSON batch that
executes on **your** infra without per-clip/credit surprises or one vendor's terms.

Mirrors the "leave a restrictive platform" playbook: it's the platform-independent
alternative to the thing annoying you most (per-output billing, credit caps, gates).

## What it is (and honestly isn't)
- A real, runnable self-hosted server: REST API + tiny web dashboard + SQLite queue.
- **It is not a model.** It orchestrates models/providers. That's the point — no
  model lock-in by construction.
- No placeholders: every button/endpoint above does what it says.

## Licensing (how it charges)
Self-hosted license = an HMAC-signed key per deployment. No key runs the **Community**
tier; the key gates tier features in code (not a banner — enforced).

| Tier | Concurrent | Queued | Priority lane | Backups |
|---|---|---|---|---|
| Community (free) | 3 | 500 | — | — |
| Pro · $39/mo | 12 | ∞ | ✓ | ✓ |
| Studio · $149/mo | 48 | ∞ | ✓ | ✓ |

```bash
OFFGRID_LICENSE_SECRET=<secret> python license.py gen pro 2027-12-31
# deploy with OFFGRID_LICENSE_KEY=<key> and the SAME OFFGRID_LICENSE_SECRET
```
Honesty rule: this is **not DRM**. The validating secret ships with the deployment, so a
determined user could forge keys. It is the standard honest-user gate at this price — same
"say the math honestly" trust the product runs on.

## Budget guardrails (the "no per-output surprises" feature)
Per-batch **USD cap**, enforced at enqueue time against per-job cost estimates, so a runaway
batch can't blow a client budget. Job cost is estimated by each provider (see below); override
any job via `payload["cost_estimate"]`. Jobs that would break the cap are rejected with the
math in the error message, so the cap is visible, not silent.

```
POST /api/batches/{name}/budget   { "budget_usd": 25.0 }     (0/absent clears)
GET  /api/batches/{name}/budget   { budget_usd, spent_est, remaining, capped }
POST /api/batch/import/{f}.json?budget=25.0                    (cap a whole import)
POST /api/admin/backup            Pro+ → snapshot offgrid.db to ./data/backups/
```

## Docs
- Landing: https://Grantgazvoda-alt.github.io/offgrid-site/  · ROI calculator: docs/roi.html · GTM: docs/offgrid_gtm.md

## Quick start (30 seconds)
```bash
cp .env.example .env        # set OFFGRID_API_TOKEN if this box is reachable
docker compose up -d
open http://localhost:8000
```
Or without Docker:
```bash
pip install -r requirements.txt
python app.py
```
Then submit a mock job to see the full queued→running→done lifecycle without
spending a cent: POST a job with `{"provider":"mock","payload":{"prompt":"hi"}}`
via the dashboard or curl.

## Providers
| name          | what it does                                              | needs |
|---------------|-----------------------------------------------------------|-------|
| `mock`        | deterministic local test (validates pipeline, costs $0)   | —     |
| `openai_images` | OpenAI images generation on **your** key               | `OPENAI_API_KEY` |
| `generic_http`  | POST a payload to any URL (your own backend / gateway)  | `OFFGRID_GENERIC_URL` (+ key) |

`generic_http` is the real "leave the platform" escape hatch: point it at your own
server and you are downstream of nothing you don't control.

## API
```
POST /api/jobs                     single job            {provider,payload,priority,max_attempts,batch}
POST /api/batch                    bulk submit           {jobs:[...]}
POST /api/batch/import/{file}.json import one of your batch files (array or {jobs:[...]}) · ?budget=USD
GET  /api/jobs[?status=&batch=]    list (incl. cost_est)
GET  /api/jobs/{id}                detail (incl. result)
POST /api/jobs/{id}/retry          retry a failed/cancelled job
POST /api/jobs/{id}/cancel         cancel queued job
DELETE /api/jobs/{id}              remove
GET  /api/health | /api/providers | /api/stats | /api/batches
GET  /api/entitlement              current tier + limits
POST /api/batches/{name}/budget · GET /api/batches/{name}/budget   budget caps
POST /api/admin/backup             Pro+ DB snapshot
```
Job cost estimates by default: `openai_images` sizes from a per-image table; `generic_http`
uses `OFFGRID_COST_PER_JOB` (default $0.30); always overridable per job via
`payload["cost_estimate"]`.
Auth: if `OFFGRID_API_TOKEN` is set, every `/api/*` call requires
`X-OffGrid-Token: <token>` or `Authorization: Bearer <token>`.

## Bring your 22-film batches in
Drop your staged batch JSONs into `./batches/`, then:
```bash
curl -X POST http://localhost:8000/api/batch/import/myfilm.json
```
Format: a JSON array of `{provider, payload, priority?, max_attempts?, meta?}`
or `{"jobs":[...]}`. Jobs drain one worker at a time, ordered by `priority`
(high first) then arrival. Queue + results persist in `./data/offgrid.db`, so a
restart resumes the queue (stuck `running` jobs are requeued at boot).

## Retry / backoff
Failures are retried up to `max_attempts` with exponential backoff (1s, 2s, …
cap 60s) then marked `failed` with the error surfaced. `retry` requeues it.

## Money model (why it's a product, not a toy)
Free single-user OSS core spreads it. Paid: **Pro** (deep/long queue, multi-node
workers, team + sharing), plus a **"we install it on your box"** support tier for
non-technical studios. Anchored at *less than a couple months of the per-output
charges the buyer is escaping* — easy value case.