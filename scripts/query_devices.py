#!/usr/bin/env python3
"""Query iQua devices for an account using the vendored client.

Examples:
  python3 scripts/query_devices.py --username user@example.com --password secret
  IQUA_USERNAME=user@example.com IQUA_PASSWORD=secret python3 scripts/query_devices.py --raw
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VENDOR_PATH = ROOT / "custom_components" / "iqua_softener" / "vendor"
if str(VENDOR_PATH) not in sys.path:
    sys.path.insert(0, str(VENDOR_PATH))

from iqua_softener import IquaSoftener  # noqa: E402


API_URLS = {
    "iqua": "https://api.myiquaapp.com/v1",
    "iqua2": "https://api.iqua2.com/v1",
}


def _property_value(device: dict[str, Any], *names: str) -> Any:
    properties = device.get("properties", {})
    for name in names:
        value = device.get(name)
        if value is None and isinstance(properties, dict):
            value = properties.get(name)
        if isinstance(value, dict):
            value = value.get("value") or value.get("converted_value")
        if value not in (None, ""):
            return value
    return None


def summarize_device(device: dict[str, Any], index: int) -> dict[str, Any]:
    """Extract the fields the config flow needs from one API device object."""
    return {
        "index": index,
        "id": device.get("id") or device.get("device_id"),
        "name": _property_value(device, "name", "nickname", "device_name", "label"),
        "model": _property_value(device, "model", "product_name", "product_model"),
        "device_serial_number": _property_value(
            device,
            "serial_number",
            "device_serial_number",
            "device_sn",
            "serialNumber",
        ),
        "product_serial_number": _property_value(
            device,
            "product_serial_number",
            "product_sn",
            "productSerialNumber",
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=os.environ.get("IQUA_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("IQUA_PASSWORD"))
    parser.add_argument(
        "--api-type",
        choices=sorted(API_URLS),
        default=os.environ.get("IQUA_API_TYPE", "iqua"),
    )
    parser.add_argument("--api-url", default=os.environ.get("IQUA_API_URL"))
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the full /devices API payload after the summary.",
    )
    args = parser.parse_args()

    if not args.username or not args.password:
        parser.error("Provide --username/--password or IQUA_USERNAME/IQUA_PASSWORD")

    api_url = args.api_url or API_URLS[args.api_type]
    client = IquaSoftener(
        username=args.username,
        password=args.password,
        api_base_url=api_url,
        enable_websocket=False,
    )

    devices = client.get_devices()
    summary = [summarize_device(device, index) for index, device in enumerate(devices)]

    print(json.dumps({"api_url": api_url, "device_count": len(devices), "devices": summary}, indent=2))

    if args.raw:
        print("\nRaw /devices data:")
        print(json.dumps(devices, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
