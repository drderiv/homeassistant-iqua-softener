#!/usr/bin/env python3
"""
Test script to check iQua WebSocket connectivity and API rate limiting.

`pip install aiohttp requests python-dotenv` to install dependencies.

Tests:
1. Rate limit headers from API responses (ratelimit-remaining, ratelimit-policy,
   ratelimit-limit) to verify the token-bucket policy is active.
2. WebSocket connectivity.
3. Extended WebSocket monitoring to observe whether the current water usage
   metric (current_water_flow_gpm) stops being published after ~3 minutes.
"""

import asyncio
import aiohttp
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add the vendored library to sys.path so `iqua_softener` can be imported
# without installing it.  The vendor directory lives at:
#   custom_components/iqua_softener/vendor/
_vendor_path = Path(__file__).parent / "custom_components" / "iqua_softener" / "vendor"
if str(_vendor_path) not in sys.path:
    sys.path.insert(0, str(_vendor_path))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    # python-dotenv not installed — fall back to manual parsing
    _env_file = Path(__file__).parent / ".env"
    if _env_file.exists():
        for _line in _env_file.read_text().splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from iqua_softener import IquaSoftener

# Default WebSocket base URL - can be overridden
DEFAULT_WEBSOCKET_BASE = "wss://api.myiquaapp.com"
WEBSOCKET_BASE_OVERRIDE = ""

# Property that is expected to stop publishing after ~3 minutes of inactivity
FLOW_PROPERTY = "current_water_flow_gpm"

# How long to monitor the WebSocket to observe the 3-minute publish window.
# 6 minutes gives a comfortable margin to see the cutoff.
WEBSOCKET_MONITOR_DURATION = 360  # seconds


def parse_rate_limit_policy(policy_header: str) -> dict:
    """Parse the ratelimit-policy header into a human-readable dict.

    Expected format: "6;w=600;burst=60;policy=token_bucket"
    Returns e.g. {'limit': 6, 'w': 600, 'burst': 60, 'policy': 'token_bucket'}
    """
    result = {}
    parts = policy_header.split(";")
    # First segment is the base limit (requests per window)
    try:
        result["limit"] = int(parts[0])
    except ValueError:
        result["limit"] = parts[0]
    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            try:
                result[key] = int(value)
            except ValueError:
                result[key] = value
    return result


def check_rate_limit_headers(softener: IquaSoftener) -> None:
    """Make a lightweight API call and display any rate-limit response headers.

    Uses the softener's internal authenticated session so no extra login is needed.
    """
    print("\n--- Rate Limit Header Check ---")

    # Use the public device_id accessor; fall back gracefully on error
    try:
        device_id = softener.get_device_id()
    except Exception as err:
        print(f"  Could not resolve device ID: {err}")
        return

    # Access the internal session that already carries the Bearer token
    session = softener._session  # noqa: SLF001 (diagnostic script, private access OK)
    if session is None:
        print("  No active session — authentication may have failed")
        return

    # Hit the devices list endpoint (light call, always available after login)
    url = f"{softener._api_base_url}/devices/{device_id}"  # noqa: SLF001
    try:
        response = session.get(url, timeout=10)
    except Exception as err:
        print(f"  Request failed: {err}")
        return

    print(f"  HTTP {response.status_code} {url}")

    expected_headers = ["ratelimit-remaining", "ratelimit-policy", "ratelimit-limit"]
    found_any = False

    for header in expected_headers:
        value = response.headers.get(header)
        if value is not None:
            found_any = True
            print(f"  {header}: {value}")
            if header == "ratelimit-policy":
                parsed = parse_rate_limit_policy(value)
                window = parsed.get("w", "?")
                burst = parsed.get("burst", "?")
                base_limit = parsed.get("limit", "?")
                policy_type = parsed.get("policy", "?")
                print(
                    f"    Parsed policy → base rate: {base_limit} req/{window}s  "
                    f"burst: {burst}  algorithm: {policy_type}"
                )
                if window != "?" and base_limit != "?":
                    refill_interval = int(window) / int(base_limit)
                    print(
                        f"    Token refill: 1 token every {refill_interval:.0f}s "
                        f"(~{int(base_limit) * 6:.0f} req/hour)"
                    )

    if not found_any:
        print(
            "  ⚠ No rate-limit headers present — "
            "policy may not yet be enforced on this endpoint"
        )

