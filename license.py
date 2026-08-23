#!/usr/bin/env python3
"""OffGrid licensing — HMAC-signed tier licenses for self-hosted deployments.

Honest model: a license is a signed {tier, expiry} token validated locally.
It gates tier features (concurrency, queue depth, priority lane, backups).

This is NOT DRM: the validation secret ships with the deployment, so a
determined user could forge keys. That is the standard honest-user gate for
self-hosted software at this price point, and we document it as such —
the same "say the math honestly" trust the product is built on.

Vendor workflow:
    export OFFGRID_LICENSE_SECRET=<secret>     # same value in customer deploys
    python license.py gen pro 2027-12-31       # prints a key for that customer

Deployments without a key run the Community tier (3 concurrent, 500 queued).
"""
import datetime as _dt
import hashlib
import hmac
import os
import secrets
import sys

TIERS = {
    "community": {"label": "Community", "concurrent": 3, "queued_limit": 500,
                  "priority_lane": False, "backups": False},
    "pro": {"label": "Pro", "concurrent": 12, "queued_limit": None,
            "priority_lane": True, "backups": True},
    "studio": {"label": "Studio", "concurrent": 48, "queued_limit": None,
               "priority_lane": True, "backups": True},
}

DEFAULT_TIER = "community"
SECRET_ENV = "OFFGRID_LICENSE_SECRET"
KEY_ENV = "OFFGRID_LICENSE_KEY"


def _secret():
    return os.environ.get(SECRET_ENV, "")


def _sign(body):
    return hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()


def gen(tier, expiry_iso):
    if tier not in TIERS:
        raise ValueError("unknown tier: %s (known: %s)" % (tier, ", ".join(TIERS)))
    exp = int(_dt.datetime.fromisoformat(expiry_iso).timestamp())
    body = "%s.%d" % (tier, exp)
    return body + "." + _sign(body)


def validate(key):
    """Return {valid, tier, expires, reason}. Missing/invalid key -> community."""
    if not key:
        return {"valid": True, "tier": DEFAULT_TIER, "expires": None,
                "reason": "no key set; community tier"}
    if not _secret():
        return {"valid": False, "tier": DEFAULT_TIER, "expires": None,
                "reason": "OFFGRID_LICENSE_SECRET not configured on this deployment"}
    parts = key.split(".")
    if len(parts) != 3:
        return {"valid": False, "tier": DEFAULT_TIER, "expires": None,
                "reason": "malformed license key"}
    tier, exp_s, sig = parts
    body = "%s.%s" % (tier, exp_s)
    if not hmac.compare_digest(_sign(body), sig):
        return {"valid": False, "tier": DEFAULT_TIER, "expires": None,
                "reason": "bad signature"}
    try:
        exp = int(exp_s)
    except ValueError:
        return {"valid": False, "tier": DEFAULT_TIER, "expires": None,
                "reason": "malformed expiry"}
    if tier not in TIERS:
        return {"valid": False, "tier": DEFAULT_TIER, "expires": None,
                "reason": "unknown tier in key"}
    if exp < int(_dt.datetime.now().timestamp()):
        return {"valid": False, "tier": DEFAULT_TIER, "expires": exp,
                "reason": "license expired"}
    return {"valid": True, "tier": tier, "expires": exp, "reason": "ok"}


def effective():
    """Entitlement dict for the current deployment (always falls back safely)."""
    info = validate(os.environ.get(KEY_ENV, ""))
    tier = info.get("tier", DEFAULT_TIER)
    ent = dict(TIERS[tier])
    ent["tier"] = tier
    ent["expires"] = info.get("expires")
    ent["license_valid"] = info.get("valid", True)
    return ent


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "gen":
        secret = _secret()
        if not secret:
            secret = secrets.token_hex(16)
            print("generated a new OFFGRID_LICENSE_SECRET (set it in EVERY deployment):")
            print("  " + secret)
        print("license key:")
        print("  " + gen(sys.argv[2], sys.argv[3]))
        print("deploy with OFFGRID_LICENSE_KEY=<key> and OFFGRID_LICENSE_SECRET=<secret>")
    else:
        print("usage: python license.py gen <tier> <expiry ISO>   e.g. gen pro 2027-12-31")
        print("tiers: " + ", ".join(TIERS))