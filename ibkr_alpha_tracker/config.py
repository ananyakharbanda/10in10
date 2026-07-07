import os


def _require(name):
    """Read a required secret from the environment. Fail loudly if missing so we
    never fall back to a hardcoded credential in source (which would leak if the
    file were ever committed)."""
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            f"Set it locally (export {name}=...) or in the Render dashboard "
            f"(Environment tab) before starting the app."
        )
    return val


# Secret: must come from the environment.
IBKR_TOKEN = _require("IBKR_TOKEN")

# Non-secret query identifiers: overridable via env, with sensible defaults.
TRADES_QUERY_ID = int(os.environ.get("TRADES_QUERY_ID", "1514323"))
POSITIONS_QUERY_ID = int(os.environ.get("POSITIONS_QUERY_ID", "1514326"))
