# screener-cli

A Python command-line tool that scrapes [screener.in](https://www.screener.in) company pages and returns structured financial data optimised for consumption by LLM coding agents (JSON by default) or human-readable terminal output.

---

## Features

- Fetches all major financial sections: Quarterly Results, Profit & Loss, Balance Sheet, Cash Flow, Key Ratios, Shareholding Pattern, and Pros/Cons.
- Outputs clean, normalised JSON (commas stripped, `%` values as floats, empty cells as `null`).
- Optional `--format text` mode renders colour-coded tables in the terminal using [Rich](https://github.com/Textualize/rich).
- TTL-based in-memory cache (5 minutes) so multiple sub-commands on the same ticker only fetch the page once per session.
- Automatic fallback from `consolidated` → `standalone` with a warning when the consolidated view is unavailable.
- Graceful error handling for missing sections, rate-limiting (HTTP 429 with exponential back-off), and invalid tickers.

---

## Requirements

- Python **3.11+**
- An internet connection (screener.in is a public site; no API key required)

---

## Installation

### From PyPI (recommended)

```bash
pip install screenercli
```

### From source (for development)

```bash
git clone <repo-url> screener-cli
cd screener-cli
pip install -e .
```

After installation the `screener` command is available in your shell.

---

## Usage

```
screener [OPTIONS] SYMBOL COMMAND [ARGS]...
```

### Global options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--view` | `consolidated` / `standalone` | `consolidated` | Which financial view to fetch (see below) |
| `--format` | `json` / `text` | `json` | Output format |
| `--no-cache` | flag | off | Bypass the in-memory TTL cache |
| `--version` | — | — | Print version and exit |

#### `--view` explained

| Value | Meaning |
|-------|---------|
| `consolidated` | Shows the **combined** financial position of the parent company and all its subsidiaries as a single entity. Most large listed companies publish consolidated results; this is the default. |
| `standalone` | Shows the financial position of **only the parent company**, excluding its subsidiaries. Useful when you want to analyse the parent in isolation. |

If the requested view is unavailable for a ticker, the CLI automatically falls back to the other view and prints a warning.

### Commands

| Command | Description |
|---------|-------------|
| `quarterly-results` | Last 13 quarters of P&L |
| `profit-loss` | Annual P&L with compounded growth tables |
| `balance-sheet` | Annual Balance Sheet |
| `cash-flow` | Annual Cash Flow statement |
| `ratios` | Key operating ratios over the years |
| `shareholding` | Quarterly promoter / FII / DII / public holding |
| `pros-cons` | Screener-generated pros and cons |
| `about` | Company description / about blurb |
| `key-metrics` | Key header metrics (Market Cap, P/E, Book Value, etc.) |
| `peer-comparison` | Industry peers with valuation and performance metrics |
| `all` | All sections combined into one JSON payload |

---

## Examples

### Get quarterly results (JSON — ready for an agent)

```bash
screener RELIANCE quarterly-results
```

```json
{
  "section": "Quarterly Results",
  "unit": "Rs. Crores",
  "currency": "INR",
  "period_type": "quarterly",
  "headers": ["Jun 2023", "Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024"],
  "rows": [
    {"label": "Sales", "values": [207559, 231886, 225086, 236533, 231784], ...},
    {"label": "Net Profit", "values": [18258, 19878, 19641, 21243, 17445], ...}
  ],
  "footnotes": []
}
```

### Get balance sheet as human-readable table

```bash
screener --format text RELIANCE balance-sheet
```

### Get standalone profit & loss for TCS

```bash
screener --view standalone TCS profit-loss
```

### Get all data sections as a single JSON payload

```bash
screener INFY all
```

### Pipe output to a file for offline agent consumption

```bash
screener HDFC all > hdfc_data.json
```

### Get pros/cons and company about

```bash
screener --format text WIPRO pros-cons
```

### Get peer comparison (JSON)

```bash
screener RELIANCE peer-comparison
```

### Get peer comparison as a terminal table

```bash
screener --format text TCS peer-comparison
```

---

## JSON Output Schema

Every financial-table command returns an object matching the following structure:

```json
{
  "section": "string",
  "unit": "Rs. Crores",
  "currency": "INR",
  "period_type": "annual | quarterly",
  "headers": ["Mar 2020", "Mar 2021", ...],
  "rows": [
    {
      "label": "Sales",
      "values": [123456, 234567, null],
      "unit": null,
      "is_subtotal": false
    }
  ],
  "footnotes": []
}
```

The `all` command wraps everything under a top-level envelope:

```json
{
  "symbol": "RELIANCE",
  "view": "consolidated",
  "scraped_at": "2026-03-13T10:00:00+00:00",
  "source_url": "https://www.screener.in/company/RELIANCE/consolidated/",
  "sections": {
    "quarterly_results": { ... },
    "profit_loss": {
      "table": { ... },
      "growth_tables": [
        {"label": "Compounded Sales Growth", "periods": ["10 Years", "5 Years"], "values": ["14%", "12%"]}
      ]
    },
    "balance_sheet": { ... },
    "cash_flow": { ... },
    "ratios": { ... },
    "shareholding": {
      "period_type": "quarterly",
      "headers": [...],
      "rows": [...],
      "latest": {"Promoters": 49.6, "FIIs": 24.3, "DIIs": 13.5, "Public": 12.6}
    },
    "pros_cons": {
      "pros": ["..."],
      "cons": ["..."],
      "about": "Reliance Industries Limited...",
      "key_metrics": {"Market Cap": "17,45,678 Cr", "P/E": "24.5"}
    },
    "peer_comparison": {
      "sector": "Energy",
      "industry": "Oil, Gas & Consumable Fuels",
      "sub_industry": "Petroleum Products",
      "sub_sub_industry": "Refineries & Marketing",
      "indices": ["BSE Sensex", "Nifty 50", "BSE 500"],
      "columns": ["Name", "CMP Rs.", "P/E", "Mar Cap Rs.Cr.", "Div Yld %", "NP Qtr Rs.Cr.", "Qtr Profit Var %", "Sales Qtr Rs.Cr.", "Qtr Sales Var %", "ROCE %"],
      "peers": [
        {"rank": 1, "name": "Reliance Industries", "url": "/company/RELIANCE/", "values": {"CMP Rs.": 1380.7, "P/E": 24.35, "Mar Cap Rs.Cr.": 1868897.82, "Div Yld %": 0.4, "ROCE %": 9.69}},
        {"rank": 2, "name": "I O C L",            "url": "/company/IOC/",      "values": {"CMP Rs.": 156.54, "P/E": 6.18, "Mar Cap Rs.Cr.": 221067.66, "Div Yld %": 4.47, "ROCE %": 7.36}}
      ]
    }
  }
}
```

---

## Error Codes

| Exit code | Reason |
|-----------|--------|
| `0` | Success |
| `1` | Company not found, rate limited, timeout, or scraper error |

Errors are printed to **stderr** so stdout always contains clean JSON.

---

## Tips for LLM Agents

- Use the `all` command to fetch everything in a single HTTP request.
- All numeric values are `float | null` — no string parsing needed.
- Percentage rows (e.g. OPM %) are identified by `"unit": "%"` on the row.
- Balance Sheet rows include `"unit": "liability"` or `"unit": "asset"` to distinguish blocks.
- Cash Flow rows include `"unit": "Operating" | "Investing" | "Financing" | "Net"`.
- The `latest` field in `shareholding` always gives the most recent quarter's breakdown.
- `peer_comparison.peers` is an ordered list (rank 1 = the queried company itself). Each peer's `values` dict has the same keys as `peer_comparison.columns` (minus "Name").
- `peer_comparison.sector / industry / sub_industry / sub_sub_industry` give the full industry hierarchy.
- The columns in the peer table are whichever columns the screener.in user has configured — always check `columns` before reading `values`.

---

## Responsible Use

- screener.in is a free public service. Please add a delay between requests if running batch jobs.
- Respect `robots.txt`. Do not use this tool for bulk or automated mass scraping.
- The tool adds a 1-second courtesy delay between retries and caches pages for 5 minutes.

---

## Project Structure

```
screener_cli/
├── cli.py              # Click-based CLI entry point
├── scraper.py          # HTTP fetch, error handling, TTL cache
├── models.py           # Dataclasses for typed output
├── parsers/
│   ├── utils.py        # Generic table parser shared by all sections
│   ├── quarterly.py
│   ├── profit_loss.py
│   ├── balance_sheet.py
│   ├── cash_flow.py
│   ├── ratios.py
│   ├── shareholding.py
│   ├── pros_cons.py
│   └── peers.py        # Peer comparison parser
└── formatters/
    ├── json_fmt.py     # JSON serialiser
    └── text_fmt.py     # Rich terminal renderer
pyproject.toml
requirements.txt
```

---

## License

MIT
