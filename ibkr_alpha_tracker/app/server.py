"""FastAPI backend. Thin wrapper over build_dashboard_payload:
  GET  /api/dashboard?currency=usd   -> computed payload (cached per currency)
  GET  /api/benchmarks               -> current benchmarks.json
  POST /api/benchmarks               -> overwrite benchmarks.json, bust cache
  GET  /                             -> the website (web/index.html)

Run locally:  uvicorn app.server:app --reload
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCHMARKS_PATH = os.path.join(ROOT, "benchmarks.json")
WEB_DIR = os.path.join(ROOT, "web")

app = FastAPI(title="Alpha Tracker")

# --- per-currency payload cache (the pipeline takes seconds; don't re-run it
#     on every page load or currency toggle). Short TTL keeps it "current".
_cache = {}
_CACHE_TTL = 120  # seconds


def _get_payload(currency, nocache=False):
    """Compute (or serve cached) dashboard payload for a currency."""
    currency = currency.lower()
    if currency not in ("usd", "sgd"):
        raise HTTPException(400, "currency must be 'usd' or 'sgd'")

    now = time.time()
    hit = _cache.get(currency)
    if hit and not nocache and now - hit[0] < _CACHE_TTL:
        return hit[1]

    # Lazy import so this module loads even when config/credentials are absent
    # (e.g. during tests or before deployment env vars are set).
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
    _cache.clear()   # benchmark change invalidates every cached payload
    return {"status": "saved", "tickers": len(cfg["map"])}


@app.get("/")
def index():
    page = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(page):
        return FileResponse(page)
    return JSONResponse({"status": "backend running",
                         "note": "web/index.html not built yet (Phase 4)"})


if os.path.isdir(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
