import os
import time
import pandas as pd
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


def _download_with_retry(ticker, start, end, attempts=4):
    """Fetch from Yahoo with exponential backoff. yfinance is inconsistent
    when blocked - sometimes it returns an empty frame, sometimes it raises -
    so we handle both and back off between tries (2s, 4s, 8s)."""
    delay = 2
    last_problem = None
    for _ in range(attempts):
        try:
            raw = yf.download(ticker, start=start, end=end,
                              auto_adjust=True, progress=False)
            if not raw.empty:
                return raw
            last_problem = "empty response (likely rate-limited)"
        except Exception as e:
            last_problem = repr(e)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(
        f"Couldn't fetch {ticker} after {attempts} tries. "
        f"Last issue: {last_problem}. Wait a minute and rerun - "
        f"the cache means you only need this to succeed once."
    )


def get_benchmark_prices(ticker, start, end):
    """Return a Series of daily prices for `ticker`, indexed by date.
    Cached to disk so repeated runs don't re-hit (and get blocked by) Yahoo."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{ticker}.csv")

    # Pad the window: we need a trading day on/before the earliest date,
    # and through today for open positions later.
    start = pd.Timestamp(start) - pd.Timedelta(days=7)
    end = pd.Timestamp(end) + pd.Timedelta(days=1)

    # Reuse cache only if it already spans the window we need.
    if os.path.exists(cache_path):
        cached = pd.read_csv(cache_path, index_col=0, parse_dates=True)["close"]
        if cached.index.min() <= start and cached.index.max() >= end - pd.Timedelta(days=5):
            return cached

    # Cache miss - fetch from Yahoo. auto_adjust=True gives dividend/split-
    # adjusted closes, i.e. total return - the fair "what if I'd held QQQ".
    raw = _download_with_retry(ticker, start, end)

    close = raw["Close"]
    if isinstance(close, pd.DataFrame):   # some yfinance versions nest columns
        close = close.iloc[:, 0]
    close.name = "close"
    close.index = pd.to_datetime(close.index)
    close.index.name = "date"

    close.to_csv(cache_path)
    return close


def price_on(prices, when):
    """Benchmark price on a date, snapping to the most recent trading day
    at or before it. Returns NaN if `when` precedes the data."""
    return prices.asof(pd.Timestamp(when).normalize())


if __name__ == "__main__":
    prices = get_benchmark_prices("QQQ", "2025-05-01", "2026-05-20")
    print(f"Fetched {len(prices)} trading days")
    print(prices.head(3))
    print(prices.tail(3))
    print("\nQQQ close on your entry (2026-03-27):", price_on(prices, "2026-03-27"))
    print("QQQ close on your exit  (2026-05-19):", price_on(prices, "2026-05-19"))
