"""Small, dependency-free configuration UI and display server for the add-on."""
from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import urlopen
import secrets

DATA_FILE = Path("/data/dashboards.json")
OPTIONS_FILE = Path("/data/options.json")
DISPLAY_FILE = Path("/app/web/display.html")
DEFAULTS = {
    "scheme": "ocean", "theme": "dark", "zoomOut": "1.2",
    "routeWidth": "12", "borderWidth": "7", "greenThreshold": "10",
    "amberThreshold": "30", "refreshInterval": "5", "title": "",
    "titlePosition": "top", "titleSize": "medium", "titleBackground": "rounded",
    "titleFont": "system", "metricSize": "large", "metricStyle": "rounded",
    "vignetteOpacity": "5", "vignetteSize": "5", "vignettePosition": "all",
    "showDuration": "true", "showNormal": "true", "showDelay": "true", "showDistance": "true",
    "tileDuration": "bl", "tileNormal": "tl", "tileDelay": "br", "tileDistance": "tr",
    "originIcon": "home", "destinationIcon": "flag",
    "originShape": "circle", "destinationShape": "circle",
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


def access_token() -> str:
    """Shared access token for direct (non-ingress) connections.

    HA ingress already authenticates users before requests reach this app, so
    ingress traffic needs no token. Direct connections (port 8099 — kiosks,
    dashboard iframes, shared links) are authenticated with this token, stored
    in /data/options.json as access_token. A stable random default is created
    on first read so it works out of the box.
    """
    try:
        options = json.loads(OPTIONS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        options = {}
    token = str(options.get("access_token", "")).strip()
    if not token:
        token = secrets.token_urlsafe(24)
        options["access_token"] = token
        try:
            OPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = OPTIONS_FILE.with_suffix(".tmp")
            temporary.write_text(json.dumps(options, indent=2) + "\n")
            temporary.replace(OPTIONS_FILE)
        except OSError:
            return ""
    return token


def clean_dashboard(payload: dict, existing: dict | None = None) -> dict:
    name = str(payload.get("name", "")).strip()
    origin = str(payload.get("origin", "")).strip()
    destination = str(payload.get("destination", "")).strip()
    if not name or not origin or not destination:
        raise ValueError("Name, origin, and destination are required.")
    kind = str(payload.get("kind") or (existing or {}).get("kind") or "full").strip().lower()
    if kind not in ("full", "compact"):
        kind = "full"
    raw_id = str(existing["id"] if existing else (payload.get("id") or name)).lower()
    identifier = re.sub(r"[^a-z0-9-]+", "-", raw_id).strip("-")[:48]
    if not identifier:
        raise ValueError("The dashboard name does not produce a valid ID.")
    values = {"id": identifier, "name": name, "origin": origin, "destination": destination, "kind": kind}
    values["scheme"] = str((existing or {}).get("scheme", "ocean"))
    # Marker settings are shared by both variants (not per-variant fields).
    for key in ("originIcon", "originShape", "destinationIcon", "destinationShape",
                "showDuration", "showNormal", "showDelay", "showDistance"):
        fallback = (existing or {}).get(key, DEFAULTS[key])
        values[key] = str(payload.get(key, fallback)) or DEFAULTS[key]
    for variant in ("full", "compact"):
        for key, default in DEFAULTS.items():
            if key in ("originIcon", "originShape", "destinationIcon", "destinationShape",
                       "showDuration", "showNormal", "showDelay", "showDistance"):
                continue
            field = variant + key[0].upper() + key[1:]
            fallback = (existing or {}).get(field, (existing or {}).get(key, default))
            values[field] = str(payload.get(field, fallback))
    return values


def admin_page() -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HERE Traffic Dashboards</title><style>
body{max-width:940px;margin:0 auto;padding:28px;font:16px system-ui,sans-serif;background:#0f172a;color:#f8fafc}h1{margin-bottom:4px}p{color:#cbd5e1}section{margin:24px 0;padding:22px;border:1px solid #334155;border-radius:12px;background:#1e293b}form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}label{display:grid;gap:5px;color:#cbd5e1;font-size:.9rem}input,select,button{padding:10px;border-radius:7px;font:inherit}input,select{border:1px solid #64748b;background:#0f172a;color:white}button{border:0;background:#38bdf8;color:#082f49;font-weight:700;cursor:pointer}.wide{grid-column:1/-1}.row{display:block;border-top:1px solid #334155;padding:15px 0}.row:first-child{border:0}.row strong{font-size:1.05rem}.dash-top{display:flex;align-items:baseline;gap:12px;margin-bottom:8px}.dash-top small{color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.link-line{display:flex;align-items:center;gap:10px;margin:6px 0}.link-label{min-width:88px;color:#94a3b8;font-size:.84rem;flex-shrink:0}.link-url{flex:1;color:#7dd3fc;font-size:.86rem;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.link-url:hover{text-decoration:underline}.copy{flex-shrink:0;background:#334155;color:#e2e8f0;padding:6px 12px;font-size:.9rem;cursor:pointer;border-radius:6px;border:0}.copy:hover{background:#475569}.dash-actions{display:flex;gap:10px;margin-top:10px}.dash-actions button{padding:8px 18px}.secondary{background:#334155;color:#fff}.danger{background:#b91c1c;color:#fff}code{padding:2px 5px;background:#0f172a;border-radius:4px}@media(max-width:600px){form{grid-template-columns:1fr}#editor [data-variant]{grid-template-columns:1fr}.row strong{min-width:100%}}.modal-overlay{position:fixed;inset:0;z-index:100;display:grid;justify-items:center;align-items:start;padding:20px;background:rgba(3,7,18,.85);overflow-y:auto}.modal-overlay[hidden]{display:none}.modal-content{width:min(100%,680px);max-height:calc(100vh-40px);overflow:auto;padding:24px;border:1px solid #475569;border-radius:14px;background:#1e293b;box-shadow:0 20px 60px rgba(0,0,0,.4)}.toast{position:fixed;top:24px;left:50%;transform:translateX(-50%);z-index:200;display:flex;align-items:center;gap:10px;padding:14px 24px;border-radius:10px;background:#166534;color:#bbf7d0;font-weight:700;font-size:1.05rem;box-shadow:0 8px 30px rgba(0,0,0,.5);animation:toast-in .3s ease-out,toast-out .3s .9s ease-in forwards}.toast .checkmark{font-size:1.3rem}@keyframes toast-in{from{opacity:0;transform:translateX(-50%) translateY(-12px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}@keyframes toast-out{from{opacity:1}to{opacity:0;transform:translateX(-50%) translateY(-12px)}}.wide-button{display:inline-block;padding:12px 24px;border:2px dashed #64748b;border-radius:10px;background:transparent;color:#38bdf8;font:inherit;font-weight:700;cursor:pointer;width:auto}.new-buttons{display:flex;gap:12px;flex-wrap:wrap}.new-buttons .wide-button{flex:1}
#editor[data-variant="full"] [data-variant="compact"]{display:none}
#editor[data-variant="compact"] [data-variant="full"]{display:none}#editor [data-variant]{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.modal-buttons{display:flex;gap:10px;grid-column:1/-1}
.field-label{font-weight:600}.tile-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.tile-control{display:grid;gap:6px;background:#0f172a;border:1px solid #334155;border-radius:9px;padding:10px}.tile-show{display:flex;align-items:center;gap:8px;font-size:.88rem;color:#e2e8f0}.tile-show input{width:auto;margin:0;accent-color:#38bdf8}.tile-control select{margin:0}.pick-field{display:grid;gap:6px;margin:2px 0 8px}.icon-grid{display:flex;gap:6px;flex-wrap:wrap}.icon-choice{width:44px;height:44px;display:grid;place-items:center;background:#0f172a;border:1px solid #64748b;border-radius:9px;color:#cbd5e1;cursor:pointer;padding:0}.icon-choice svg{width:22px;height:22px}.icon-choice:hover{border-color:#94a3b8}.icon-choice.selected{background:#38bdf8;border-color:#38bdf8;color:#082f49}.shape-row{display:flex;gap:6px;flex-wrap:wrap}.shape-choice{background:#0f172a;border:1px solid #64748b;border-radius:7px;color:#cbd5e1;font:inherit;font-size:.86rem;padding:7px 13px;cursor:pointer}.shape-choice:hover{border-color:#94a3b8}.shape-choice.selected{background:#38bdf8;border-color:#38bdf8;color:#082f49;font-weight:600}.pick{grid-column:1/-1;margin:2px 0 6px}.pick-head{display:flex;align-items:center;gap:8px;background:#0f172a;border:1px solid #64748b;border-radius:9px;padding:11px 14px;color:#cbd5e1;font:inherit;font-size:.92rem;cursor:pointer;width:100%;text-align:left}.pick-head b{color:#f8fafc}.pick-head .chev{margin-left:auto;transition:transform .2s}.pick.open .chev{transform:rotate(180deg)}.pick-body{display:none;margin-top:10px;padding:12px;border:1px solid #334155;border-radius:10px;background:#0b1222}.pick.open .pick-body{display:block}.pick-tabs{display:flex;gap:8px;margin-bottom:10px}.pick-tabs button{background:#334155;color:#e2e8f0;font:inherit;font-size:.88rem;padding:7px 14px;border-radius:7px;cursor:pointer}.pick-tabs button[aria-selected="true"]{background:#38bdf8;color:#082f49;font-weight:700}.pick-search{display:flex;gap:8px}.pick-search input{flex:1}.pick-search button{padding:10px 16px}.pick-results{margin:10px 0 0;padding:0;list-style:none;display:grid;gap:6px;max-height:180px;overflow:auto}.pick-results button{display:block;width:100%;text-align:left;background:#0f172a;border:1px solid #334155;color:#e2e8f0;font:inherit;font-size:.88rem;padding:9px 12px;border-radius:8px;cursor:pointer}.pick-results button:hover{border-color:#38bdf8}.pick-results .sub{display:block;color:#94a3b8;font-size:.8rem}.pick-status{margin:10px 0 0;color:#94a3b8;font-size:.86rem}.pick-status.error{color:#fca5a5}.pick-map-wrap{position:relative;height:320px;border-radius:8px;overflow:hidden;border:1px solid #334155}.pick-hint{position:absolute;z-index:1000;top:10px;left:50%;transform:translateX(-50%);padding:6px 14px;border-radius:999px;background:rgba(15,23,42,.88);color:#cbd5e1;font-size:.8rem;pointer-events:none;white-space:nowrap}.pick-actions{display:flex;align-items:center;gap:10px;margin-top:10px}.pick-coords{flex:1;color:#94a3b8;font-size:.84rem;font-family:ui-monospace,monospace}.pick-actions .use{background:#38bdf8;color:#082f49;font-weight:700;padding:9px 16px;cursor:pointer;border:0;border-radius:7px;font:inherit}.pick-actions .use:disabled{opacity:.4;cursor:not-allowed}.leaflet-container{background:#0b1222;font:inherit}
.slider-field .slider-row{display:flex;align-items:center;gap:12px}.slider-field input[type=range]{flex:1;padding:0;border:0;background:transparent;accent-color:#38bdf8;height:24px}.slider-field output{min-width:26px;text-align:center;background:#0f172a;border:1px solid #334155;border-radius:6px;padding:4px 6px;font-size:.85rem;color:#e2e8f0}
.preview-actions{margin-top:14px;display:flex;align-items:center;gap:12px}.preview-btn{background:#38bdf8;color:#082f49;font-weight:700;padding:10px 20px;border-radius:8px;cursor:pointer;border:0;font:inherit}.preview-btn:hover{filter:brightness(1.1)}.preview-hint{color:#fca5a5;font-size:.86rem}.preview-overlay{position:fixed;inset:0;z-index:200;background:rgba(3,7,18,.88);display:grid;place-items:center;padding:24px}.preview-overlay[hidden]{display:none}.preview-frame-wrap{width:min(96vw,1400px);height:min(92vh,1000px);display:flex;flex-direction:column;background:#0f172a;border:1px solid #334155;border-radius:12px;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.5)}.preview-frame-bar{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;background:#1e293b;border-bottom:1px solid #334155;color:#e2e8f0}.preview-close{background:#334155;color:#e2e8f0;border:0;border-radius:7px;padding:7px 14px;font:inherit;cursor:pointer}.preview-close:hover{background:#475569}.preview-frame{flex:1;border:0;width:100%;background:#0b1222}</style><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" /><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script></head><body>
<h1>HERE Traffic Dashboards</h1><p>Set the shared HERE API key in this app's <strong>Configuration</strong> tab. Create named displays below; no device needs to enter the key.</p>
<section><h2>Dashboards</h2><div class="new-buttons"><button id="new-full" class="wide-button">＋ Add Full Screen Map</button><button id="new-compact" class="wide-button">＋ Add Card</button></div></section>
<section><h2>Your dashboard displays</h2><p>Use <em>Full screen</em> for a wall/tablet display and <em>Compact</em> for a dashboard iframe card. Ingress URLs work within Home Assistant; direct URLs require this app's port to be reachable on your LAN.</p><div id="list">Loading…</div></section>
<div id="editor-modal" class="modal-overlay" hidden><div class="modal-content"><h2 id="modal-title">New dashboard</h2><form id="editor"><input id="edit-id" type="hidden"><label>Name<input name="name" required placeholder="Morning commute"></label><label class="wide">Origin<input name="origin" required placeholder="Home"></label><div class="pick" id="pick-origin"><button type="button" class="pick-head"><span>📍 Choose <b>Origin</b> on a map</span><span class="chev">▾</span></button><div class="pick-body"><div class="pick-search"><input type="search" placeholder="Search a place or address…" aria-label="Search origin location"><button type="button">Search</button></div><ul class="pick-results"></ul><p class="pick-status" hidden></p><div class="pick-map-wrap"><div class="pick-hint">Tap the map to drop or move the pin</div><div class="pick-map" style="height:100%"></div></div><div class="pick-actions"><span class="pick-coords">No point selected</span><button type="button" class="use" disabled>Use this location</button></div></div></div><label class="wide">Destination<input name="destination" required placeholder="Office"></label><div class="pick" id="pick-destination"><button type="button" class="pick-head"><span>📍 Choose <b>Destination</b> on a map</span><span class="chev">▾</span></button><div class="pick-body"><div class="pick-search"><input type="search" placeholder="Search a place or address…" aria-label="Search destination location"><button type="button">Search</button></div><ul class="pick-results"></ul><p class="pick-status" hidden></p><div class="pick-map-wrap"><div class="pick-hint">Tap the map to drop or move the pin</div><div class="pick-map" style="height:100%"></div></div><div class="pick-actions"><span class="pick-coords">No point selected</span><button type="button" class="use" disabled>Use this location</button></div></div></div><h3 class="wide">Full-screen display</h3><label>Map appearance<select name="fullTheme"><option value="auto">Automatic (device setting)</option><option value="dark">Dark</option><option value="light">Light</option></select></label><label>Route outline colour<select name="fullScheme"><option value="ocean">Ocean blue</option><option value="emerald">Emerald green</option><option value="sunset">Sunset orange</option><option value="violet">Violet</option><option value="contrast">High contrast yellow</option></select></label><label>Map framing<select name="fullZoomOut"><option value="0.7">Normal</option><option value="1.2" selected>Spacious</option><option value="1.7">Extra spacious</option></select></label><label>Route width<select name="fullRouteWidth"><option value="8">Slim</option><option value="12" selected>Standard</option><option value="16">Wide</option><option value="22">Extra wide</option></select></label><label>Route border<select name="fullBorderWidth"><option value="4">Thin</option><option value="7" selected>Standard</option><option value="10">Thick</option></select></label><label>Green delay through (%)<input name="fullGreenThreshold" type="number" min="0" max="100" value="10"></label><label>Amber delay through (%)<input name="fullAmberThreshold" type="number" min="0" max="100" value="30"></label><label>Refresh interval<select name="fullRefreshInterval"><option value="0">Off</option><option value="1">Every minute</option><option value="5" selected>Every 5 minutes</option><option value="10">Every 10 minutes</option><option value="15">Every 15 minutes</option><option value="30">Every 30 minutes</option></select></label><h3 class="wide">Compact display</h3><label>Map appearance<select name="compactTheme"><option value="auto">Automatic (device setting)</option><option value="dark">Dark</option><option value="light">Light</option></select></label><label>Route outline colour<select name="compactScheme"><option value="ocean">Ocean blue</option><option value="emerald">Emerald green</option><option value="sunset">Sunset orange</option><option value="violet">Violet</option><option value="contrast">High contrast yellow</option></select></label><label>Map framing<select name="compactZoomOut"><option value="0.7">Normal</option><option value="1.2" selected>Spacious</option><option value="1.7">Extra spacious</option></select></label><label>Route width<select name="compactRouteWidth"><option value="8">Slim</option><option value="12" selected>Standard</option><option value="16">Wide</option><option value="22">Extra wide</option></select></label><label>Route border<select name="compactBorderWidth"><option value="4">Thin</option><option value="7" selected>Standard</option><option value="10">Thick</option></select></label><label>Green delay through (%)<input name="compactGreenThreshold" type="number" min="0" max="100" value="10"></label><label>Amber delay through (%)<input name="compactAmberThreshold" type="number" min="0" max="100" value="30"></label><label>Refresh interval<select name="compactRefreshInterval"><option value="0">Off</option><option value="1">Every minute</option><option value="5" selected>Every 5 minutes</option><option value="10">Every 10 minutes</option><option value="15">Every 15 minutes</option><option value="30">Every 30 minutes</option></select></label><div class="modal-buttons"><button type="submit">Save dashboard</button> <button class="secondary" id="cancel" type="button">Cancel</button></div></form></div></div>
<script>const f=document.querySelector('#editor'),list=document.querySelector('#list'),cancel=document.querySelector('#cancel'),modal=document.querySelector('#editor-modal'),modalTitle=document.querySelector('#modal-title'),newBtn=document.querySelector('#new-dashboard');let items=[];const base=location.pathname.replace(/\/$/,'');const route=p=>`${location.origin}${base}${p}`;async function request(path,options){const r=await fetch(route(path),options);const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data}
// Display links must be RELATIVE (no origin): through HA ingress the path
// contains a per-session token, so an absolute URL copied from one session
// (e.g. pasted into another user's browser or a kiosk) 401s for everyone else.
// "display/<id>" resolves against the ingress base automatically per session.
const displayLink=p=>`${base}/${p.replace(/^\//,'')}`;
// Direct (non-ingress) link with the shared access token, for kiosks and
// devices that don't have a Home Assistant session.
const ACCESS_TOKEN='__ACCESS_TOKEN__';
const directLink=p=>ACCESS_TOKEN?`${location.origin}${base}${p}?auth=${encodeURIComponent(ACCESS_TOKEN)}`:'';function field(name,value){const input=f.elements[name];if(input)input.value=value??''}function resetForm(){f.reset();field('edit-id','');modalTitle.textContent='New dashboard';for(const[w,k]of[['origin','Icon'],['origin','Shape'],['destination','Icon'],['destination','Shape']]){const el=f.elements[w+k];if(el)el.value=''}for(const which of['origin','destination'])if(typeof markerButtonState==='function')markerButtonState(which)}// Group each h3 section (and everything after it) into a data-variant wrapper
// so a single variant can be shown/hidden when creating a new dashboard.
function groupVariants(){
  const kids=[...f.children];let wrapper=null,variant='';
  for(const node of kids){
    if(node.tagName==='H3'){
      variant=node.textContent.toLowerCase().includes('compact')?'compact':'full';
      wrapper=document.createElement('div');wrapper.dataset.variant=variant;
      node.before(wrapper);
    }
    if(node.classList.contains('modal-buttons')){wrapper=null;}
    if(wrapper){wrapper.append(node);}
  }
}
groupVariants();
function openModal(dashboard,variant){
  resetForm();
  if(dashboard){
    for(const[k,v]of Object.entries(dashboard))field(k,v);
    field('edit-id',dashboard.id);
    for(const which of ['origin','destination'])markerButtonState(which);
    for(const prefix of ['full','compact'])populateTileCorners(prefix);
    modalTitle.textContent=`Edit: ${dashboard.name}`;
    f.dataset.variant=dashboard.kind==='compact'?'compact':'full';
  }else{
    for(const prefix of ['full','compact'])populateTileCorners(prefix);
    f.dataset.variant=variant||'';
    modalTitle.textContent=variant==='compact'?'New Card':'New Full Screen Map';
  }
  modal.hidden=false;
}function closeModal(){modal.hidden=true;resetForm()}function showToast(message){const toast=document.createElement('div');toast.className='toast';toast.innerHTML=`<span class="checkmark">✓</span>${message}`;document.body.append(toast);setTimeout(()=>toast.remove(),1300)}function render(){list.innerHTML=items.length?'': '<p>No dashboards yet.</p>';for(const d of items){const full=displayLink(`/display/${d.id}`),compact=displayLink(`/card/${d.id}`);const row=document.createElement('div');row.className='row';row.innerHTML=`<div class="dash-top"><strong>${d.name}</strong><small>${d.kind==='compact'?'Card':'Full screen'}</small></div>${d.kind==='compact'
? `<div class="link-line"><span class="link-label">Compact</span><a class="link-url" href="${compact}" target="_blank" rel="noopener">${compact}</a><button class="copy" type="button" data-copy="${compact}" title="Copy link">⧉</button></div>${directLink(`/card/${d.id}`)?`<div class="link-line"><span class="link-label">Direct</span><a class="link-url" href="${directLink(`/card/${d.id}`)}" target="_blank" rel="noopener">${directLink(`/card/${d.id}`)}</a><button class="copy" type="button" data-copy="${directLink(`/card/${d.id}`)}" title="Copy direct link (token-authenticated, for kiosks)">⧉</button></div>`:''}`
: `<div class="link-line"><span class="link-label">Full screen</span><a class="link-url" href="${full}" target="_blank" rel="noopener">${full}</a><button class="copy" type="button" data-copy="${full}" title="Copy link">⧉</button></div>${directLink(`/display/${d.id}`)?`<div class="link-line"><span class="link-label">Direct</span><a class="link-url" href="${directLink(`/display/${d.id}`)}" target="_blank" rel="noopener">${directLink(`/display/${d.id}`)}</a><button class="copy" type="button" data-copy="${directLink(`/display/${d.id}`)}" title="Copy direct link (token-authenticated, for kiosks)">⧉</button></div>`:''}`}<div class="dash-actions"><button class="secondary">Edit</button><button class="danger">Delete</button></div>`;row.querySelector('.secondary').onclick=()=>openModal(d);const delBtn=row.querySelector('.danger');delBtn.onclick=async()=>{// Native confirm() is silently blocked inside HA's sandboxed iframe — use a two-tap confirmation instead.
if(delBtn.dataset.armed){delBtn.disabled=true;try{await request(`/api/dashboards/${d.id}`,{method:'DELETE'});showToast('Deleted');}catch(e){showToast(e.message);delBtn.disabled=false;delBtn.dataset.armed='';delBtn.textContent='Delete';return}load()}else{delBtn.dataset.armed='1';delBtn.textContent='Really delete?';setTimeout(()=>{if(delBtn.isConnected&&delBtn.dataset.armed){delBtn.dataset.armed='';delBtn.textContent='Delete'}},3000)}};for(const btn of row.querySelectorAll('.copy'))btn.onclick=async()=>{const url=btn.dataset.copy;try{await navigator.clipboard.writeText(url)}catch(e){const ta=document.createElement('textarea');ta.value=url;document.body.append(ta);ta.select();document.execCommand('copy');ta.remove()}btn.textContent='✓';setTimeout(()=>btn.textContent='⧉',1200)};list.append(row)}}async function load(){items=await request('/api/dashboards');render()}f.onsubmit=async e=>{e.preventDefault();const id=f.elements['edit-id'].value;const data=Object.fromEntries(new FormData(f));if(!id&&f.dataset.variant)data.kind=f.dataset.variant;const path=id?`/api/dashboards/${id}`:'/api/dashboards';await request(path,{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});showToast(id?'Saved':'Created');closeModal();load()};cancel.onclick=closeModal;document.querySelector('#new-full').onclick=()=>openModal(null,'full');document.querySelector('#new-compact').onclick=()=>openModal(null,'compact');modal.addEventListener('click',e=>{if(e.target===modal)closeModal()});
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
const slider=(name,text,min,max,step,selected,scale)=>{scale=scale||{};return `<label class="slider-field">${label(name,text)}<span class="slider-row"><input type="range" name="${name}" min="${min}" max="${max}" step="${step}" value="${scale[selected]??selected}"><output>${scale[selected]??selected}</output></span></label>`};
const options={
 position:[['top','Top middle'],['bottom','Bottom middle']],
 background:[['rounded','Rounded background'],['none','No background']],
 font:[['system','System sans'],['serif','Serif'],['mono','Monospace']],
 cardStyle:[['rounded','Rounded cards'],['vignette','Corner vignette']],
 vignettePosition:[['all','All around'],['top','Top edge'],['bottom','Bottom edge'],['left','Left edge'],['right','Right edge'],['tl','Top-left corner'],['tr','Top-right corner'],['bl','Bottom-left corner'],['br','Bottom-right corner']],
 markerIcon:[['home','Home'],['flag','Flag'],['briefcase','Work'],['car','Car'],['star','Star'],['heart','Heart'],['plus','Hospital'],['cart','Shopping'],['pin','Map pin'],['bolt','Charge point'],['school','School'],['train','Station']],
 markerShape:[['circle','Circle'],['square','Square'],['rounded','Rounded square'],['pin','Teardrop pin']]
};
const markerIconPicker=(which,text)=>`<div class="pick-field wide"><span class="field-label">${text}</span><div class="icon-grid" data-which="${which}">${options.markerIcon.map(([value,iconLabel])=>`<button type="button" class="icon-choice" data-value="${value}" title="${iconLabel}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[value]||ICONS.pin}</svg></button>`).join('')}</div></div>`;
const markerShapePicker=(which,text)=>`<div class="pick-field wide"><span class="field-label">${text}</span><div class="shape-row" data-which="${which}">${options.markerShape.map(([value,shapeLabel])=>`<button type="button" class="shape-choice" data-value="${value}">${shapeLabel}</button>`).join('')}</div></div>`;
const ICONS={
 home:'<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
 flag:'<path d="M5 21V4"/><path d="M5 4h13l-2.5 4L18 12H5"/>',
 briefcase:'<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/><path d="M3 13h18"/>',
 car:'<path d="M5 16l1.5-5.5A2 2 0 0 1 8.4 9h7.2a2 2 0 0 1 1.9 1.5L19 16"/><rect x="3" y="16" width="18" height="4" rx="1.5"/><circle cx="7.5" cy="20" r="1"/><circle cx="16.5" cy="20" r="1"/>',
 star:'<path d="M12 3l2.7 5.7 6.3.8-4.6 4.3 1.2 6.2L12 17l-5.6 3 1.2-6.2L3 9.5l6.3-.8z"/>',
 heart:'<path d="M12 21C7 16.5 3 13.3 3 9.3 3 6.4 5.2 4 8 4c1.6 0 3.1.8 4 2 0.9-1.2 2.4-2 4-2 2.8 0 5 2.4 5 5.3 0 4-4 7.2-9 11.7z"/>',
 plus:'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M12 8v8M8 12h8"/>',
 cart:'<circle cx="9" cy="20" r="1.5"/><circle cx="17" cy="20" r="1.5"/><path d="M3 4h2l2.5 11h10L20 8H6"/>',
 pin:'<path d="M12 21s-7-6.1-7-11a7 7 0 0 1 14 0c0 4.9-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
 bolt:'<path d="M13 2 4 14h6l-1 8 9-12h-6z"/>',
 school:'<path d="M12 3 2 8l10 5 10-5z"/><path d="M6 10.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-5.5"/>',
 train:'<rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 11h14"/><circle cx="9" cy="14.5" r=".8"/><circle cx="15" cy="14.5" r=".8"/><path d="M8 20l-1.5 2M16 20l1.5 2"/>'
};
const sizeMap={small:3,medium:5,large:7};
const TILE_DEFS=[['Duration','Trip time'],['Normal','Normal time'],['Delay','Traffic delay'],['Distance','Distance']];
const previewButton=(prefix,heading)=>`<div class="preview-actions wide"><button type="button" class="preview-btn" data-previewbtn="${prefix}">▶ ${heading} preview</button><span class="preview-hint" data-previewhint="${prefix}" hidden></span></div>`;
// Defaults: top left = normal time, top right = distance, bottom left = trip time, bottom right = traffic delay.
const TILE_DEFAULT_POS={Duration:'bl',Normal:'tl',Delay:'br',Distance:'tr'};
const CORNERS=[['tl','Top left'],['tr','Top right'],['bl','Bottom left'],['br','Bottom right']];
for(const [prefix,heading] of [['full','Full-screen presentation'],['compact','Compact presentation']]){
  const anchor=[...editor.querySelectorAll('h3')].find(node=>node.textContent.startsWith(prefix==='full'?'Full':'Compact'));
  anchor.insertAdjacentHTML('afterend', `<h4 class="wide">${heading}</h4>${input(prefix+'Title','Optional title','e.g. Morning commute')}${select(prefix+'TitlePosition','Title position',options.position,'top')}${slider(prefix+'TitleSize','Title size',1,10,1,'medium',sizeMap)}${select(prefix+'TitleBackground','Title background',options.background,'rounded')}${select(prefix+'TitleFont','Title font',options.font,'system')}${slider(prefix+'MetricSize','Card size',1,10,1,'large',sizeMap)}${select(prefix+'MetricStyle','Card style',options.cardStyle,'rounded')}${select(prefix+'VignettePosition','Vignette position',options.vignettePosition,'all')}${slider(prefix+'VignetteOpacity','Vignette opacity',1,10,1,'5',null)}${slider(prefix+'VignetteSize','Vignette size',1,10,1,'5',null)}${tileControls(prefix)}${previewButton(prefix,prefix==='full'?'Full screen':'Compact card')}`);
}
// Per-corner tile pickers: checkbox enables the corner, select chooses its tile.
function tileControls(prefix){
  const corners=CORNERS.map(([value,cLabel])=>`<div class="tile-control"><label class="tile-show"><input type="checkbox" data-cornercheck="${prefix}${value}" checked> ${cLabel}</label><select data-corner="${prefix}${value}"><option value="">—</option>${TILE_DEFS.map(([key,label])=>`<option value="${key}">${label}</option>`).join('')}</select></div>`).join('');
  return `<div class="tile-grid wide">${corners}</div>`;
}
// Shared marker settings: hidden inputs hold the values; visible pickers toggle them.
const markerSection=document.createElement('div');
markerSection.innerHTML=`<h3 class="wide">Route markers</h3>${markerShapePicker('origin','Origin marker shape')}${markerIconPicker('origin','Origin marker icon')}${markerShapePicker('destination','Destination marker shape')}${markerIconPicker('destination','Destination marker icon')}`;
const h3Full=[...editor.querySelectorAll('h3')].find(node=>node.textContent==='Full-screen display');
h3Full.parentNode.insertBefore(markerSection,h3Full);
for(const which of ['origin','destination']){
  for(const kind of ['Icon','Shape']){
    const hidden=document.createElement('input');
    hidden.type='hidden';hidden.name=which+kind;hidden.value='';
    editor.appendChild(hidden);
  }
}
// Tile show/hide checkboxes + corner pickers -> hidden inputs named <prefix>Show<Key> / <prefix>Tile<Key>
function tileCornerSelects(prefix){return [...editor.querySelectorAll(`select[data-corner^="${prefix}"]`)];}
function syncTileHidden(prefix){
  const selects=tileCornerSelects(prefix);
  const used=new Set(selects.filter(s=>s.value).map(s=>s.dataset.corner.slice(prefix.length)));
  // Assigned tiles: position = their corner, visible = corner checkbox checked.
  for(const sel of selects){
    if(!sel.value)continue;
    const corner=sel.dataset.corner.slice(prefix.length);
    editor.elements[prefix+'Tile'+sel.value].value=corner;
    editor.elements[prefix+'Show'+sel.value].value=editor.querySelector(`[data-cornercheck="${prefix}${corner}"]`).checked?'true':'false';
  }
  // Unassigned tiles: hidden, parked on a free corner for their position value.
  for(const [key] of TILE_DEFS){
    const sel=selects.find(s=>s.value===key);
    if(sel)continue;
    editor.elements[prefix+'Show'+key].value='false';
    const fallback=[TILE_DEFAULT_POS[key],...CORNERS.map(c=>c[0])].find(c=>!used.has(c));
    if(fallback){editor.elements[prefix+'Tile'+key].value=fallback;used.add(fallback);}
  }
}
function populateTileCorners(prefix){
  for(const [key] of TILE_DEFS){
    const value=editor.elements[prefix+'Tile'+key]?.value||TILE_DEFAULT_POS[key];
    const sel=tileCornerSelects(prefix).find(s=>s.dataset.corner===prefix+value);
    if(sel)sel.value=key;
  }
  // Corner checkbox reflects whether the tile assigned to it is shown.
  for(const sel of tileCornerSelects(prefix)){
    const corner=sel.dataset.corner.slice(prefix.length);
    const key=sel.value;
    const check=editor.querySelector(`[data-cornercheck="${prefix}${corner}"]`);
    check.checked=key?editor.elements[prefix+'Show'+key].value!=='false':true;
  }
  syncTileHidden(prefix);
}
for(const prefix of ['full','compact']){
  for(const [key] of TILE_DEFS){
    for(const [name,value] of [[prefix+'Show'+key,'true'],[prefix+'Tile'+key,TILE_DEFAULT_POS[key]]]){
      const hidden=document.createElement('input');
      hidden.type='hidden';hidden.name=name;hidden.value=value;
      editor.appendChild(hidden);
    }
  }
  for(const sel of tileCornerSelects(prefix)){
    const corner=sel.dataset.corner.slice(prefix.length);
    const check=editor.querySelector(`[data-cornercheck="${prefix}${corner}"]`);
    check.addEventListener('change',()=>syncTileHidden(prefix));
    sel.addEventListener('change',()=>{
      if(sel.value){for(const other of tileCornerSelects(prefix))if(other!==sel&&other.value===sel.value)other.value='';}
      syncTileHidden(prefix);
    });
  }
  syncTileHidden(prefix);
}
function markerButtonState(which){
  const hidden=n=>editor.elements[which+n];
  for(const btn of editor.querySelectorAll(`.icon-grid[data-which="${which}"] .icon-choice`))btn.classList.toggle('selected',btn.dataset.value===hidden('Icon').value);
  for(const btn of editor.querySelectorAll(`.shape-row[data-which="${which}"] .shape-choice`))btn.classList.toggle('selected',btn.dataset.value===hidden('Shape').value);
}
for(const which of ['origin','destination']){
  editor.querySelectorAll(`.icon-grid[data-which="${which}"] .icon-choice`).forEach(btn=>btn.onclick=()=>{editor.elements[which+'Icon'].value=btn.dataset.value;markerButtonState(which)});
  editor.querySelectorAll(`.shape-row[data-which="${which}"] .shape-choice`).forEach(btn=>btn.onclick=()=>{editor.elements[which+'Shape'].value=btn.dataset.value;markerButtonState(which)});
}
// Slider value readouts
for(const sliderEl of editor.querySelectorAll('input[type=range]')){
  const out=sliderEl.closest('.slider-row').querySelector('output');
  sliderEl.addEventListener('input',()=>out.textContent=sliderEl.value);
}
// Full live preview: render the real display page (map, route, tiles) from the current form values
// in a large overlay. POSTs the unsaved form to /api/preview and shows the result in an iframe.
const previewBase=location.pathname.replace(/\/$/,'');
const overlay=document.createElement('div');
overlay.className='preview-overlay';
overlay.hidden=true;
overlay.innerHTML=`<div class="preview-frame-wrap"><div class="preview-frame-bar"><strong data-previewtitle></strong><button type="button" class="preview-close">✕ Close</button></div><iframe class="preview-frame" title="Dashboard preview"></iframe></div>`;
document.body.append(overlay);
const previewFrame=overlay.querySelector('.preview-frame');
const openPreview=async prefix=>{
  const hint=editor.querySelector(`[data-previewhint="${prefix}"]`);
  const variant=prefix==='full'?'full':'compact';
  const data=Object.fromEntries(new FormData(f));
  data.previewVariant=variant;
  if(!data.name)data.name=variant==='compact'?'Preview card':'Preview full screen';
  if(!f.elements['origin'].value.trim()||!f.elements['destination'].value.trim()){
    hint.textContent='Set an origin and destination first.';hint.hidden=false;return;
  }
  hint.hidden=true;
  overlay.querySelector('[data-previewtitle]').textContent='Preview — current (unsaved) settings';
  overlay.hidden=false;
  previewFrame.srcdoc='<p style="font:16px system-ui;color:#94a3b8;padding:20px">Loading preview…</p>';
  try{
    const r=await fetch(previewBase+'/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    const payload=await r.json();
    if(!r.ok)throw Error(payload.error||'Preview failed');
    previewFrame.srcdoc=payload.html;
  }catch(err){
    overlay.hidden=true;
    hint.textContent=err.message;hint.hidden=false;
  }
};
overlay.addEventListener('click',e=>{if(e.target===overlay)overlay.hidden=true});
overlay.querySelector('.preview-close').onclick=()=>overlay.hidden=true;
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!overlay.hidden)overlay.hidden=true});
for(const prefix of ['full','compact']){
  editor.querySelector(`[data-previewbtn="${prefix}"]`).onclick=()=>openPreview(prefix);
}
</script>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(fmt % args, flush=True)

    def is_ingress(self) -> bool:
        """True when the request arrived through Home Assistant's ingress proxy
        (which already authenticated the user). Direct connections don't carry
        these headers."""
        return bool(self.headers.get("X-Hassio-Ingress") or self.headers.get("X-Forwarded-For") or self.headers.get("X-Forwarded-Host"))

    def authorized(self) -> bool:
        """Ingress requests pass (HA authenticated them); everything else needs
        the shared access token via ?auth=… (or the X-Access-Token header)."""
        if self.is_ingress(): return True
        expected = access_token()
        if not expected: return True  # token unavailable (e.g. dev box): fail open rather than lock the app
        supplied = parse_qs(urlparse(self.path).query).get("auth", [""])[0] or self.headers.get("X-Access-Token", "")
        return secrets.compare_digest(supplied, expected)

    def send_json(self, value: object, status: int = 200) -> None:
        data = json.dumps(value).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def send_html(self, value: str, status: int = 200) -> None:
        data = value.encode()
        # no-store: devices must always fetch the current display page, never a
        # cached one (a stale cached page is exactly what keeps some devices on
        # old, broken tile code after an update).
        self.send_response(status); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0")); return json.loads(self.rfile.read(length) or b"{}")

    def find(self, identifier: str) -> tuple[list[dict], int]:
        dashboards = load_dashboards()
        for index, dashboard in enumerate(dashboards):
            if dashboard["id"] == identifier: return dashboards, index
        raise KeyError("Dashboard not found.")

    def build_config(self, dashboard: dict, variant: str, compact: bool) -> dict:
        config = {**DEFAULTS, **dashboard, "apiKey": api_key()}
        for key, default in DEFAULTS.items():
            field = variant + key[0].upper() + key[1:]
            config[key] = dashboard.get(field, dashboard.get(key, default))
        if not config["apiKey"]: raise ValueError("Set the HERE API key in this app's Configuration tab first.")
        return config

    def render_display(self, config: dict, compact: bool) -> str:
        injected = json.dumps(config).replace("<", "\\u003c")
        flags = f"<script>window.HERE_TRAFFIC_CONFIG={injected};window.HERE_TRAFFIC_COMPACT={str(compact).lower()};</script>"
        return DISPLAY_FILE.read_text().replace("</head>", flags + "</head>", 1)

    def display(self, identifier: str, compact: bool) -> None:
        try:
            dashboards, index = self.find(identifier)
            variant = "compact" if compact else "full"
            self.send_html(self.render_display(self.build_config(dashboards[index], variant, compact), compact))
        except (KeyError, ValueError) as error:
            self.send_html(f"<h1>HERE Traffic Dashboard</h1><p>{error}</p>", 404)

    def preview(self) -> None:
        try:
            payload = self.payload()
            variant = "compact" if payload.get("previewVariant") == "compact" else "full"
            compact = variant == "compact"
            pseudo = clean_dashboard({**payload, "kind": variant})
            self.send_json({"html": self.render_display(self.build_config(pseudo, variant, compact), compact)})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

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
        if path == "/health": return self.send_json({"ok": True})
        if not self.authorized(): return self.send_json({"error": "Unauthorized — append ?auth=<access token> (see the add-on's admin page)."}, 401)
        if path == "/":
            token = access_token()
            page = admin_page().replace("__ACCESS_TOKEN__", token).replace("</body>", PRESENTATION_FIELDS + "</body>")
            return self.send_html(page)
        if path == "/api/dashboards": return self.send_json(load_dashboards())
        if path == "/api/geocode": return self.geocode()
        match = re.fullmatch(r"/(display|card)/([a-z0-9-]+)", path)
        if match: return self.display(match.group(2), match.group(1) == "card")
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        if not self.authorized(): return self.send_json({"error": "Unauthorized."}, 401)
        if urlparse(self.path).path.rstrip("/") == "/api/preview": return self.preview()
        if urlparse(self.path).path.rstrip("/") != "/api/dashboards": return self.send_json({"error": "Not found"}, 404)
        try:
            dashboards = load_dashboards(); item = clean_dashboard(self.payload())
            if any(d["id"] == item["id"] for d in dashboards): raise ValueError("A dashboard with this name already exists.")
            dashboards.append(item); save_dashboards(dashboards); self.send_json(item, HTTPStatus.CREATED)
        except (ValueError, json.JSONDecodeError) as error: self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def do_PUT(self) -> None:
        if not self.authorized(): return self.send_json({"error": "Unauthorized."}, 401)
        match = re.fullmatch(r"/api/dashboards/([a-z0-9-]+)", urlparse(self.path).path.rstrip("/"))
        if not match: return self.send_json({"error": "Not found"}, 404)
        try:
            dashboards, index = self.find(match.group(1)); dashboards[index] = clean_dashboard(self.payload(), dashboards[index]); save_dashboards(dashboards); self.send_json(dashboards[index])
        except (KeyError, ValueError, json.JSONDecodeError) as error: self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        if not self.authorized(): return self.send_json({"error": "Unauthorized."}, 401)
        match = re.fullmatch(r"/api/dashboards/([a-z0-9-]+)", urlparse(self.path).path.rstrip("/"))
        if not match: return self.send_json({"error": "Not found"}, 404)
        try:
            dashboards, index = self.find(match.group(1)); dashboards.pop(index); save_dashboards(dashboards); self.send_json({"ok": True})
        except KeyError as error: self.send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)


if __name__ == "__main__":
    print("Starting HERE Traffic Dashboards on port 8099", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
