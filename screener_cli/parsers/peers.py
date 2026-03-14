"""Parser for the Peer Comparison section.

Strategy
--------
The peer table is **not** embedded in the main page HTML — it is loaded
dynamically via a second AJAX request to::

    GET /api/company/{warehouseId}/peers/

The ``warehouseId`` is stored in ``#company-info[data-warehouse-id]`` on the
main page.  ``parse()`` performs both steps automatically.
"""

from __future__ import annotations

import sys

from bs4 import BeautifulSoup, Tag

from ..models import PeerComparisonData, PeerData
from ..scraper import fetch_peers_fragment
from .utils import _clean_value

SECTION_ID = "peers"


# ---------------------------------------------------------------------------
# Helpers — main page (industry breadcrumb, indices, warehouseId)
# ---------------------------------------------------------------------------

def _extract_warehouse_id(soup: BeautifulSoup) -> str | None:
    """Return the numeric warehouseId from ``#company-info[data-warehouse-id]``."""
    tag = soup.find(id="company-info")
    if tag:
        return tag.get("data-warehouse-id")  # type: ignore[return-value]
    return None


def _extract_industry_breadcrumb(section: Tag) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Extract the 4-level industry hierarchy from ``<a href="/market/…">`` links
    inside the ``#peers`` section.
    """
    levels: list[str] = []
    p = section.find("p", class_="sub")
    if p:
        for a in p.find_all("a", href=lambda h: h and "/market/" in h):
            text = a.get_text(strip=True)
            if text:
                levels.append(text)

    levels += [None] * 4  # type: ignore[arg-type]
    return tuple(levels[:4])  # type: ignore[return-value]


def _extract_indices(section: Tag) -> list[str]:
    """
    Extract market-index memberships from ``#benchmarks a`` tags
    that are *not* hidden (class "hidden").
    """
    benchmarks = section.find(id="benchmarks")
    if not benchmarks:
        return []
    return [
        a.get_text(strip=True)
        for a in benchmarks.find_all("a")
        if "hidden" not in a.get("class", []) and a.get_text(strip=True)
    ]


# ---------------------------------------------------------------------------
# Helper — peers fragment (the AJAX response)
# ---------------------------------------------------------------------------

def _parse_peers_fragment(fragment: BeautifulSoup) -> tuple[list[str], list[PeerData]]:
    """
    Parse the HTML fragment returned by ``/api/company/{warehouseId}/peers/``.

    The fragment contains a ``<table>`` whose **first** ``<tr>`` (inside
    ``<tbody>``) holds ``<th>`` column headers; all subsequent rows are data.

    Returns ``(columns, peers)`` where *columns* excludes the "S.No." header.
    """
    table: Tag | None = fragment.find("table")  # type: ignore[assignment]
    if table is None:
        print("[warning] Peers API returned no table.", file=sys.stderr)
        return [], []

    tbody = table.find("tbody") or table
    all_rows = tbody.find_all("tr")
    if not all_rows:
        return [], []

    # --- header row: first <tr> contains <th> elements ---
    header_row = all_rows[0]
    raw_headers: list[str] = []
    tooltips: list[str] = []
    for th in header_row.find_all("th"):
        # Combine main text + unit span, e.g. "CMP Rs." / "P/E" / "Mar Cap Rs.Cr."
        parts = [t.strip() for t in th.stripped_strings]
        label = " ".join(parts).strip()
        raw_headers.append(label)
        tooltips.append(th.get("data-tooltip", "").strip())

    # Drop "S.No." (index 0); keep "Name" + metric columns
    display_columns = raw_headers[1:] if raw_headers else []
    metric_columns = display_columns[1:]  # everything after "Name"

    # --- data rows ---
    peers: list[PeerData] = []
    for tr in all_rows[1:]:
        cells = tr.find_all(["th", "td"])
        if len(cells) < 2:
            continue

        # Rank from first cell
        rank_text = cells[0].get_text(strip=True).rstrip(".")
        try:
            rank = int(rank_text)
        except ValueError:
            rank = None

        # Name + URL from second cell
        name_cell = cells[1]
        name = name_cell.get_text(strip=True)
        if not name:
            continue
        link = name_cell.find("a")
        url: str | None = link["href"] if link and link.get("href") else None

        # Metric values
        metric_cells = cells[2:]
        values: dict[str, float | None] = {}
        for col, cell in zip(metric_columns, metric_cells):
            values[col] = _clean_value(cell.get_text(strip=True))

        peers.append(PeerData(rank=rank, name=name, url=url, values=values))

    return display_columns, peers


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(soup: BeautifulSoup, no_cache: bool = False) -> PeerComparisonData | None:
    """
    Parse the Peer Comparison section.

    1. Locates ``#company-info[data-warehouse-id]`` in *soup* to get the
       warehouse ID.
    2. Fetches the AJAX peer fragment from
       ``/api/company/{warehouseId}/peers/``.
    3. Parses the returned HTML fragment for column headers and peer rows.
    4. Also extracts the industry breadcrumb and index memberships from the
       main page ``#peers`` section.

    Returns ``None`` (with a stderr warning) if the warehouse ID is missing
    or the peers section is absent.
    """
    warehouse_id = _extract_warehouse_id(soup)
    if not warehouse_id:
        print("[warning] Could not find warehouseId (data-warehouse-id) on this page.", file=sys.stderr)
        return None

    # Industry breadcrumb + indices come from the static #peers section
    section: Tag | None = soup.find("section", id=SECTION_ID)  # type: ignore[assignment]
    if section is None:
        print(f"[warning] Section '{SECTION_ID}' not found on this page.", file=sys.stderr)
        return None

    sector, industry, sub_industry, sub_sub = _extract_industry_breadcrumb(section)
    indices = _extract_indices(section)

    # Extract symbol + view from #company-info for the Referer header
    company_info = soup.find(id="company-info")
    is_consolidated = (company_info.get("data-consolidated", "false") == "true") if company_info else False
    view = "consolidated" if is_consolidated else "standalone"

    # The URL path gives us the symbol
    canonical_link = soup.find("link", rel="canonical")
    symbol = "UNKNOWN"
    if canonical_link and canonical_link.get("href"):
        # e.g. https://www.screener.in/company/HDFCBANK/consolidated/
        parts = canonical_link["href"].rstrip("/").split("/")
        if len(parts) >= 2:
            symbol = parts[-2] if parts[-1] in ("consolidated", "standalone") else parts[-1]

    # Fetch + parse the AJAX peers fragment
    try:
        fragment = fetch_peers_fragment(warehouse_id, symbol, view, no_cache)
    except Exception as exc:
        print(f"[warning] Could not fetch peers data: {exc}", file=sys.stderr)
        return PeerComparisonData(
            sector=sector, industry=industry,
            sub_industry=sub_industry, sub_sub_industry=sub_sub,
            indices=indices, columns=[], peers=[],
        )

    columns, peers = _parse_peers_fragment(fragment)

    return PeerComparisonData(
        sector=sector,
        industry=industry,
        sub_industry=sub_industry,
        sub_sub_industry=sub_sub,
        indices=indices,
        columns=columns,
        peers=peers,
    )
