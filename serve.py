#!/usr/bin/env python3
"""
Local dev server for Ad Tech Intelligence dashboard.
Serves static files from docs/ and provides /api/refresh to re-run the pipeline.

Usage: python3 serve.py
"""

import http.server
import json
import os
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time

PORT = 8888
ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
SCRIPT = os.path.join(ROOT, "scripts", "generate_daily_intel.py")

_refresh_lock = threading.Lock()
_refresh_status = {"running": False, "last_run": None, "last_result": None}


def kill_port(port):
    """Kill any process using this port (macOS/Linux)."""
    try:
        out = subprocess.check_output(
            ["lsof", "-t", "-i", f":{port}"], stderr=subprocess.DEVNULL, text=True
        )
        for pid in out.strip().split("\n"):
            pid = pid.strip()
            if pid and pid != str(os.getpid()):
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
        time.sleep(1)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def find_free_port(preferred, fallbacks=None):
    """Try preferred port, then fallbacks, then any free port."""
    fallbacks = fallbacks or [8080, 8888, 9000, 9090]
    for p in [preferred] + fallbacks:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", p))
            s.close()
            return p
        except OSError:
            continue
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def run_pipeline():
    """Execute the pipeline in a subprocess."""
    _refresh_status["running"] = True
    _refresh_status["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        result = subprocess.run(
            ["python3", SCRIPT, "--days", "14", "--output", os.path.join(DOCS, "data")],
            capture_output=True, text=True, timeout=300, cwd=ROOT,
        )
        _refresh_status["last_result"] = {
            "success": result.returncode == 0,
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
            "stderr_tail": result.stderr[-300:] if result.stderr else "",
        }
    except Exception as e:
        _refresh_status["last_result"] = {"success": False, "error": str(e)}
    finally:
        _refresh_status["running"] = False


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOCS, **kw)

    def do_POST(self):
        if self.path == "/api/refresh":
            if _refresh_status["running"]:
                self._json_response(200, {"status": "already_running"})
                return
            if _refresh_lock.acquire(blocking=False):
                try:
                    t = threading.Thread(target=run_pipeline, daemon=True)
                    t.start()
                    self._json_response(200, {"status": "started"})
                finally:
                    _refresh_lock.release()
            else:
                self._json_response(200, {"status": "already_running"})
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path == "/api/refresh/status":
            self._json_response(200, _refresh_status)
        else:
            super().do_GET()

    def _json_response(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        if "/api/refresh" in (args[0] if args else ""):
            super().log_message(fmt, *args)


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        super().server_bind()


if __name__ == "__main__":
    kill_port(PORT)

    port = find_free_port(PORT)
    if port != PORT:
        print(f"  Port {PORT} busy, using {port} instead.")

    try:
        with ReusableTCPServer(("", port), Handler) as httpd:
            url = f"http://localhost:{port}/curator.html"
            print(f"\n  Ad Tech Intelligence - Local Server")
            print(f"  {url}")
            print(f"  POST /api/refresh  -> re-run pipeline")
            print(f"  GET  /api/refresh/status -> check status")
            print(f"  Press Ctrl+C to stop\n")
            sys.stdout.flush()
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n  Server stopped.")
    except OSError as e:
        print(f"  Error: {e}")
        print(f"  Try: kill -9 $(lsof -t -i :{port})")
        sys.exit(1)
