"""Small, dependency-free configuration UI and display server for the add-on."""
from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

DATA_FILE = Path("/data/dashboards.json")
OPTIONS_FILE = Path("/data/options.json")
DISPLAY_FILE = Path("/app/web/display.html")
DEFAULTS = {
    "scheme": "ocean", "theme": "dark", "zoomOut": "1.2",
    "routeWidth": "12", "borderWidth": "7", "greenThreshold": "10",
    "amberThreshold": "30",
}


def load_dashboards() -> list[dict]:
    try:
        value = json.loads(DATA_FILE.read_text())
        return value if isinstance(value, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_dashboards(dashboards: list[dict]) -> None:
    temporary = DATA_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(dashboards, indent=2) + "\n")
    temporary.replace(DATA_FILE)


def api_key() -> str:
    try:
        return str(json.loads(OPTIONS_FILE.read_text()).get("here_api_key", "")).strip()
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def clean_dashboard(payload: dict, existing: dict | None = None) -> dict:
    name = str(payload.get("name", "")).strip()
    origin = str(payload.get("origin", "")).strip()
    destination = str(payload.get("destination", "")).strip()
    if not name or not origin or not destination:
        raise ValueError("Name, origin, and destination are required.")
    raw_id = str(existing["id"] if existing else (payload.get("id") or name)).lower()
    identifier = re.sub(r"[^a-z0-9-]+", "-", raw_id).strip("-")[:48]
    if not identifier:
        raise ValueError("The dashboard name does not produce a valid ID.")
    values = {"id": identifier, "name": name, "origin": origin, "destination": destination}
    values["scheme"] = str((existing or {}).get("scheme", "ocean"))
    for variant in ("full", "compact"):
        for key, default in DEFAULTS.items():
            field = variant + key[0].upper() + key[1:]
            fallback = (existing or {}).get(field, (existing or {}).get(key, default))
            values[field] = str(payload.get(field, fallback))
    return values


