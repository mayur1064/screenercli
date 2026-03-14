"""HTTP scraper for screener.in with error handling and TTL caching."""

import time
import requests
from bs4 import BeautifulSoup
from cachetools import TTLCache, cached
from cachetools.keys import hashkey


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ScraperError(Exception):
    """Base scraper error."""


class CompanyNotFoundError(ScraperError):
    def __init__(self, symbol: str):
        super().__init__(
            f"Company '{symbol}' not found on screener.in. "
            "Check that the ticker symbol is correct."
        )
        self.symbol = symbol


class RateLimitError(ScraperError):
    def __init__(self, retry_after: int | None = None):
        msg = "Rate limited by screener.in (HTTP 429)."
        if retry_after:
            msg += f" Retry after {retry_after} seconds."
        super().__init__(msg)
        self.retry_after = retry_after


class ScraperTimeoutError(ScraperError):
    def __init__(self):
        super().__init__("Request to screener.in timed out.")


class ConsolidatedUnavailableError(ScraperError):
    def __init__(self, symbol: str):
        super().__init__(
            f"Consolidated view not available for '{symbol}'. "
            "Use --view standalone."
        )
        self.symbol = symbol


class StandaloneUnavailableError(ScraperError):
    def __init__(self, symbol: str):
        super().__init__(
            f"Standalone view not available for '{symbol}'. "
            "Use --view consolidated."
        )
        self.symbol = symbol


# ---------------------------------------------------------------------------
# HTTP headers — browser-like to avoid bot detection
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# TTL cache: max 32 entries, 5-minute expiry
_cache: TTLCache = TTLCache(maxsize=32, ttl=300)

def _build_url(symbol: str, view: str) -> str:
    # Standalone: https://www.screener.in/company/SYMBOL/
    # Consolidated: https://www.screener.in/company/SYMBOL/consolidated
    sym = symbol.upper()
    if view == "standalone":
        return f"https://www.screener.in/company/{sym}/"
    return f"https://www.screener.in/company/{sym}/consolidated"


def _do_fetch(symbol: str, view: str, timeout: int = 15) -> BeautifulSoup:
    """Single HTTP fetch with retry on 429."""
    url = _build_url(symbol, view)
    max_retries = 3
    delay = 2

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
        except requests.Timeout:
            raise ScraperTimeoutError()
        except requests.ConnectionError as exc:
            raise ScraperError(f"Connection error: {exc}") from exc

        if resp.status_code == 200:
            # screener.in redirects to the base URL when consolidated is absent.
            # A successful consolidated request whose final URL lacks /consolidated
            # means the server silently fell back to standalone.
            if view == "consolidated" and "/consolidated" not in resp.url:
                raise ConsolidatedUnavailableError(symbol)
            # If the base standalone URL somehow redirected to /consolidated
            # the company only has a consolidated view.
            if view == "standalone" and "/consolidated" in resp.url:
                raise StandaloneUnavailableError(symbol)
            return BeautifulSoup(resp.text, "lxml")

        if resp.status_code == 404:
            raise CompanyNotFoundError(symbol)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", delay))
            if attempt < max_retries - 1:
                time.sleep(retry_after)
                delay *= 2
                continue
            raise RateLimitError(retry_after)

        resp.raise_for_status()

    raise ScraperError("Unexpected failure after retries.")


def fetch_page(symbol: str, view: str = "consolidated", no_cache: bool = False) -> BeautifulSoup:
    """
    Fetch and parse the screener.in company page.

    Parameters
    ----------
    symbol:   Stock ticker, e.g. ``"RELIANCE"``.
    view:     ``"consolidated"`` (default) or ``"standalone"``.
    no_cache: If True, bypass the in-memory TTL cache.

    Returns
    -------
    A ``BeautifulSoup`` object of the full page.
    """
    key = hashkey(symbol.upper(), view)
    if not no_cache and key in _cache:
        return _cache[key]

    soup = _do_fetch(symbol, view)
    if not no_cache:
        _cache[key] = soup
    return soup


def fetch_page_with_fallback(
    symbol: str,
    view: str = "consolidated",
    no_cache: bool = False,
) -> tuple[BeautifulSoup, str]:
    """
    Like ``fetch_page`` but automatically falls back to ``standalone``
    when the consolidated view is unavailable.

    Returns
    -------
    ``(soup, actual_view)`` where ``actual_view`` is the view that was used.
    """
    import sys

    try:
        soup = fetch_page(symbol, view, no_cache)
        return soup, view
    except ConsolidatedUnavailableError:
        print(
            f"[warning] Consolidated view not available for {symbol!r}; "
            "falling back to standalone.",
            file=sys.stderr,
        )
        soup = fetch_page(symbol, "standalone", no_cache)
        return soup, "standalone"
    except StandaloneUnavailableError:
        print(
            f"[warning] Standalone view not available for {symbol!r}; "
            "falling back to consolidated.",
            file=sys.stderr,
        )
        soup = fetch_page(symbol, "consolidated", no_cache)
        return soup, "consolidated"


# ---------------------------------------------------------------------------
# Peers fragment fetch  (separate AJAX endpoint)
# ---------------------------------------------------------------------------

_peers_cache: TTLCache = TTLCache(maxsize=32, ttl=300)

PEERS_API_URL = "https://www.screener.in/api/company/{warehouse_id}/peers/"


def fetch_peers_fragment(
    warehouse_id: str,
    symbol: str,
    view: str,
    no_cache: bool = False,
) -> BeautifulSoup:
    """
    Fetch the peers HTML fragment from the screener.in AJAX API.

    Parameters
    ----------
    warehouse_id: The numeric warehouseId from ``#company-info[data-warehouse-id]``.
    symbol:       Ticker (used only for the Referer header and error messages).
    view:         ``"consolidated"`` or ``"standalone"`` (for Referer header).
    no_cache:     Bypass the TTL cache when True.

    Returns
    -------
    A ``BeautifulSoup`` of the returned HTML fragment.
    """
    key = hashkey("peers", warehouse_id)
    if not no_cache and key in _peers_cache:
        return _peers_cache[key]

    url = PEERS_API_URL.format(warehouse_id=warehouse_id)
    referer = f"https://www.screener.in/company/{symbol.upper()}/{view}/"
    peer_headers = {**HEADERS, "Referer": referer, "X-Requested-With": "XMLHttpRequest"}

    max_retries = 3
    delay = 2
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=peer_headers, timeout=15)
        except requests.Timeout:
            raise ScraperTimeoutError()
        except requests.ConnectionError as exc:
            raise ScraperError(f"Connection error fetching peers: {exc}") from exc

        if resp.status_code == 200:
            fragment = BeautifulSoup(resp.text, "lxml")
            if not no_cache:
                _peers_cache[key] = fragment
            return fragment

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", delay))
            if attempt < max_retries - 1:
                time.sleep(retry_after)
                delay *= 2
                continue
            raise RateLimitError(retry_after)

        resp.raise_for_status()

    raise ScraperError("Unexpected failure after retries fetching peers.")
