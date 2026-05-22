"""FastAPI backend. Thin wrapper over build_dashboard_payload, with an optional
HTTP Basic Auth gate (active whenever DASHBOARD_PASSWORD is set) so the tunneled
public URL stays private.

  GET  /api/dashboard?currency=usd   -> computed payload (cached per currency)
  GET  /api/benchmarks               -> current benchmarks.json
  POST /api/benchmarks               -> overwrite benchmarks.json, bust cache
  GET  /                             -> the website (web/index.html)

Run locally:  uvicorn app.server:app --reload
"""
import sys, os, json, time, secrets
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCHMARKS_PATH = os.path.join(ROOT, "benchmarks.json")
WEB_DIR = os.path.join(ROOT, "web")

# --- auth: enforced only when DASHBOARD_PASSWORD is set (so local dev stays
#     frictionless, but the tunneled public URL is gated). Set both env vars
#     before exposing the app to the internet. ---
DASH_USER = os.environ.get("DASHBOARD_USER", "admin")
DASH_PASS = os.environ.get("DASHBOARD_PASSWORD")
_basic = HTTPBasic(auto_error=False)


def require_auth(creds: HTTPBasicCredentials = Depends(_basic)):
    if not DASH_PASS:
        return  # no password configured -> auth disabled (local use only)
    unauthorized = HTTPException(401, "Authentication required",
                                 headers={"WWW-Authenticate": "Basic"})
    if creds is None:
        raise unauthorized
    ok_user = secrets.compare_digest(creds.username, DASH_USER)
    ok_pass = secrets.compare_digest(creds.password, DASH_PASS)
    if not (ok_user and ok_pass):
        raise unauthorized


# the auth dependency guards every routed endpoint
app = FastAPI(title="Alpha Tracker", dependencies=[Depends(require_auth)])

_cache = {}
_CACHE_TTL = 120


def _get_payload(currency, nocache=False):
    currency = currency.lower()
    if currency not in ("usd", "sgd"):
        raise HTTPException(400, "currency must be 'usd' or 'sgd'")
    now = time.time()
    hit = _cache.get(currency)
    if hit and not nocache and now - hit[0] < _CACHE_TTL:
        return hit[1]
    from app.dashboard import build_dashboard_payload
    try:
        payload = build_dashboard_payload(currency)
    except Exception as e:
        raise HTTPException(502, f"Pipeline failed: {type(e).__name__}: {e}")
    _cache[currency] = (now, payload)
    return payload


@app.get("/api/dashboard")
def dashboard(currency: str = "usd", refresh: bool = False):
    return JSONResponse(_get_payload(currency, nocache=refresh))


@app.get("/api/benchmarks")
def get_benchmarks():
    with open(BENCHMARKS_PATH) as f:
        return JSONResponse(json.load(f))


@app.post("/api/benchmarks")
def set_benchmarks(cfg: dict = Body(...)):
    if "map" not in cfg or "default" not in cfg:
        raise HTTPException(400, "config must include 'map' and 'default' keys")
    if not isinstance(cfg["map"], dict):
        raise HTTPException(400, "'map' must be an object of ticker -> [benchmarks]")
    with open(BENCHMARKS_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    _cache.clear()
    return {"status": "saved", "tickers": len(cfg["map"])}


@app.get("/")
def index():
    page = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(page):
        return FileResponse(page)
    return JSONResponse({"status": "backend running",
                         "note": "web/index.html not built yet"})


if os.path.isdir(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