def admin_page() -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HERE Traffic Dashboards</title><style>
body{max-width:940px;margin:0 auto;padding:28px;font:16px system-ui,sans-serif;background:#0f172a;color:#f8fafc}h1{margin-bottom:4px}p{color:#cbd5e1}section{margin:24px 0;padding:22px;border:1px solid #334155;border-radius:12px;background:#1e293b}form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}label{display:grid;gap:5px;color:#cbd5e1;font-size:.9rem}input,select,button{padding:10px;border-radius:7px;font:inherit}input,select{border:1px solid #64748b;background:#0f172a;color:white}button{border:0;background:#38bdf8;color:#082f49;font-weight:700;cursor:pointer}.wide{grid-column:1/-1}.row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;border-top:1px solid #334155;padding:15px 0}.row:first-child{border:0}.row strong{min-width:170px}.row small{color:#94a3b8;flex:1}.secondary{background:#334155;color:#fff}.danger{background:#b91c1c;color:#fff}code{padding:2px 5px;background:#0f172a;border-radius:4px}@media(max-width:600px){form{grid-template-columns:1fr}.row strong{min-width:100%}}</style></head><body>
<h1>HERE Traffic Dashboards</h1><p>Set the shared HERE API key in this app's <strong>Configuration</strong> tab. Create named displays below; no device needs to enter the key.</p>
<section><h2 id="form-title">New dashboard</h2><form id="editor"><input id="edit-id" type="hidden"><label>Name<input name="name" required placeholder="Morning commute"></label><label>Origin<input name="origin" required placeholder="Home"></label><label>Destination<input name="destination" required placeholder="Office"></label><h3 class="wide">Full-screen display</h3><label>Map appearance<select name="fullTheme"><option value="dark">Dark</option><option value="light">Light</option></select></label><label>Map framing<select name="fullZoomOut"><option value="0.7">Normal</option><option value="1.2" selected>Spacious</option><option value="1.7">Extra spacious</option></select></label><label>Route width<select name="fullRouteWidth"><option value="8">Slim</option><option value="12" selected>Standard</option><option value="16">Wide</option><option value="22">Extra wide</option></select></label><label>Route border<select name="fullBorderWidth"><option value="4">Thin</option><option value="7" selected>Standard</option><option value="10">Thick</option></select></label><label>Green delay through (%)<input name="fullGreenThreshold" type="number" min="0" max="100" value="10"></label><label>Amber delay through (%)<input name="fullAmberThreshold" type="number" min="0" max="100" value="30"></label><h3 class="wide">Compact display</h3><label>Map appearance<select name="compactTheme"><option value="dark">Dark</option><option value="light">Light</option></select></label><label>Map framing<select name="compactZoomOut"><option value="0.7">Normal</option><option value="1.2" selected>Spacious</option><option value="1.7">Extra spacious</option></select></label><label>Route width<select name="compactRouteWidth"><option value="8">Slim</option><option value="12" selected>Standard</option><option value="16">Wide</option><option value="22">Extra wide</option></select></label><label>Route border<select name="compactBorderWidth"><option value="4">Thin</option><option value="7" selected>Standard</option><option value="10">Thick</option></select></label><label>Green delay through (%)<input name="compactGreenThreshold" type="number" min="0" max="100" value="10"></label><label>Amber delay through (%)<input name="compactAmberThreshold" type="number" min="0" max="100" value="30"></label><div class="wide"><button type="submit">Save dashboard</button> <button class="secondary" id="cancel" type="button" hidden>Cancel edit</button></div></form></section>
<section><h2>Your dashboard displays</h2><p>Use <em>Full screen</em> for a wall/tablet display and <em>Compact</em> for a dashboard iframe card. Ingress URLs work within Home Assistant; direct URLs require this app's port to be reachable on your LAN.</p><div id="list">Loading…</div></section>
<script>const f=document.querySelector('#editor'),list=document.querySelector('#list'),cancel=document.querySelector('#cancel');let items=[];const base=location.pathname.replace(/\/$/,'');const route=p=>`${base}${p}`;async function request(path,options){const r=await fetch(route(path),options);const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data}function field(name,value){const input=f.elements[name];if(input)input.value=value??''}function reset(){f.reset();field('edit-id','');document.querySelector('#form-title').textContent='New dashboard';cancel.hidden=true}function render(){list.innerHTML=items.length?'': '<p>No dashboards yet.</p>';for(const d of items){const full=route(`/display/${d.id}`),compact=route(`/card/${d.id}`);const row=document.createElement('div');row.className='row';row.innerHTML=`<strong>${d.name}</strong><small>${d.origin} → ${d.destination}<br>Full: <code>${full}</code><br>Compact: <code>${compact}</code></small><button class="secondary">Edit</button><button class="danger">Delete</button>`;row.querySelector('.secondary').onclick=()=>{for(const [k,v]of Object.entries(d))field(k,v);field('edit-id',d.id);document.querySelector('#form-title').textContent=`Edit: ${d.name}`;cancel.hidden=false;scrollTo({top:0,behavior:'smooth'})};row.querySelector('.danger').onclick=async()=>{if(confirm(`Delete ${d.name}?`)){await request(`/api/dashboards/${d.id}`,{method:'DELETE'});load()}};list.append(row)}}async function load(){items=await request('/api/dashboards');render()}f.onsubmit=async e=>{e.preventDefault();const id=f.elements['edit-id'].value;const data=Object.fromEntries(new FormData(f));const path=id?`/api/dashboards/${id}`:'/api/dashboards';await request(path,{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});reset();load()};cancel.onclick=reset;load().catch(e=>list.textContent=e.message);</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(fmt % args, flush=True)

    def send_json(self, value: object, status: int = 200) -> None:
        data = json.dumps(value).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def send_html(self, value: str, status: int = 200) -> None:
        data = value.encode(); self.send_response(status); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0")); return json.loads(self.rfile.read(length) or b"{}")

    def find(self, identifier: str) -> tuple[list[dict], int]:
        dashboards = load_dashboards()
        for index, dashboard in enumerate(dashboards):
            if dashboard["id"] == identifier: return dashboards, index
        raise KeyError("Dashboard not found.")

    def display(self, identifier: str, compact: bool) -> None:
        try:
            dashboards, index = self.find(identifier)
            dashboard = dashboards[index]
            variant = "compact" if compact else "full"
            config = {**DEFAULTS, **dashboard, "apiKey": api_key()}
            for key, default in DEFAULTS.items():
                field = variant + key[0].upper() + key[1:]
                config[key] = dashboard.get(field, dashboard.get(key, default))
            if not config["apiKey"]: raise ValueError("Set the HERE API key in this app's Configuration tab first.")
            injected = json.dumps(config).replace("<", "\\u003c")
            flags = f"<script>window.HERE_TRAFFIC_CONFIG={injected};window.HERE_TRAFFIC_COMPACT={str(compact).lower()};</script>"
            self.send_html(DISPLAY_FILE.read_text().replace("</head>", flags + "</head>", 1))
        except (KeyError, ValueError) as error:
            self.send_html(f"<h1>HERE Traffic Dashboard</h1><p>{error}</p>", 404)

    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path).rstrip("/") or "/"
        if path == "/": return self.send_html(admin_page())
        if path == "/health": return self.send_json({"ok": True})
        if path == "/api/dashboards": return self.send_json(load_dashboards())
        match = re.fullmatch(r"/(display|card)/([a-z0-9-]+)", path)
        if match: return self.display(match.group(2), match.group(1) == "card")
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        if urlparse(self.path).path.rstrip("/") != "/api/dashboards": return self.send_json({"error": "Not found"}, 404)
        try:
            dashboards = load_dashboards(); item = clean_dashboard(self.payload())
            if any(d["id"] == item["id"] for d in dashboards): raise ValueError("A dashboard with this name already exists.")
            dashboards.append(item); save_dashboards(dashboards); self.send_json(item, HTTPStatus.CREATED)
        except (ValueError, json.JSONDecodeError) as error: self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def do_PUT(self) -> None:
        match = re.fullmatch(r"/api/dashboards/([a-z0-9-]+)", urlparse(self.path).path.rstrip("/"))
        if not match: return self.send_json({"error": "Not found"}, 404)
        try:
            dashboards, index = self.find(match.group(1)); dashboards[index] = clean_dashboard(self.payload(), dashboards[index]); save_dashboards(dashboards); self.send_json(dashboards[index])
        except (KeyError, ValueError, json.JSONDecodeError) as error: self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        match = re.fullmatch(r"/api/dashboards/([a-z0-9-]+)", urlparse(self.path).path.rstrip("/"))
        if not match: return self.send_json({"error": "Not found"}, 404)
        try:
            dashboards, index = self.find(match.group(1)); dashboards.pop(index); save_dashboards(dashboards); self.send_json({"ok": True})
        except KeyError as error: self.send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)


if __name__ == "__main__":
    print("Starting HERE Traffic Dashboards on port 8099", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
