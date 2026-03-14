"""Click-based CLI entry point for screener_cli."""

from __future__ import annotations

import dataclasses
import sys
from datetime import datetime, timezone
from typing import Any

import click

from .scraper import (
    CompanyNotFoundError,
    RateLimitError,
    ScraperError,
    ScraperTimeoutError,
    fetch_page_with_fallback,
)
from .parsers import quarterly, profit_loss, balance_sheet, cash_flow, ratios, shareholding, pros_cons, peers
from .formatters import json_fmt, text_fmt

# ---------------------------------------------------------------------------
# Shared output helper
# ---------------------------------------------------------------------------

def _output(data: Any, fmt: str, symbol: str = "", view: str = "") -> None:
    if fmt == "json":
        json_fmt.print_json(data)
    else:
        text_fmt.print_text(data, symbol=symbol, view=view)


# ---------------------------------------------------------------------------
# Root command group
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=False)
@click.version_option(package_name="screener-cli")
@click.argument("symbol")
@click.option(
    "--view",
    type=click.Choice(["consolidated", "standalone"], case_sensitive=False),
    default="consolidated",
    show_default=True,
    help="Use consolidated or standalone financials.",
)
@click.option(
    "--format", "fmt",
    type=click.Choice(["json", "text"], case_sensitive=False),
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--no-cache",
    is_flag=True,
    default=False,
    help="Bypass the in-memory page cache.",
)
@click.pass_context
def main(ctx: click.Context, symbol: str, view: str, fmt: str, no_cache: bool) -> None:
    """
    Fetch structured financial data for SYMBOL from screener.in.

    SYMBOL is a stock ticker, e.g. RELIANCE, TCS, INFY.
    """
    ctx.ensure_object(dict)
    ctx.obj["symbol"] = symbol.upper()
    ctx.obj["view"] = view
    ctx.obj["fmt"] = fmt
    ctx.obj["no_cache"] = no_cache

    # Fetch and cache the page eagerly so subcommands share it.
    try:
        soup, actual_view = fetch_page_with_fallback(symbol, view, no_cache)
    except CompanyNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except RateLimitError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except ScraperTimeoutError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except ScraperError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    ctx.obj["soup"] = soup
    ctx.obj["view"] = actual_view  # may have changed due to fallback


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

@main.command("quarterly-results")
@click.pass_context
def quarterly_results_cmd(ctx: click.Context) -> None:
    """Last 13 quarters of Profit & Loss."""
    data = quarterly.parse(ctx.obj["soup"])
    if data is None:
        click.echo("Error: Quarterly Results section not found.", err=True)
        sys.exit(1)
    _output(dataclasses.asdict(data), ctx.obj["fmt"])


@main.command("profit-loss")
@click.pass_context
def profit_loss_cmd(ctx: click.Context) -> None:
    """Annual Profit & Loss with compounded growth tables."""
    result = profit_loss.parse(ctx.obj["soup"])
    if result is None:
        click.echo("Error: Profit & Loss section not found.", err=True)
        sys.exit(1)
    # Serialise nested dataclasses
    out = {
        "table": dataclasses.asdict(result["table"]),
        "growth_tables": [dataclasses.asdict(g) for g in result["growth_tables"]],
    }
    _output(out, ctx.obj["fmt"])


@main.command("balance-sheet")
@click.pass_context
def balance_sheet_cmd(ctx: click.Context) -> None:
    """Annual Balance Sheet."""
    data = balance_sheet.parse(ctx.obj["soup"])
    if data is None:
        click.echo("Error: Balance Sheet section not found.", err=True)
        sys.exit(1)
    _output(dataclasses.asdict(data), ctx.obj["fmt"])


@main.command("cash-flow")
@click.pass_context
def cash_flow_cmd(ctx: click.Context) -> None:
    """Annual Cash Flow statement."""
    data = cash_flow.parse(ctx.obj["soup"])
    if data is None:
        click.echo("Error: Cash Flow section not found.", err=True)
        sys.exit(1)
    _output(dataclasses.asdict(data), ctx.obj["fmt"])


@main.command("ratios")
@click.pass_context
def ratios_cmd(ctx: click.Context) -> None:
    """Key operating ratios over the years."""
    data = ratios.parse(ctx.obj["soup"])
    if data is None:
        click.echo("Error: Ratios section not found.", err=True)
        sys.exit(1)
    _output(dataclasses.asdict(data), ctx.obj["fmt"])


@main.command("shareholding")
@click.pass_context
def shareholding_cmd(ctx: click.Context) -> None:
    """Quarterly promoter / FII / DII / public holding pattern."""
    data = shareholding.parse(ctx.obj["soup"])
    if data is None:
        click.echo("Error: Shareholding section not found.", err=True)
        sys.exit(1)
    _output(dataclasses.asdict(data), ctx.obj["fmt"])


@main.command("pros-cons")
@click.pass_context
def pros_cons_cmd(ctx: click.Context) -> None:
    """Machine-generated pros and cons, about blurb, and key metrics."""
    data = pros_cons.parse(ctx.obj["soup"])
    _output(dataclasses.asdict(data), ctx.obj["fmt"])


@main.command("peer-comparison")
@click.pass_context
def peer_comparison_cmd(ctx: click.Context) -> None:
    """Peer comparison table: sector, industry, indices and per-peer metrics."""
    data = peers.parse(ctx.obj["soup"], no_cache=ctx.obj["no_cache"])
    if data is None:
        click.echo("Error: Peer Comparison section not found.", err=True)
        sys.exit(1)
    _output(dataclasses.asdict(data), ctx.obj["fmt"])


@main.command("all")
@click.pass_context
def all_cmd(ctx: click.Context) -> None:
    """All sections combined into one payload."""
    soup = ctx.obj["soup"]
    symbol = ctx.obj["symbol"]
    view = ctx.obj["view"]
    no_cache = ctx.obj["no_cache"]

    pl_result = profit_loss.parse(soup)
    pl_table = dataclasses.asdict(pl_result["table"]) if pl_result else None
    pl_growth = [dataclasses.asdict(g) for g in pl_result["growth_tables"]] if pl_result else []

    def _safe(fn, *args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            return dataclasses.asdict(result) if (result is not None and dataclasses.is_dataclass(result)) else result
        except Exception:
            return None

    out = {
        "symbol": symbol,
        "view": view,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source_url": f"https://www.screener.in/company/{symbol}/{view}/",
        "sections": {
            "quarterly_results": _safe(quarterly.parse, soup),
            "profit_loss": {"table": pl_table, "growth_tables": pl_growth},
            "balance_sheet": _safe(balance_sheet.parse, soup),
            "cash_flow": _safe(cash_flow.parse, soup),
            "ratios": _safe(ratios.parse, soup),
            "shareholding": _safe(shareholding.parse, soup),
            "pros_cons": _safe(pros_cons.parse, soup),
            "peer_comparison": _safe(peers.parse, soup, no_cache=no_cache),
        },
    }
    _output(out, ctx.obj["fmt"], symbol=symbol, view=view)
