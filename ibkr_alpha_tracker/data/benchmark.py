import os
import time
import pandas as pd
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


def _download_with_retry(ticker, start, end, attempts=4):
    """Fetch from Yahoo with exponential backoff. yfinance is inconsistent
    when blocked - sometimes empty frame, sometimes raises - so handle both
    and back off between tries (2s, 4s, 8s)."""
    delay = 2
    last_problem = None
    for _ in range(attempts):
        try:
            # auto_adjust=False -> 'Close' is split-adjusted but NOT
            # dividend-adjusted (price return). This matches your own P&L, which
            # is price-only (from trade prices), so the comparison is symmetric -
            # neither side counts dividends. (Crediting dividends on both sides is
            # a faithful future upgrade once Cash Transactions are fetched.)
            raw = yf.download(ticker, start=start, end=end,
                              auto_adjust=False, progress=False)
            if not raw.empty:
                return raw
            last_problem = "empty response (likely rate-limited)"
        except Exception as e:
            last_problem = repr(e)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(
        f"Couldn't fetch {ticker} after {attempts} tries. Last issue: {last_problem}.")


def get_benchmark_prices(ticker, start, end, ttl_hours=6):
    """Return a Series of daily prices for `ticker`, indexed by date.

    Cache rules (so the dashboard stays current AND stays up):
      - reuse cache if it covers the window AND is younger than ttl_hours
      - otherwise try to refetch (picks up new closes for a live dashboard)
      - if the refetch fails but we have ANY cache, return the stale cache
        rather than break the page
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{ticker}.csv")

    start = pd.Timestamp(start) - pd.Timedelta(days=7)
    end = pd.Timestamp(end) + pd.Timedelta(days=1)

    cached = None
    if os.path.exists(cache_path):
        cached = pd.read_csv(cache_path, index_col=0, parse_dates=True)["close"]
        covers = (cached.index.min() <= start and
                  cached.index.max() >= end - pd.Timedelta(days=5))
        fresh = (time.time() - os.path.getmtime(cache_path)) < ttl_hours * 3600
        if covers and fresh:
            return cached

    # Need fresh data (no cache, doesn't cover the window, or TTL expired).
    try:
        raw = _download_with_retry(ticker, start, end)
    except RuntimeError:
        if cached is not None:
            return cached   # degrade to stale cache instead of crashing
        raise

    close = raw["Close"]
    if isinstance(close, pd.DataFrame):   # some yfinance versions nest columns
        close = close.iloc[:, 0]
    close.name = "close"
    close.index = pd.to_datetime(close.index)
    close.index.name = "date"
    close.to_csv(cache_path)
    return close


def price_on(prices, when):
    """Benchmark price on a date, snapping to the most recent trading day at
    or before it. Returns NaN if `when` precedes the data."""
    return prices.asof(pd.Timestamp(when).normalize())