def _build_websocket_url(softener: IquaSoftener, ws_uri: str) -> str:
    """Resolve a WebSocket URI to a fully-qualified wss:// URL."""
    if WEBSOCKET_BASE_OVERRIDE:
        ws_base = WEBSOCKET_BASE_OVERRIDE.rstrip("/")
        if ws_uri.startswith("wss://") or ws_uri.startswith("ws://"):
            path = "/" + ws_uri.split("//", 1)[1].split("/", 1)[1]
            return f"{ws_base}{path}"
        if ws_uri.startswith("/"):
            return f"{ws_base}{ws_uri}"
        return f"{ws_base}/{ws_uri}"

    if ws_uri.startswith("wss://") or ws_uri.startswith("ws://"):
        return ws_uri

    # Derive host from API base URL
    api_base = getattr(softener, "_api_base_url", None) or "https://api.myiquaapp.com/v1"  # noqa: SLF001
    ws_base = api_base.replace("https://", "wss://").replace("http://", "ws://")
    # Strip path components (keep only scheme://host)
    ws_host = ws_base.split("/")[0] + "//" + ws_base.split("//")[1].split("/")[0]

    if ws_uri.startswith("/"):
        return f"{ws_host}{ws_uri}"

    # Unexpected format — fall back to configured default
    print(f"  Unexpected URI format, using default base: {DEFAULT_WEBSOCKET_BASE}")
    return f"{DEFAULT_WEBSOCKET_BASE}{ws_uri}"


