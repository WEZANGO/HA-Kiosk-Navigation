"""Small, dependency-free configuration UI and display server for the add-on."""
from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import urlopen

DATA_FILE = Path("/data/dashboards.json")
OPTIONS_FILE = Path("/data/options.json")
DISPLAY_FILE = Path("/app/web/display.html")
DEFAULTS = {
    "scheme": "ocean", "theme": "dark", "zoomOut": "1.2",
    "routeWidth": "12", "borderWidth": "7", "greenThreshold": "10",
    "amberThreshold": "30", "refreshInterval": "5", "title": "",
    "titlePosition": "top", "titleSize": "medium", "titleBackground": "rounded",
    "titleFont": "system", "metricSize": "large", "metricStyle": "rounded",
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
body{max-width:940px;margin:0 auto;padding:28px;font:16px system-ui,sans-serif;background:#0f172a;color:#f8fafc}h1{margin-bottom:4px}p{color:#cbd5e1}section{margin:24px 0;padding:22px;border:1px solid #334155;border-radius:12px;background:#1e293b}form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}label{display:grid;gap:5px;color:#cbd5e1;font-size:.9rem}input,select,button{padding:10px;border-radius:7px;font:inherit}input,select{border:1px solid #64748b;background:#0f172a;color:white}button{border:0;background:#38bdf8;color:#082f49;font-weight:700;cursor:pointer}.wide{grid-column:1/-1}.row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;border-top:1px solid #334155;padding:15px 0}.row:first-child{border:0}.row strong{min-width:170px}.row small{color:#94a3b8;flex:1}.secondary{background:#334155;color:#fff}.danger{background:#b91c1c;color:#fff}code{padding:2px 5px;background:#0f172a;border-radius:4px}@media(max-width:600px){form{grid-template-columns:1fr}.row strong{min-width:100%}}.modal-overlay{position:fixed;inset:0;z-index:100;display:grid;justify-items:center;align-items:start;padding:20px;background:rgba(3,7,18,.85);overflow-y:auto}.modal-overlay[hidden]{display:none}.modal-content{width:min(100%,680px);max-height:calc(100vh-40px);overflow:auto;padding:24px;border:1px solid #475569;border-radius:14px;background:#1e293b;box-shadow:0 20px 60px rgba(0,0,0,.4)}.toast{position:fixed;top:24px;left:50%;transform:translateX(-50%);z-index:200;display:flex;align-items:center;gap:10px;padding:14px 24px;border-radius:10px;background:#166534;color:#bbf7d0;font-weight:700;font-size:1.05rem;box-shadow:0 8px 30px rgba(0,0,0,.5);animation:toast-in .3s ease-out,toast-out .3s .9s ease-in forwards}.toast .checkmark{font-size:1.3rem}@keyframes toast-in{from{opacity:0;transform:translateX(-50%) translateY(-12px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}@keyframes toast-out{from{opacity:1}to{opacity:0;transform:translateX(-50%) translateY(-12px)}}.wide-button{display:inline-block;padding:12px 24px;border:2px dashed #64748b;border-radius:10px;background:transparent;color:#38bdf8;font:inherit;font-weight:700;cursor:pointer;width:auto}.modal-buttons{display:flex;gap:10px;grid-column:1/-1}
.field-label{font-weight:600}.pick{grid-column:1/-1;margin:2px 0 6px}.pick-head{display:flex;align-items:center;gap:8px;background:#0f172a;border:1px solid #64748b;border-radius:9px;padding:11px 14px;color:#cbd5e1;font:inherit;font-size:.92rem;cursor:pointer;width:100%;text-align:left}.pick-head b{color:#f8fafc}.pick-head .chev{margin-left:auto;transition:transform .2s}.pick.open .chev{transform:rotate(180deg)}.pick-body{display:none;margin-top:10px;padding:12px;border:1px solid #334155;border-radius:10px;background:#0b1222}.pick.open .pick-body{display:block}.pick-tabs{display:flex;gap:8px;margin-bottom:10px}.pick-tabs button{background:#334155;color:#e2e8f0;font:inherit;font-size:.88rem;padding:7px 14px;border-radius:7px;cursor:pointer}.pick-tabs button[aria-selected="true"]{background:#38bdf8;color:#082f49;font-weight:700}.pick-search{display:flex;gap:8px}.pick-search input{flex:1}.pick-search button{padding:10px 16px}.pick-results{margin:10px 0 0;padding:0;list-style:none;display:grid;gap:6px;max-height:180px;overflow:auto}.pick-results button{display:block;width:100%;text-align:left;background:#0f172a;border:1px solid #334155;color:#e2e8f0;font:inherit;font-size:.88rem;padding:9px 12px;border-radius:8px;cursor:pointer}.pick-results button:hover{border-color:#38bdf8}.pick-results .sub{display:block;color:#94a3b8;font-size:.8rem}.pick-status{margin:10px 0 0;color:#94a3b8;font-size:.86rem}.pick-status.error{color:#fca5a5}.pick-map-wrap{position:relative;height:320px;border-radius:8px;overflow:hidden;border:1px solid #334155}.pick-hint{position:absolute;z-index:1000;top:10px;left:50%;transform:translateX(-50%);padding:6px 14px;border-radius:999px;background:rgba(15,23,42,.88);color:#cbd5e1;font-size:.8rem;pointer-events:none;white-space:nowrap}.pick-actions{display:flex;align-items:center;gap:10px;margin-top:10px}.pick-coords{flex:1;color:#94a3b8;font-size:.84rem;font-family:ui-monospace,monospace}.pick-actions .use{background:#38bdf8;color:#082f49;font-weight:700;padding:9px 16px;cursor:pointer;border:0;border-radius:7px;font:inherit}.pick-actions .use:disabled{opacity:.4;cursor:not-allowed}.leaflet-container{background:#0b1222;font:inherit}</style><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" /><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script></head><body>
<h1>HERE Traffic Dashboards</h1><p>Set the shared HERE API key in this app's <strong>Configuration</strong> tab. Create named displays below; no device needs to enter the key.</p>
<section><h2>Dashboards</h2><button id="new-dashboard" class="wide-button">+ New dashboard</button></section>
<section><h2>Your dashboard displays</h2><p>Use <em>Full screen</em> for a wall/tablet display and <em>Compact</em> for a dashboard iframe card. Ingress URLs work within Home Assistant; direct URLs require this app's port to be reachable on your LAN.</p><div id="list">Loading…</div></section>
<div id="editor-modal" class="modal-overlay" hidden><div class="modal-content"><h2 id="modal-title">New dashboard</h2><form id="editor"><input id="edit-id" type="hidden"><label>Name<input name="name" required placeholder="Morning commute"></label><label>Origin<input name="origin" required placeholder="Home"></label><label>Destination<input name="destination" required placeholder="Office"></label><div class="pick" id="pick-origin"><button type="button" class="pick-head"><span>📍 Choose <b>Origin</b> on a map</span><span class="chev">▾</span></button><div class="pick-body"><div class="pick-search"><input type="search" placeholder="Search a place or address…" aria-label="Search origin location"><button type="button">Search</button></div><ul class="pick-results"></ul><p class="pick-status" hidden></p><div class="pick-map-wrap"><div class="pick-hint">Tap the map to drop or move the pin</div><div class="pick-map" style="height:100%"></div></div><div class="pick-actions"><span class="pick-coords">No point selected</span><button type="button" class="use" disabled>Use this location</button></div></div></div><div class="pick" id="pick-destination"><button type="button" class="pick-head"><span>📍 Choose <b>Destination</b> on a map</span><span class="chev">▾</span></button><div class="pick-body"><div class="pick-search"><input type="search" placeholder="Search a place or address…" aria-label="Search destination location"><button type="button">Search</button></div><ul class="pick-results"></ul><p class="pick-status" hidden></p><div class="pick-map-wrap"><div class="pick-hint">Tap the map to drop or move the pin</div><div class="pick-map" style="height:100%"></div></div><div class="pick-actions"><span class="pick-coords">No point selected</span><button type="button" class="use" disabled>Use this location</button></div></div></div><h3 class="wide">Full-screen display</h3><label>Map appearance<select name="fullTheme"><option value="auto">Automatic (device setting)</option><option value="dark">Dark</option><option value="light">Light</option></select></label><label>Route outline colour<select name="fullScheme"><option value="ocean">Ocean blue</option><option value="emerald">Emerald green</option><option value="sunset">Sunset orange</option><option value="violet">Violet</option><option value="contrast">High contrast yellow</option></select></label><label>Map framing<select name="fullZoomOut"><option value="0.7">Normal</option><option value="1.2" selected>Spacious</option><option value="1.7">Extra spacious</option></select></label><label>Route width<select name="fullRouteWidth"><option value="8">Slim</option><option value="12" selected>Standard</option><option value="16">Wide</option><option value="22">Extra wide</option></select></label><label>Route border<select name="fullBorderWidth"><option value="4">Thin</option><option value="7" selected>Standard</option><option value="10">Thick</option></select></label><label>Green delay through (%)<input name="fullGreenThreshold" type="number" min="0" max="100" value="10"></label><label>Amber delay through (%)<input name="fullAmberThreshold" type="number" min="0" max="100" value="30"></label><label>Refresh interval<select name="fullRefreshInterval"><option value="0">Off</option><option value="1">Every minute</option><option value="5" selected>Every 5 minutes</option><option value="10">Every 10 minutes</option><option value="15">Every 15 minutes</option><option value="30">Every 30 minutes</option></select></label><h3 class="wide">Compact display</h3><label>Map appearance<select name="compactTheme"><option value="auto">Automatic (device setting)</option><option value="dark">Dark</option><option value="light">Light</option></select></label><label>Route outline colour<select name="compactScheme"><option value="ocean">Ocean blue</option><option value="emerald">Emerald green</option><option value="sunset">Sunset orange</option><option value="violet">Violet</option><option value="contrast">High contrast yellow</option></select></label><label>Map framing<select name="compactZoomOut"><option value="0.7">Normal</option><option value="1.2" selected>Spacious</option><option value="1.7">Extra spacious</option></select></label><label>Route width<select name="compactRouteWidth"><option value="8">Slim</option><option value="12" selected>Standard</option><option value="16">Wide</option><option value="22">Extra wide</option></select></label><label>Route border<select name="compactBorderWidth"><option value="4">Thin</option><option value="7" selected>Standard</option><option value="10">Thick</option></select></label><label>Green delay through (%)<input name="compactGreenThreshold" type="number" min="0" max="100" value="10"></label><label>Amber delay through (%)<input name="compactAmberThreshold" type="number" min="0" max="100" value="30"></label><label>Refresh interval<select name="compactRefreshInterval"><option value="0">Off</option><option value="1">Every minute</option><option value="5" selected>Every 5 minutes</option><option value="10">Every 10 minutes</option><option value="15">Every 15 minutes</option><option value="30">Every 30 minutes</option></select></label><div class="modal-buttons"><button type="submit">Save dashboard</button> <button class="secondary" id="cancel" type="button">Cancel</button></div></form></div></div>
<script>const f=document.querySelector('#editor'),list=document.querySelector('#list'),cancel=document.querySelector('#cancel'),modal=document.querySelector('#editor-modal'),modalTitle=document.querySelector('#modal-title'),newBtn=document.querySelector('#new-dashboard');let items=[];const base=location.pathname.replace(/\/$/,'');const route=p=>`${base}${p}`;async function request(path,options){const r=await fetch(route(path),options);const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data}function field(name,value){const input=f.elements[name];if(input)input.value=value??''}function resetForm(){f.reset();field('edit-id','');modalTitle.textContent='New dashboard'}function openModal(dashboard){resetForm();if(dashboard){for(const[k,v]of Object.entries(dashboard))field(k,v);field('edit-id',dashboard.id);modalTitle.textContent=`Edit: ${dashboard.name}`}modal.hidden=false}function closeModal(){modal.hidden=true;resetForm()}function showToast(message){const toast=document.createElement('div');toast.className='toast';toast.innerHTML=`<span class="checkmark">✓</span>${message}`;document.body.append(toast);setTimeout(()=>toast.remove(),1300)}function render(){list.innerHTML=items.length?'': '<p>No dashboards yet.</p>';for(const d of items){const full=route(`/display/${d.id}`),compact=route(`/card/${d.id}`);const row=document.createElement('div');row.className='row';row.innerHTML=`<strong>${d.name}</strong><small>${d.origin} → ${d.destination}<br>Full: <code>${full}</code><br>Compact: <code>${compact}</code></small><button class="secondary">Edit</button><button class="danger">Delete</button>`;row.querySelector('.secondary').onclick=()=>openModal(d);row.querySelector('.danger').onclick=async()=>{if(confirm(`Delete ${d.name}?`)){await request(`/api/dashboards/${d.id}`,{method:'DELETE'});load()}};list.append(row)}}async function load(){items=await request('/api/dashboards');render()}f.onsubmit=async e=>{e.preventDefault();const id=f.elements['edit-id'].value;const data=Object.fromEntries(new FormData(f));const path=id?`/api/dashboards/${id}`:'/api/dashboards';await request(path,{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});showToast(id?'Saved':'Created');closeModal();load()};cancel.onclick=closeModal;newBtn.onclick=()=>openModal();modal.addEventListener('click',e=>{if(e.target===modal)closeModal()});
const LATLNG=/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/;
function setupPicker(which){
  const root=document.querySelector('#pick-'+which),target=f.elements[which];
  const head=root.querySelector('.pick-head'),body=root.querySelector('.pick-body'),searchIn=root.querySelector('.pick-search input'),searchBtn=root.querySelector('.pick-search button'),results=root.querySelector('.pick-results'),statusEl=root.querySelector('.pick-status'),mapDiv=root.querySelector('.pick-map'),coordsEl=root.querySelector('.pick-coords'),useBtn=root.querySelector('.use');
  let map,marker,pending=null;
  const setStatus=(msg,error)=>{statusEl.textContent=msg;statusEl.classList.toggle('error',!!error);statusEl.hidden=!msg};
  function ensureMap(){
    if(map){setTimeout(()=>map.invalidateSize(),50);return}
    map=L.map(mapDiv).setView([53.35,-6.26],6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
    map.on('click',e=>placePin(e.latlng.lat,e.latlng.lng));
  }
  function placePin(lat,lng,title){
    pending={lat,lng,title:title||''};
    if(!marker)marker=L.marker([lat,lng],{draggable:true}).addTo(map);
    else marker.setLatLng([lat,lng]);
    marker.bindTooltip(title||'Drag me',{direction:'top',offset:[0,-8]});
    marker.on('dragend',()=>{const p=marker.getLatLng();pending={lat:p.lat,lng:p.lng,title:pending.title};updateCoords()});
    map.panTo([lat,lng]);updateCoords();
  }
  function updateCoords(){coordsEl.textContent=pending?`${pending.lat.toFixed(5)}, ${pending.lng.toFixed(5)}${pending.title?' — '+pending.title:''}`:'No point selected';useBtn.disabled=!pending}
  function applyPending(){
    if(!pending)return;
    target.value=`${pending.lat.toFixed(5)}, ${pending.lng.toFixed(5)}`;
    target.dispatchEvent(new Event('input',{bubbles:true}));
    setStatus(`Saved to ${which.charAt(0).toUpperCase()+which.slice(1)}: ${pending.title||coordsEl.textContent}`);
    useBtn.disabled=true;pending=null;
  }
  useBtn.onclick=applyPending;
  async function search(){
    const q=searchIn.value.trim();if(!q)return;
    setStatus('Searching…');results.innerHTML='';
    try{
      const data=await request(`/api/geocode?q=${encodeURIComponent(q)}`);
      if(!data.items.length){setStatus('No matches found.',true);return}
      setStatus('');
      for(const item of data.items){
        const li=document.createElement('li'),btn=document.createElement('button');
        btn.type='button';
        btn.innerHTML=`${item.title}<span class="sub">${item.address||''}</span>`;
        btn.onclick=()=>{placePin(item.position.lat,item.position.lng,item.title);map.setView([item.position.lat,item.position.lng],13)};
        li.append(btn);results.append(li);
      }
    }catch(err){setStatus(err.message,true)}
  }
  searchBtn.onclick=search;searchIn.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();search()}};
  head.onclick=()=>{
    const open=root.classList.toggle('open');
    if(open){
      ensureMap();
      const m=LATLNG.exec(target.value);
      if(m){const lat=+m[1],lng=+m[2];placePin(lat,lng,'Current '+which);map.setView([lat,lng],13)}
      else setStatus(pending?'':'Search above or tap the map to drop a pin.');
    }else{results.innerHTML='';setStatus('')}
  };
}
setupPicker('origin');setupPicker('destination');
load().catch(e=>list.textContent=e.message);</script></body></html>"""



PRESENTATION_FIELDS = """<script>
const editor=document.querySelector('#editor');
const label=(name,text)=>`<span class="field-label">${text}</span>`;
const select=(name,text,values,selected)=>`<label>${label(name,text)}<select name="${name}">${values.map(([value,label])=>`<option value="${value}"${value===selected?' selected':''}>${label}</option>`).join('')}</select></label>`;
const input=(name,text,placeholder)=>`<label>${label(name,text)}<input name="${name}" placeholder="${placeholder}"></label>`;
const options={
 position:[['top','Top middle'],['bottom','Bottom middle']],
 size:[['small','Small'],['medium','Medium'],['large','Large']],
 background:[['rounded','Rounded background'],['none','No background']],
 font:[['system','System sans'],['serif','Serif'],['mono','Monospace']],
 cards:[['small','Small'],['medium','Medium'],['large','Large']],
 cardStyle:[['rounded','Rounded cards'],['vignette','Corner vignette']]
};
for(const [prefix,heading] of [['full','Full-screen presentation'],['compact','Compact presentation']]){
  const anchor=[...editor.querySelectorAll('h3')].find(node=>node.textContent.startsWith(prefix==='full'?'Full':'Compact'));
  anchor.insertAdjacentHTML('afterend', `<h4 class="wide">${heading}</h4>${input(prefix+'Title','Optional title','e.g. Morning commute')}${select(prefix+'TitlePosition','Title position',options.position,'top')}${select(prefix+'TitleSize','Title size',options.size,'medium')}${select(prefix+'TitleBackground','Title background',options.background,'rounded')}${select(prefix+'TitleFont','Title font',options.font,'system')}${select(prefix+'MetricSize','Card size',options.cards,'large')}${select(prefix+'MetricStyle','Card style',options.cardStyle,'rounded')}`);
}
</script>"""


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

    def geocode(self) -> None:
        query = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
        if not query: return self.send_json({"items": []})
        key = api_key()
        if not key: return self.send_json({"error": "Set the HERE API key in this app's Configuration tab first."}, 400)
        url = "https://geocode.search.hereapi.com/v1/geocode?" + urlencode({"q": query, "apiKey": key, "limit": "6"})
        try:
            with urlopen(url, timeout=10) as response: data = json.load(response)
        except OSError:
            return self.send_json({"error": "Location search failed — check the API key and network."}, 502)
        items = [{"title": i.get("title", ""), "address": i.get("address", {}).get("label", ""), "position": i.get("position", {})}
                 for i in data.get("items", []) if i.get("position")]
        self.send_json({"items": items})

    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path).rstrip("/") or "/"
        if path == "/": return self.send_html(admin_page().replace("</body>", PRESENTATION_FIELDS + "</body>"))
        if path == "/health": return self.send_json({"ok": True})
        if path == "/api/dashboards": return self.send_json(load_dashboards())
        if path == "/api/geocode": return self.geocode()
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
