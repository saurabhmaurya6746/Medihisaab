#!/usr/bin/env python3
"""Publisher tool: Generate and sign offline client licenses using Ed25519 asymmetric cryptography.

Usage:
    python scripts/generate-license.py --client "Apex Medicos" --id "LIC-1001" --terminals 5 --expiry "2027-10-01"
    python scripts/generate-license.py --batch 100 --out-dir dist-release/licenses
"""

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sys

# Ensure pharmacy_daemon is in python path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "daemon" / "src"))

from pharmacy_daemon.security.license import (
    EMBEDDED_PUBLIC_KEY_HEX,
    evaluate_license,
    load_private_key,
    sign_license,
)

DEFAULT_KEY_PATH = ROOT / "publisher_keys" / "license_private_key.pem"


def create_signed_license(
    client_name: str,
    license_id: str,
    private_key_path: Path,
    terminal_count: int = 3,
    activation_date: str = None,
    expiry_date: str = None,
    edition: str = "COMMERCIAL",
) -> dict:
    if not activation_date:
        activation_date = date.today().isoformat()

    payload = {
        "client_name": client_name.strip(),
        "license_id": license_id.strip(),
        "terminal_count": int(terminal_count),
        "activation_date": activation_date,
        "expiry_date": expiry_date,
        "edition": edition,
        "features": "ALL",
    }

    sig = sign_license(payload, private_key_path)
    payload["signature"] = sig
    return payload


def main():
    parser = argparse.ArgumentParser(description="Generate cryptographically signed offline licenses.")
    parser.add_argument("--key", default=str(DEFAULT_KEY_PATH), help="Path to publisher Ed25519 private key PEM")
    parser.add_argument("--client", default="Apex Health Pharmacy", help="Store or client name")
    parser.add_argument("--id", default="LIC-2026-0001", help="Unique license ID")
    parser.add_argument("--terminals", type=int, default=5, help="Allowed network terminal count")
    parser.add_argument("--activation", default=None, help="Activation date (YYYY-MM-DD)")
    parser.add_argument("--expiry", default=None, help="Optional expiry date (YYYY-MM-DD)")
    parser.add_argument("--out", default=None, help="Output JSON file path")
    parser.add_argument("--batch", type=int, default=0, help="Generate N batch licenses for distribution")
    parser.add_argument("--out-dir", default="dist-release/licenses", help="Output directory for batch")

    args = parser.parse_args()
    key_path = Path(args.key)

    if not key_path.exists():
        print(f"[ERROR] Publisher private key not found at: {key_path}")
        print("Please ensure the publisher private key is located in publisher_keys/license_private_key.pem")
        sys.exit(1)

    if args.batch > 0:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"Generating {args.batch} signed licenses into {out_dir} using publisher private key...")
        one_year_later = (date.today() + timedelta(days=365)).isoformat()
        manifest = []

        for i in range(1, args.batch + 1):
            client_id = f"LIC-CLIENT-{i:03d}"
            store_name = f"Pharmacy Client #{i:03d}"
            lic = create_signed_license(
                client_name=store_name,
                license_id=client_id,
                private_key_path=key_path,
                terminal_count=5,
                activation_date=date.today().isoformat(),
                expiry_date=one_year_later,
            )
            # Verify with public key
            status = evaluate_license(lic)
            assert status.is_valid, f"Signature failed for {client_id}: {status.message}"

            file_path = out_dir / f"{client_id}.json"
            file_path.write_text(json.dumps(lic, indent=2), encoding="utf-8")
            manifest.append({"client_id": client_id, "store": store_name, "file": file_path.name})

        index_file = out_dir / "index.json"
        index_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Successfully generated {args.batch} client licenses. Manifest saved to {index_file}")
        return

    lic = create_signed_license(
        client_name=args.client,
        license_id=args.id,
        private_key_path=key_path,
        terminal_count=args.terminals,
        activation_date=args.activation,
        expiry_date=args.expiry,
    )

    # Validate generated license using public key
    status = evaluate_license(lic)
    assert status.is_valid, f"Self-validation failed: {status.message}"

    formatted = json.dumps(lic, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(formatted, encoding="utf-8")
        print(f"License written to {out_path}")
    else:
        print(formatted)
    print(f"\nLicense Status: {status.status} (Valid: {status.is_valid}, Terminals: {status.terminal_count})")


if __name__ == "__main__":
    main()
