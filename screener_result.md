# Screener.in CLI Tool — Implementation Plan

## Overview

A Python-based CLI tool that scrapes [screener.in](https://www.screener.in) company pages and returns structured financial data optimized for consumption by coding agents. The tool accepts a stock ticker symbol and exposes subcommands for each financial data section.

---

## URL Pattern & Identifier

Screener.in uses the stock ticker symbol in its URL:

```
https://www.screener.in/company/{SYMBOL}/consolidated/
https://www.screener.in/company/{SYMBOL}/standalone/
```

**Identifier chosen: Ticker symbol** (e.g., `RELIANCE`, `TCS`, `INFY`)  
- Universally recognized and directly maps to the URL
- Unambiguous — no fuzzy matching needed
- Default view: `consolidated`; switchable to `standalone` via flag

---

## Project Structure

```
screener_cli/
├── __init__.py
├── cli.py              # Click-based CLI entry point
├── scraper.py          # HTTP fetch with session, headers, caching
├── parsers/
│   ├── __init__.py
│   ├── quarterly.py    # Quarterly Results parser
│   ├── profit_loss.py  # Profit & Loss parser
│   ├── balance_sheet.py
│   ├── cash_flow.py
│   ├── ratios.py
│   ├── shareholding.py
│   └── pros_cons.py    # Pros & Cons + About section parser
├── formatters/
│   ├── __init__.py
│   ├── json_fmt.py     # JSON output (default for agents)
│   └── text_fmt.py     # Rich/tabular text output (human-readable)
└── models.py           # Dataclasses for each financial data type

setup.py / pyproject.toml
requirements.txt
```

---

## Dependencies

```
requests>=2.31.0          # HTTP client
beautifulsoup4>=4.12.0    # HTML parsing
lxml>=5.0.0               # Fast HTML parser backend for BS4
click>=8.1.0              # CLI framework
rich>=13.0.0              # Terminal tables and formatted output
cachetools>=5.3.0         # In-memory request caching (TTL cache)
```

---

## CLI Interface Design

```
screener [OPTIONS] SYMBOL COMMAND
```

### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--view` | `consolidated` or `standalone` | `consolidated` |
| `--format` | `json` or `text` | `json` |
| `--no-cache` | Bypass in-memory cache | False |

### Commands

| Command | Description |
|---------|-------------|
| `quarterly-results` | Last 13 quarters of P&L |
| `profit-loss` | Annual P&L with growth metrics |
| `balance-sheet` | Annual balance sheet |
| `cash-flow` | Annual cash flow statement |
| `ratios` | Key operating ratios over years |
| `shareholding` | Quarterly promoter/FII/DII/public holding |
| `pros-cons` | Machine-generated pros and cons from screener |
| `all` | All sections combined into one JSON payload |

### Example Usage

```bash
# Get quarterly results for Reliance (JSON, default)
screener RELIANCE quarterly-results

# Get balance sheet in human-readable text
screener --format text RELIANCE balance-sheet

# Get standalone profit & loss
screener --view standalone TCS profit-loss

# Get all sections as JSON
screener INFY all

# Pipe to a file for agent consumption
screener HDFC all > hdfc_data.json
```

---

## Implementation Steps

### Step 1: Project Scaffolding

1. Create the directory structure above.
2. Add `pyproject.toml` (or `setup.py`) with entry point:
   ```toml
   [project.scripts]
   screener = "screener_cli.cli:main"
   ```
3. Install in editable mode: `pip install -e .`

---

### Step 2: HTTP Scraper (`scraper.py`)

**Key responsibilities:**
- Build the URL from symbol + view type
- Send a `GET` request with browser-like headers to avoid bot detection
- Raise clear errors for HTTP 404 (company not found) or 429 (rate limited)
- Cache the parsed `BeautifulSoup` object per symbol+view for the duration of a CLI session (TTL: 5 minutes)

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetch_page(symbol: str, view: str = "consolidated") -> BeautifulSoup:
    url = f"https://www.screener.in/company/{symbol.upper()}/{view}/"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()  # raises HTTPError for 4xx/5xx
    return BeautifulSoup(response.text, "lxml")
```

**Error handling:**
- `404` → `CompanyNotFoundError(symbol)`
- `429` → `RateLimitError` with retry-after hint
- Connection timeout → `ScraperTimeoutError`

---

### Step 3: Generic Table Parser Utility

All financial sections on screener.in are HTML `<table>` elements within `<section>` tags with known `id` attributes:

| Section | HTML `id` |
|---------|-----------|
| Quarterly Results | `quarters` |
| Profit & Loss | `profit-loss` |
| Balance Sheet | `balance-sheet` |
| Cash Flows | `cash-flow` |
| Ratios | `ratios` |
| Shareholding | `shareholding` |

A shared utility function extracts any section table:

```python
def parse_section_table(soup: BeautifulSoup, section_id: str) -> dict:
    """
    Returns:
    {
        "headers": ["Mar 2022", "Mar 2023", ...],
        "rows": [
            {"label": "Sales", "values": [216737, 231886, ...]},
            {"label": "Expenses", "values": [181728, 190918, ...]},
            ...
        ]
    }
    """
    section = soup.find("section", id=section_id)
    table = section.find("table")
    # parse <thead> for date headers
    # parse <tbody> rows for label + numeric values
    # strip commas, handle % signs, convert to float/int
```

**Value normalization:**
- Strip commas from numbers: `"1,38,761"` → `138761`
- Keep `%` values as floats: `"16%"` → `16.0`
- Replace empty cells with `null`
- Annotate unit in metadata: `"unit": "Rs. Crores"` or `"unit": "percentage"`

---

### Step 4: Section-Specific Parsers

Each parser calls the generic table parser and adds section-specific enrichment:

#### `quarterly.py`
- Section id: `quarters`
- Adds growth rates section if present (compounded sales/profit growth)
- Output includes `"period_type": "quarterly"`

#### `profit_loss.py`
- Section id: `profit-loss`
- Extracts compounded growth tables (Sales Growth, Profit Growth, Stock CAGR, ROE)
- Output includes both the main table and growth summary

#### `balance_sheet.py`
- Section id: `balance-sheet`
- Distinguishes liabilities block from assets block
- Labels rows as `"type": "liability"` or `"type": "asset"`

#### `cash_flow.py`
- Section id: `cash-flow`
- Tags rows: `"Operating"`, `"Investing"`, `"Financing"`, `"Net"`

#### `ratios.py`
- Section id: `ratios`
- Includes `"description"` hints for each ratio (e.g., Debtor Days, ROCE %)

#### `shareholding.py`
- Section id: `shareholding`
- Output: latest quarter percentages + historical trend
- Clearly separates: `Promoters`, `FIIs`, `DIIs`, `Government`, `Public`

#### `pros_cons.py`
- Pros: `soup.select(".pros li")` (or similar selector)
- Cons: `soup.select(".cons li")`
- Also extracts the company `About` blurb and key metrics header (Market Cap, P/E, etc.)

---

### Step 5: Output Models (`models.py`)

Use Python `dataclasses` or `TypedDict` for typed output:

```python
@dataclass
class FinancialTable:
    section: str
    unit: str
    currency: str
    period_type: str          # "annual" or "quarterly"
    headers: list[str]        # Date labels
    rows: list[RowData]
    footnotes: list[str]

@dataclass
class RowData:
    label: str
    values: list[float | None]
    is_subtotal: bool = False
```

---

### Step 6: Output Formatters

#### JSON Formatter (`json_fmt.py`)
- Serialize dataclasses to JSON using `dataclasses.asdict()`
- Wrap all sections under a top-level key with metadata:

```json
{
  "symbol": "RELIANCE",
  "view": "consolidated",
  "scraped_at": "2026-03-13T10:00:00Z",
  "source_url": "https://www.screener.in/company/RELIANCE/consolidated/",
  "sections": {
    "quarterly_results": { ... },
    "profit_loss": { ... },
    "balance_sheet": { ... },
    "cash_flow": { ... },
    "ratios": { ... },
    "shareholding": { ... },
    "pros_cons": { ... }
  }
}
```

#### Text Formatter (`text_fmt.py`)
- Uses `rich.table.Table` to render pretty terminal tables
- Color-codes positive/negative values (green/red)
- Prints section headings and units

---

### Step 7: CLI Entry Point (`cli.py`)

```python
import click
from .scraper import fetch_page
from .parsers import quarterly, profit_loss, balance_sheet, cash_flow, ratios, shareholding, pros_cons
from .formatters import json_fmt, text_fmt

@click.group()
@click.argument("symbol")
@click.option("--view", type=click.Choice(["consolidated", "standalone"]), default="consolidated")
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="json")
@click.pass_context
def main(ctx, symbol, view, fmt):
    ctx.ensure_object(dict)
    ctx.obj["symbol"] = symbol
    ctx.obj["view"] = view
    ctx.obj["fmt"] = fmt
    ctx.obj["soup"] = fetch_page(symbol, view)