async def test_websocket_connection(softener: IquaSoftener) -> bool:
    """Quick connectivity smoke-test: connect, receive up to 3 messages, disconnect."""
    print("\n--- WebSocket Connectivity Check ---")

    try:
        ws_uri = softener.get_websocket_uri()
    except AttributeError:
        print("✗ get_websocket_uri method not available in library")
        return False
    except Exception as err:
        print(f"✗ Failed to get WebSocket URI: {err}")
        return False

    if not ws_uri:
        print("✗ WebSocket URI is empty")
        return False

    full_uri = _build_websocket_url(softener, ws_uri)
    base_uri = full_uri.split("?")[0]
    print(f"  URI: {base_uri}?…")

    session = aiohttp.ClientSession()
    try:
        async with session.ws_connect(
            full_uri,
            timeout=aiohttp.ClientTimeout(total=10),
            heartbeat=30,
        ) as ws:
            print("✓ WebSocket connected")
            message_count = 0
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    msg = await asyncio.wait_for(
                        ws.receive(),
                        timeout=max(0.1, deadline - time.monotonic()),
                    )
                except asyncio.TimeoutError:
                    print("  (timeout — no further messages in 10 s)")
                    break

                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        payload = json.loads(msg.data)
                        message_count += 1
                        print(f"  Message {message_count}: {payload}")
                        if message_count >= 3:
                            break
                    except json.JSONDecodeError:
                        print(f"  Invalid JSON: {msg.data}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"  WebSocket error: {ws.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    print("  WebSocket closed by server")
                    break

        if message_count > 0:
            print(f"✓ Received {message_count} WebSocket messages")
        else:
            print("⚠ WebSocket connected but no messages received (device may be idle)")
        return True

    except aiohttp.ClientResponseError as err:
        if err.status == 400:
            print(f"✗ WebSocket 400 — authentication/token issue: {err}")
        else:
            print(f"✗ WebSocket HTTP error: {err}")
        return False
    except Exception as err:
        print(f"✗ WebSocket connection failed: {err}")
        return False
    finally:
        await session.close()


async def monitor_websocket_publish_window(softener: IquaSoftener) -> bool:
    """Monitor the WebSocket for WEBSOCKET_MONITOR_DURATION seconds.

    Tracks per-property message timing to observe whether the server stops
    publishing 'current_water_flow_gpm' after ~3 minutes (the expected behaviour).

    Reports:
    - All unique property names received
    - First/last seen timestamps per property
    - Whether the flow property went silent after ~180 seconds
    - Server-side close / connection drop timing
    """
    print(
        f"\n--- WebSocket Publish-Window Monitor ({WEBSOCKET_MONITOR_DURATION}s) ---"
    )
    print(
        f"  Monitoring for {WEBSOCKET_MONITOR_DURATION // 60}m {WEBSOCKET_MONITOR_DURATION % 60}s "
        f"to observe the ~3-minute '{FLOW_PROPERTY}' publish window."
    )
    print("  Press Ctrl+C to stop early.\n")

    try:
        ws_uri = softener.get_websocket_uri()
    except Exception as err:
        print(f"✗ Failed to get WebSocket URI: {err}")
        return False

    if not ws_uri:
        print("✗ WebSocket URI is empty")
        return False

    full_uri = _build_websocket_url(softener, ws_uri)

    # Tracking structures
    first_seen: dict[str, float] = {}   # property → epoch of first message
    last_seen: dict[str, float] = {}    # property → epoch of most recent message
    counts: dict[str, int] = defaultdict(int)

    connect_time = time.monotonic()
    server_closed_at: float | None = None
    total_messages = 0

    session = aiohttp.ClientSession()
    try:
        async with session.ws_connect(
            full_uri,
            timeout=aiohttp.ClientTimeout(connect=10),
            heartbeat=30,
        ) as ws:
            print(f"  ✓ Connected at {datetime.now().strftime('%H:%M:%S')}")
            remaining = WEBSOCKET_MONITOR_DURATION

            while remaining > 0:
                try:
                    timeout = min(remaining, 5)
                    msg = await asyncio.wait_for(ws.receive(), timeout=timeout)

                    elapsed = time.monotonic() - connect_time

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        total_messages += 1
                        try:
                            payload = json.loads(msg.data)
                        except json.JSONDecodeError:
                            print(
                                f"  [{elapsed:6.1f}s] Non-JSON message: {msg.data[:80]}"
                            )
                            remaining -= 0  # don't subtract — handled by timeout
                            continue

                        prop = payload.get("name") or payload.get("type", "<unknown>")
                        now = time.time()
                        if prop not in first_seen:
                            first_seen[prop] = now
                        last_seen[prop] = now
                        counts[prop] += 1

                        value = payload.get("value", payload.get("converted_value", ""))
                        print(
                            f"  [{elapsed:6.1f}s] {prop} = {value}"
                        )

                    elif msg.type == aiohttp.WSMsgType.CLOSE:
                        server_closed_at = time.monotonic() - connect_time
                        print(
                            f"  [{server_closed_at:6.1f}s] ⚠ Server closed the connection "
                            f"(code {ws.close_code})"
                        )
                        break

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"  WebSocket error: {ws.exception()}")
                        break

                except asyncio.TimeoutError:
                    elapsed = time.monotonic() - connect_time
                    remaining -= 5
                    # Periodic heartbeat so the user sees the script is alive
                    if int(elapsed) % 30 < 5:
                        print(
                            f"  [{elapsed:6.1f}s] … (waiting, {remaining:.0f}s left)"
                        )
                except KeyboardInterrupt:
                    print("\n  Stopped by user")
                    break

    except Exception as err:
        print(f"✗ Monitor failed: {err}")
        return False
    finally:
        await session.close()

    # ── Summary ──────────────────────────────────────────────────────────────
    total_duration = time.monotonic() - connect_time
    print(f"\n  --- Summary ({total_duration:.0f}s monitored, {total_messages} messages) ---")

    if not first_seen:
        print("  No property messages received during monitoring window.")
        return True

    # Column widths
    name_w = max(len(n) for n in first_seen) + 2

    print(f"  {'Property':<{name_w}} {'Count':>6}  {'First seen':>10}  {'Last seen':>10}")
    print(f"  {'-' * name_w} {'------':>6}  {'----------':>10}  {'----------':>10}")
    for prop in sorted(first_seen):
        first_dt = datetime.fromtimestamp(first_seen[prop]).strftime("%H:%M:%S")
        last_dt = datetime.fromtimestamp(last_seen[prop]).strftime("%H:%M:%S")
        print(
            f"  {prop:<{name_w}} {counts[prop]:>6}  {first_dt:>10}  {last_dt:>10}"
        )

    # Flow-property analysis
    print()
    if FLOW_PROPERTY in last_seen:
        flow_window = last_seen[FLOW_PROPERTY] - first_seen[FLOW_PROPERTY]
        print(
            f"  '{FLOW_PROPERTY}' publish window: {flow_window:.0f}s "
            f"({counts[FLOW_PROPERTY]} messages)"
        )
        if flow_window < 200:
            print(
                "  ✓ Flow property stopped publishing within expected ~3-minute window"
            )
        else:
            print(
                f"  ⚠ Flow property published for {flow_window:.0f}s — "
                "behaviour may have changed from the expected 3-minute window"
            )
    else:
        print(
            f"  '{FLOW_PROPERTY}' was never received — "
            "device may have been idle (no active flow) during the test"
        )

    if server_closed_at is not None:
        print(f"  Server closed connection at {server_closed_at:.0f}s")

    return True


async def run_all_tests(
    username: str,
    password: str,
    device_sn: str,
    product_sn: str,
) -> bool:
    """Authenticate once and run all verification tests."""
    if device_sn:
        print(f"Device serial : {device_sn}")
    if product_sn:
        print(f"Product serial: {product_sn}")

    # ── Step 1: Authenticate & fetch initial data ─────────────────────────
    print("\n--- Authentication & Initial Data ---")
    softener = IquaSoftener(
        username,
        password,
        device_serial_number=device_sn or None,
        product_serial_number=product_sn or None,
        enable_websocket=False,
    )
    try:
        data = softener.get_data()
        print("✓ Authentication successful")
        print(f"  Device state : {data.state.value}")
        print(f"  Current flow : {data.current_water_flow}")
    except Exception as err:
        print(f"✗ Authentication failed: {err}")
        return False

    # ── Step 2: Rate-limit header check ──────────────────────────────────
    check_rate_limit_headers(softener)

    # ── Step 3: Quick WebSocket connectivity smoke-test ───────────────────
    ws_ok = await test_websocket_connection(softener)
    if not ws_ok:
        return False

    # ── Step 4: Extended publish-window monitor ───────────────────────────
    await monitor_websocket_publish_window(softener)

    return True


def main():
    """Entry point.

    Credentials are read from the .env file (or environment variables).
    CLI arguments override .env values when provided:
      python test_websocket.py [username] [password] [device_serial] [product_serial] [websocket_base_url]
    """
    # Resolve credentials: .env → env vars → CLI args
    username = os.environ.get("IQUA_USERNAME", "")
    password = os.environ.get("IQUA_PASSWORD", "")
    device_sn = os.environ.get("IQUA_DEVICE_SERIAL", "")
    product_sn = os.environ.get("IQUA_PRODUCT_SERIAL", "")
    ws_base = os.environ.get("IQUA_WEBSOCKET_BASE", "")

    # CLI arguments override .env values
    if len(sys.argv) >= 2:
        username = sys.argv[1]
    if len(sys.argv) >= 3:
        password = sys.argv[2]
    if len(sys.argv) >= 4:
        device_sn = sys.argv[3]
    if len(sys.argv) >= 5:
        if sys.argv[4].startswith(("ws://", "wss://", "http://", "https://")):
            ws_base = sys.argv[4]
        else:
            product_sn = sys.argv[4]
    if len(sys.argv) >= 6:
        ws_base = sys.argv[5]

    if not username or not password or not (device_sn or product_sn):
        print(
            "Error: IQUA_USERNAME, IQUA_PASSWORD, and either IQUA_DEVICE_SERIAL "
            "or IQUA_PRODUCT_SERIAL must be set "
            "in .env or passed as CLI arguments."
        )
        print(
            "Usage: python test_websocket.py [username] [password] [device_serial] "
            "[product_serial] [websocket_base_url]"
        )
        sys.exit(1)

    if ws_base:
        global WEBSOCKET_BASE_OVERRIDE  # noqa: PLW0603
        WEBSOCKET_BASE_OVERRIDE = ws_base
        print(f"Using custom WebSocket base URL: {WEBSOCKET_BASE_OVERRIDE}")

    print("iQua Rate-Limit & WebSocket Verification")
    print("=" * 45)

    success = asyncio.run(run_all_tests(username, password, device_sn, product_sn))

    print("\n" + "=" * 45)
    if success:
        print("✓ Verification complete")
        print(
            "\nReview the rate-limit summary and WebSocket publish-window output above "
            "before proceeding with integration changes."
        )
    else:
        print("✗ One or more checks failed — see output above for details")
        print("\nPossible causes:")
        print("  1. Invalid credentials, device serial number, or product serial number")
        print("  2. Rate limit already exhausted — wait and retry")
        print("  3. Server temporarily unavailable")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
