"""Rich text formatter — renders financial tables in the terminal."""

from __future__ import annotations

import dataclasses
import io
import sys
from typing import Any

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

try:
    _out = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
except AttributeError:
    _out = sys.stdout

console = Console(file=_out, legacy_windows=False)


def _val_to_str(val: float | None, unit: str | None = None) -> str:
    if val is None:
        return "-"
    formatted = f"{val:,.2f}".rstrip("0").rstrip(".")
    if unit == "%":
        return f"{formatted}%"
    return formatted


def _value_style(val: float | None) -> str:
    if val is None:
        return "dim"
    if val < 0:
        return "red"
    return "green"


def _render_financial_table(data: Any, title: str) -> None:
    """Render a FinancialTable dataclass as a Rich table."""
    if data is None:
        console.print(f"[yellow]{title}[/yellow]: data not available.")
        return

    if dataclasses.is_dataclass(data):
        d = dataclasses.asdict(data)
    else:
        d = data

    headers = d.get("headers", [])
    rows = d.get("rows", [])
    unit = d.get("unit", "")

    table = Table(
        title=f"{title}  [dim]({unit})[/dim]",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("", style="bold", no_wrap=True)
    for h in headers:
        table.add_column(h, justify="right")

    for row in rows:
        label = row.get("label", "")
        values = row.get("values", [])
        row_unit = row.get("unit")
        is_subtotal = row.get("is_subtotal", False)

        cells = []
        for val in values:
            style = _value_style(val)
            cells.append(Text(_val_to_str(val, row_unit), style=style))

        label_text = Text(label, style="bold" if is_subtotal else "")
        table.add_row(label_text, *cells)

    console.print(table)


def print_text(data: Any, symbol: str = "", view: str = "") -> None:
    """
    Render *data* (result of any parse() call) as rich terminal output.

    Handles both single-section dicts and the ``all`` combined dict.
    """
    if isinstance(data, dict) and "sections" in data:
        # 'all' command output
        sym = data.get("symbol", symbol)
        v = data.get("view", view)
        console.rule(f"[bold]{sym}[/bold] — {v}")
        sections: dict[str, Any] = data["sections"]
        _render_section("Quarterly Results", sections.get("quarterly_results"))
        _render_section("Profit & Loss", sections.get("profit_loss"))
        _render_section("Balance Sheet", sections.get("balance_sheet"))
        _render_section("Cash Flow", sections.get("cash_flow"))
        _render_section("Key Ratios", sections.get("ratios"))
        _render_section("Shareholding", sections.get("shareholding"))
        _render_pros_cons(sections.get("pros_cons"))
        _render_peers(sections.get("peer_comparison"))
        return

    # Single-section: detect peer comparison data by its distinctive keys
    if isinstance(data, dict) and "peers" in data and "columns" in data:
        _render_peers(data)
        return

    # Single section
    _render_section("Financial Data", data)


def _render_section(title: str, data: Any) -> None:
    if data is None:
        return
    if isinstance(data, dict) and "table" in data:
        # profit_loss returns {"table": ..., "growth_tables": [...]}
        _render_financial_table(data["table"], title)
        for g in data.get("growth_tables", []):
            _render_growth(g)
        return
    # ShareholdingTable / FinancialTable
    if dataclasses.is_dataclass(data):
        d = dataclasses.asdict(data)
    elif isinstance(data, dict):
        d = data
    else:
        return
    _render_financial_table(d, title)
    if "latest" in d:
        _render_latest(d["latest"])


def _render_latest(latest: dict[str, Any]) -> None:
    console.print("[bold]Latest quarter:[/bold]")
    for k, v in latest.items():
        val_str = f"{v:.2f}%" if v is not None else "-"
        console.print(f"  {k}: {val_str}")
    console.print()


def _render_growth(g: Any) -> None:
    if dataclasses.is_dataclass(g):
        g = dataclasses.asdict(g)
    label = g.get("label", "Growth")
    periods = g.get("periods", [])
    values = g.get("values", [])
    console.print(f"[bold]{label}[/bold]")
    for p, v in zip(periods, values):
        console.print(f"  {p}: {v}")
    console.print()


def _render_pros_cons(data: Any) -> None:
    if data is None:
        return
    if dataclasses.is_dataclass(data):
        data = dataclasses.asdict(data)

    about = data.get("about")
    if about:
        console.rule("[bold]About[/bold]")
        console.print(about)
        console.print()

    key_metrics = data.get("key_metrics", {})
    if key_metrics:
        console.rule("[bold]Key Metrics[/bold]")
        for k, v in key_metrics.items():
            console.print(f"  [cyan]{k}[/cyan]: {v}")
        console.print()

    pros = data.get("pros", [])
    cons = data.get("cons", [])

    if pros:
        console.rule("[bold green]Pros[/bold green]")
        for p in pros:
            console.print(f"  [green]+ {p}[/green]")
        console.print()

    if cons:
        console.rule("[bold red]Cons[/bold red]")
        for c in cons:
            console.print(f"  [red]- {c}[/red]")
        console.print()


def _render_peers(data: Any) -> None:
    """Render a PeerComparisonData dict as a Rich table."""
    if data is None:
        return
    if dataclasses.is_dataclass(data):
        data = dataclasses.asdict(data)

    console.rule("[bold]Peer Comparison[/bold]")

    # Industry breadcrumb
    breadcrumb_parts = [
        data.get("sector"),
        data.get("industry"),
        data.get("sub_industry"),
        data.get("sub_sub_industry"),
    ]
    breadcrumb = " > ".join(p for p in breadcrumb_parts if p)
    if breadcrumb:
        console.print(f"  [dim]Sector:[/dim] {breadcrumb}")

    indices = data.get("indices", [])
    if indices:
        console.print(f"  [dim]Part of:[/dim] {', '.join(indices)}")
    console.print()

    columns: list[str] = data.get("columns", [])
    peer_rows: list[dict] = data.get("peers", [])
    if not peer_rows:
        console.print("  No peer data available.")
        return

    # Build Rich table — Name column + one column per metric
    metric_columns = columns[1:] if len(columns) > 1 else columns  # skip Name
    table = Table(
        title="Peers",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Name", style="bold", no_wrap=True)
    for col in metric_columns:
        table.add_column(col, justify="right")

    for peer in peer_rows:
        rank_str = str(peer.get("rank", "") or "")
        name = peer.get("name", "")
        values: dict = peer.get("values", {})
        cells = []
        for col in metric_columns:
            val = values.get(col)
            style = _value_style(val)
            cells.append(Text(_val_to_str(val), style=style))
        table.add_row(rank_str, name, *cells)

    console.print(table)
