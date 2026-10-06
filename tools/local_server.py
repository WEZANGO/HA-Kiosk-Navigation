"""Local dev harness for HA-Kiosk-Navigation.

app.py hard-codes /data/*.json and /app/web/display.html, so a local run must
rebind those module constants before serving app.Handler (see the repo notes:
DISPLAY_FILE is a module constant read at request time).

Usage:  python3 tools/local_server.py [port]
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
DATA_DIR = Path(tempfile.mkdtemp(prefix="kiosk-traffic-"))

app.DATA_FILE = DATA_DIR / "dashboards.json"
app.OPTIONS_FILE = DATA_DIR / "options.json"
app.DISPLAY_FILE = ROOT / "web" / "display.html"
app.OPTIONS_FILE.write_text(json.dumps({"here_api_key": "DEVKEY"}))
# Local dev: no auth. Fail open like the app does when no token is available.
app.access_token = lambda: ""

if __name__ == "__main__":
    from http.server import ThreadingHTTPServer
    print(f"data dir: {DATA_DIR}")
    print(f"serving on http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), app.Handler).serve_forever()