"""Parser for Balance Sheet section (annual)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import FinancialTable
from .utils import parse_section_table

# Row labels that belong to the liabilities block; everything else is assets.
_LIABILITY_LABELS = frozenset(
    {
        "share capital",
        "reserves",
        "borrowings",
        "other liabilities",
        "total liabilities",
        "equity capital",
        "equity share capital",
    }
)


def parse(soup: BeautifulSoup) -> FinancialTable | None:
    """
    Parse the Balance Sheet table (section id: ``balance-sheet``).

    Rows are annotated with a ``unit`` tag of ``"liability"`` or ``"asset"``
    using the ``RowData.unit`` field when no currency unit is otherwise set.
    """
    table = parse_section_table(
        soup=soup,
        section_id="balance-sheet",
        section_name="Balance Sheet",
        period_type="annual",
    )
    if table is None:
        return None

    # Annotate each row as liability or asset based on label heuristics.
    in_liabilities_block = True
    for row in table.rows:
        label_lower = row.label.lower()
        if "total liabilities" in label_lower:
            in_liabilities_block = False
        if row.unit is None:
            row.unit = "liability" if in_liabilities_block else "asset"

    return table
