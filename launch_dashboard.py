"""
launch_dashboard.py
-------------------
Starts the Streamlit dashboard (opens browser once).

    python launch_dashboard.py
    python launch_dashboard.py --stop   # free port 8501 if a stale server is running

Press Ctrl+C in this window to stop the server.
"""

from __future__ import annotations

import argparse
import socket

from brand import APP_NAME
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = 8501
PORT_RANGE = range(8501, 8510)


def _port_in_use(port: int) -> bool:
    """True if something is accepting connections on localhost:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _pids_on_port(port: int) -> list[int]:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return []
    pids = []
    needle = f":{port}"
    for line in out.splitlines():
        if needle not in line:
            continue
        upper = line.upper()
        if "LISTENING" not in upper and "ESTABLISHED" not in upper:
            continue
        parts = line.split()
        if parts:
            try:
                pids.append(int(parts[-1]))
            except ValueError:
                pass
    return list(dict.fromkeys(pids))


def _find_port() -> int:
    for port in PORT_RANGE:
        if not _port_in_use(port):
            return port
    raise RuntimeError(f"No free port in {PORT_RANGE.start}–{PORT_RANGE.stop - 1}")


def _stop_stale_servers() -> None:
    killed = []
    for port in PORT_RANGE:
        for pid in _pids_on_port(port):
            if pid in killed:
                continue
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    check=False,
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                killed.append(pid)
                print(f"  Stopped PID {pid} (was using port {port})")
            except Exception as e:
                print(f"  Could not stop PID {pid}: {e}")
    if not killed:
        print("  No dashboard processes found on ports 8501–8509.")


def main():
    parser = argparse.ArgumentParser(description=f"Launch {APP_NAME} dashboard")
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop any stale Streamlit/Python process on ports 8501–8509",
    )
    args = parser.parse_args()

    if args.stop:
        print("Stopping stale dashboard processes…")
        _stop_stale_servers()
        return

    if _port_in_use(DEFAULT_PORT):
        pids = _pids_on_port(DEFAULT_PORT)
        print("=" * 60)
        print("  Port 8501 is already in use")
        print("=" * 60)
        print("  A dashboard may already be running:")
        print("    → http://localhost:8501")
        if pids:
            print(f"  Process ID(s): {', '.join(map(str, pids))}")
            print(f"  To stop it:  python launch_dashboard.py --stop")
            print(f"            or: taskkill /PID {pids[0]} /F")
        print()

    port = _find_port()
    url = f"http://localhost:{port}"

    if port != DEFAULT_PORT:
        print(f"  Starting on alternate port: {url}\n")

    print("=" * 60)
    print(f"  {APP_NAME}")
    print("=" * 60)
    print(f"\n  URL: {url}")
    print("  Browser opens in a few seconds.")
    print("  Keep this window open while you use the dashboard.")
    print("  Press Ctrl+C here when you are done (clean shutdown).\n")

    def _open_browser_once():
        time.sleep(2.5)
        webbrowser.open(url)

    threading.Thread(target=_open_browser_once, daemon=True).start()

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ROOT / "dashboard.py"),
        "--server.port",
        str(port),
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.runOnSave=false",
    ]

    try:
        subprocess.run(cmd, cwd=ROOT, check=False)
    except KeyboardInterrupt:
        print("\n  Dashboard stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
