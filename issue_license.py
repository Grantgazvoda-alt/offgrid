#!/usr/bin/env python3
"""1-Click Customer License Fulfillment for OffGrid.

Usage:
    python issue_license.py <customer_email> <pro|studio> [days_valid=365]

Maintains a persistent master secret in .license_secret (gitignored),
logs every issued license to .issued_licenses.jsonl, and outputs a
ready-to-send fulfillment email with the customer's activation credentials.
"""
import datetime as dt
import json
import os
import secrets
import sys
from pathlib import Path

import license as lic

ROOT = Path(__file__).resolve().parent
SECRET_FILE = ROOT / ".license_secret"
LEDGER_FILE = ROOT / ".issued_licenses.jsonl"


def get_or_create_secret() -> str:
    env_sec = os.environ.get(lic.SECRET_ENV, "").strip()
    if env_sec:
        return env_sec
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()
    new_sec = secrets.token_hex(16)
    SECRET_FILE.write_text(new_sec + "\n", encoding="utf-8")
    return new_sec


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python issue_license.py <customer_email> <pro|studio> [days_valid=365]")
        return 1

    email = sys.argv[1].strip()
    tier = sys.argv[2].strip().lower()
    days = int(sys.argv[3]) if len(sys.argv) >= 4 else 365

    if tier not in ("pro", "studio"):
        print(f"Error: tier must be 'pro' or 'studio' (got '{tier}')")
        return 1

    secret = get_or_create_secret()
    os.environ[lic.SECRET_ENV] = secret

    expiry_date = (dt.date.today() + dt.timedelta(days=days)).isoformat()
    key = lic.gen(tier, expiry_date)
    tier_info = lic.TIERS[tier]

    record = {
        "issued_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "customer_email": email,
        "tier": tier,
        "expires": expiry_date,
        "license_key": key,
    }
    with open(LEDGER_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    print("=" * 72)
    print(f"OFFGRID {tier_info['label'].upper()} LICENSE ISSUED FOR: {email}")
    print("=" * 72)
    print("\n--- COPY & SEND THIS EMAIL TO CUSTOMER ---\n")
    print(f"To: {email}")
    print(f"Subject: Your OffGrid {tier_info['label']} License Key & Quickstart\n")
    print("Hi there,\n")
    print(f"Thank you for upgrading to OffGrid {tier_info['label']}! Your license is active through {expiry_date}.\n")
    print("1. Add these two lines to your `.env` file (or docker-compose environment):\n")
    print(f"OFFGRID_LICENSE_SECRET={secret}")
    print(f"OFFGRID_LICENSE_KEY={key}\n")
    print("2. Restart OffGrid:")
    print("   docker compose up -d\n")
    print("3. Verify your entitlement:")
    print("   curl http://localhost:8000/api/entitlement")
    print(f"   (You should see tier='{tier}', concurrent={tier_info['concurrent']}, priority_lane=true)\n")
    print("Need help wiring up your batch pipeline or custom providers? Reply directly to this email.\n")
    print("Best,")
    print("Grant Gazvoda")
    print("OffGrid — https://grantgazvoda-alt.github.io/offgrid-site/")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
