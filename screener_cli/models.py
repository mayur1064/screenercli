"""Data models (dataclasses) for financial sections returned by screener_cli."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RowData:
    label: str
    values: list[float | None]
    unit: str | None = None          # override when row has its own unit (e.g. OPM %)
    is_subtotal: bool = False


@dataclass
class FinancialTable:
    section: str
    unit: str                        # display unit, e.g. "Rs. Crores"
    currency: str                    # e.g. "INR"
    period_type: str                 # "annual" | "quarterly"
    headers: list[str]              # date labels
    rows: list[RowData]
    footnotes: list[str] = field(default_factory=list)


@dataclass
class GrowthTable:
    """Compounded growth / CAGR table that appears in Profit & Loss section."""
    label: str                       # e.g. "Compounded Sales Growth"
    periods: list[str]               # e.g. ["10 Years", "5 Years", "3 Years", "TTM"]
    values: list[str]                # e.g. ["14%", "12%", "10%", "8%"]


@dataclass
class ShareholdingTable:
    period_type: str                 # "quarterly"
    headers: list[str]
    rows: list[RowData]
    latest: dict[str, float | None] = field(default_factory=dict)


@dataclass
class ProsConsData:
    pros: list[str]
    cons: list[str]
    about: str | None = None
    key_metrics: dict[str, str] = field(default_factory=dict)


@dataclass
class PeerData:
    rank: int | None
    name: str
    url: str | None                  # screener.in relative URL, e.g. "/company/IOCL/"
    values: dict[str, float | None]  # column_name -> numeric value (None when N/A or text)


@dataclass
class PeerComparisonData:
    sector: str | None               # e.g. "Energy"
    industry: str | None             # e.g. "Oil, Gas & Consumable Fuels"
    sub_industry: str | None         # e.g. "Petroleum Products"
    sub_sub_industry: str | None     # e.g. "Refineries & Marketing"
    indices: list[str]               # market indices the company belongs to
    columns: list[str]               # column headers as shown on the page
    peers: list[PeerData]


@dataclass
class AllSections:
    symbol: str
    view: str
    scraped_at: str
    source_url: str
    quarterly_results: FinancialTable | None = None
    profit_loss: FinancialTable | None = None
    profit_loss_growth: list[GrowthTable] = field(default_factory=list)
    balance_sheet: FinancialTable | None = None
    cash_flow: FinancialTable | None = None
    ratios: FinancialTable | None = None
    shareholding: ShareholdingTable | None = None
    pros_cons: ProsConsData | None = None