@main.command("quarterly-results")
@click.pass_context
def quarterly_results_cmd(ctx):
    data = quarterly.parse(ctx.obj["soup"])
    output(data, ctx.obj["fmt"])

# ... similar for all other commands

@main.command("all")
@click.pass_context
def all_cmd(ctx):
    soup = ctx.obj["soup"]
    data = {
        "symbol": ctx.obj["symbol"],
        "view": ctx.obj["view"],
        "sections": {
            "quarterly_results": quarterly.parse(soup),
            "profit_loss": profit_loss.parse(soup),
            "balance_sheet": balance_sheet.parse(soup),
            "cash_flow": cash_flow.parse(soup),
            "ratios": ratios.parse(soup),
            "shareholding": shareholding.parse(soup),
            "pros_cons": pros_cons.parse(soup),
        }
    }
    output(data, ctx.obj["fmt"])
```

---

### Step 8: Error Handling & Edge Cases

| Scenario | Handling |
|----------|----------|
| Company has no consolidated view | Auto-fallback to standalone + warn |
| Section missing from page | Return `null` for that section, log warning |
| Login-gated content (e.g., Insights) | Return `{"status": "login_required"}` |
| Numbers with footnote markers (`+`) | Strip `+`, note in `footnotes` field |
| Rate limiting by screener.in | Exponential backoff (max 3 retries) |
| Invalid symbol | Exit with code 1 and clear error message |

---

## Data Output Schema (Agent-Optimized)

The JSON output is designed to be directly consumable by LLM agents:

```json
{
  "symbol": "RELIANCE",
  "view": "consolidated",
  "scraped_at": "2026-03-13T10:00:00Z",
  "sections": {
    "quarterly_results": {
      "unit": "Rs. Crores",
      "period_type": "quarterly",
      "headers": ["Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024"],
      "rows": [
        {"label": "Sales", "values": [207559, 231886, 225086, 236533, 231784]},
        {"label": "Expenses", "values": [169466, 190918, 184430, 194017, 193019]},
        {"label": "Operating Profit", "values": [38093, 40968, 40656, 42516, 38765]},
        {"label": "OPM %", "values": [18.0, 18.0, 18.0, 18.0, 17.0], "unit": "%"},
        {"label": "Net Profit", "values": [18258, 19878, 19641, 21243, 17445]}
      ]
    },
    "pros_cons": {
      "pros": [],
      "cons": [
        "The company has delivered a poor sales growth of 10.0% over past five years.",
        "Company has a low return on equity of 8.79% over last 3 years.",
        "Dividend payout has been low at 9.84% of profits over last 3 years."
      ]
    }
  }
}
```

---

## Development Phases

### Phase 1 — Core Scraper (MVP)
- [ ] `scraper.py`: fetch page, handle errors
- [ ] Generic table parser utility
- [ ] `quarterly.py` and `profit_loss.py` parsers
- [ ] JSON formatter
- [ ] Basic Click CLI with `quarterly-results` and `profit-loss` commands

### Phase 2 — Full Data Coverage
- [ ] Remaining parsers: `balance_sheet`, `cash_flow`, `ratios`, `shareholding`, `pros_cons`
- [ ] `all` command
- [ ] Text formatter with `rich`

### Phase 3 — Polish & Packaging
- [ ] `pyproject.toml` with entry point
- [ ] TTL caching to avoid redundant requests
- [ ] Retry logic with exponential backoff
- [ ] Standalone fallback when consolidated is unavailable
- [ ] Unit tests using saved HTML fixtures (no real network calls in tests)
- [ ] README with examples

---

## Notes on screener.in Scraping

1. **No official API**: screener.in does not provide a public API; scraping is the only option.
2. **Login wall**: Some data (e.g., Product Insights, detailed notes) requires a free account login. The core financial tables (Quarterly, P&L, Balance Sheet, Cash Flow, Ratios, Shareholding, Pros/Cons) are publicly accessible without login.
3. **Respectful scraping**: Add a delay between requests (`time.sleep(1)`) and respect the site's `robots.txt`. Do not use this tool for bulk/automated mass scraping.
4. **HTML stability**: screener.in's HTML structure is stable but can change. Parsers should fail gracefully with descriptive errors rather than silently returning empty data.
5. **Data currency**: Data on screener.in is sourced from C-MOTS Internet Technologies and is typically updated within 24 hours of official filings.
