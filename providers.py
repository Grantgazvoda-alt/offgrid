"""OffGrid provider adapters.

Each provider implements run(job_payload, job_meta, progress) -> dict result.
Providers are chosen per-job by name. Unknown providers are rejected at submit
time so the queue never silently swallows a bad provider string.

Design goal: this IS the 'escape the platform' layer. Bring your own keys, or
your own backend entirely (generic_http), and OffGrid owns the queue/batch/retry
so you are never hostage to one vendor's per-output billing or terms.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request


def _env(*names, default=None):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


def _json_post(url, payload, headers=None, timeout=180):
    """Sync JSON POST via stdlib urllib (no httpx dependency)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError("HTTP %s: %s" % (e.code, body[:500]))
    except urllib.error.URLError as e:
        raise RuntimeError("network error: %s" % e.reason)
    try:
        return json.loads(raw)
    except ValueError:
        return {"_raw": raw}


class Provider:
    name = "base"
    label = "base"
    needs_key = False

    def run(self, payload, meta, progress):
        raise NotImplementedError

    def estimate_cost(self, payload):
        """Best-effort USD estimate for one job (used for budget guardrails).
        Always overridable per-job via payload['cost_estimate']."""
        if "cost_estimate" in payload:
            return float(payload["cost_estimate"])
        return 0.0


# ------------------------------------------------------------------ mock


class MockProvider(Provider):
    """Deterministic local provider used to validate the pipeline without
    spending money or needing keys. Clearly not a real output backend."""

    name = "mock"
    label = "Mock (local test)"

    def run(self, payload, meta, progress):
        steps = payload.get("steps", 3)
        for i in range(1, steps + 1):
            time.sleep(0.2)
            progress(int(i / steps * 100), "step %d/%d" % (i, steps))
        return {
            "provider": "mock",
            "message": "mock ok",
            "echo": payload.get("prompt") or payload.get("text") or payload,
            "finished_at": time.time(),
        }


# ------------------------------------------------------------------ openai


class OpenAIProvider(Provider):
    """OpenAI images API on your own key. Escape the hosted credits: you pay
    OpenAI directly, OffGrid owns queue/batch/retry. Set OPENAI_API_KEY."""

    name = "openai_images"
    label = "OpenAI · images"
    needs_key = True

    def run(self, payload, meta, progress):
        import json

        key = payload.get("api_key") or _env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set and no payload.api_key")
        progress(5, "submitting")
        body = {
            "model": payload.get("model") or _env("OFFGRID_OPENAI_MODEL", default="gpt-image-1"),
            "prompt": payload["prompt"],
            "n": payload.get("n", 1),
            "size": payload.get("size", "1024x1024"),
        }
        if "quality" in payload:
            body["quality"] = payload["quality"]
        if "style" in payload:
            body["style"] = payload["style"]
        url = _env("OPENAI_IMAGES_URL", default="https://api.openai.com/v1/images/generations")
        resp = _json_post(url, body, headers={"Authorization": "Bearer " + key})
        progress(80, "generated")
        out = {"provider": "openai_images", "model": body["model"]}
        if "data" in resp:
            items = resp["data"]
            if items and "b64_json" in items[0]:
                out["b64"] = items[0]["b64_json"]
                out["format"] = "b64"
            elif items and "url" in items[0]:
                out["url"] = items[0]["url"]
                out["format"] = "url"
        out["raw_keys"] = sorted(resp.keys())
        return out

    def estimate_cost(self, payload):
        # gpt-image-style per-image pricing by size (approx, overridable).
        # payload['quantity'] mirrors the openai `n` param when present.
        if "cost_estimate" in payload:
            return float(payload["cost_estimate"])
        n = int(payload.get("quantity", payload.get("n", 1)))
        size = payload.get("size", "1024x1024")
        table = {"512x512": 0.03, "1024x1024": 0.06,
                 "1024x1536": 0.10, "1536x1024": 0.10}
        return table.get(size, 0.08) * max(1, n)


# ------------------------------------------------------------------ generic


class GenericHTTPProvider(Provider):
    """BYO-backend escape hatch: POST a payload to any URL (your own server, an
    org gateway, a self-hosted model endpoint). Payload may set url / api_key;
    otherwise env OFFGRID_GENERIC_URL / OFFGRID_GENERIC_API_KEY are used.
    Everything the job's `payload.body` (or the remaining payload) is sent as
    the JSON body; the full response is captured verbatim."""

    name = "generic_http"
    label = "Generic HTTP (BYO backend)"
    needs_key = False

    def run(self, payload, meta, progress):
        url = payload.get("url") or _env("OFFGRID_GENERIC_URL")
        if not url:
            raise RuntimeError(
                "generic_http needs payload.url or OFFGRID_GENERIC_URL "
                "(point it at your own backend to leave hosted platforms)")
        key = payload.get("api_key") or _env("OFFGRID_GENERIC_API_KEY")
        headers = {}
        if key:
            headers["Authorization"] = "Bearer " + key
        body = payload.get("body") if isinstance(payload.get("body"), dict) else {
            k: v for k, v in payload.items() if k not in ("url", "api_key", "body")
        }
        progress(5, "posting")
        resp = _json_post(url, body, headers=headers, timeout=payload.get("timeout", 300))
        progress(90, "response")
        return {"provider": "generic_http", "status": "ok", "response": resp}

    def estimate_cost(self, payload):
        # BYO-backend: we can't know the real price, so it's payload- or
        # env-configured (OFFGRID_COST_PER_JOB, default $0.30 — the GTM figure).
        if "cost_estimate" in payload:
            return float(payload["cost_estimate"])
        return float(os.environ.get("OFFGRID_COST_PER_JOB", "0.30"))


# ------------------------------------------------------------- registry


REGISTRY = {p.name: p for p in (MockProvider(), OpenAIProvider(), GenericHTTPProvider())}


def known_providers():
    return [
        {"name": p.name, "label": p.label, "needs_key": p.needs_key}
        for p in REGISTRY.values()
    ]