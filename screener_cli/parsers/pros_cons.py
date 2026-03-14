"""Parser for Pros, Cons, About and key metrics header."""

from __future__ import annotations

import sys

from bs4 import BeautifulSoup, Tag

from ..models import ProsConsData


def _text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    return tag.get_text(separator=" ", strip=True)


def parse(soup: BeautifulSoup) -> ProsConsData:
    """
    Extract:
    - Pros bullet-points
    - Cons bullet-points
    - Company ``About`` blurb (first paragraph of the company description)
    - Key header metrics (Market Cap, P/E, Book Value, etc.)
    """
    pros: list[str] = []
    cons: list[str] = []

    # Screener.in wraps pros/cons in a <div class="pros"> / <div class="cons">
    pros_div: Tag | None = soup.find("div", class_="pros")  # type: ignore[assignment]
    if pros_div:
        for li in pros_div.find_all("li"):
            text = li.get_text(strip=True)
            if text:
                pros.append(text)

    cons_div: Tag | None = soup.find("div", class_="cons")  # type: ignore[assignment]
    if cons_div:
        for li in cons_div.find_all("li"):
            text = li.get_text(strip=True)
            if text:
                cons.append(text)

    if not pros_div and not cons_div:
        print("[warning] Pros/Cons section not found on this page.", file=sys.stderr)

    # About blurb — company description paragraph
    about: str | None = None
    about_tag = (
        soup.find("div", class_="company-profile")
        or soup.find("p", class_="about")
        or soup.find("section", id="about")
    )
    if about_tag:
        # Grab the first non-empty paragraph
        p = about_tag.find("p") if about_tag.name != "p" else about_tag
        about = _text(p) or None

    # Key metrics from the top-level company header
    # e.g. Market Cap, P/E, Book Value, Dividend Yield …
    key_metrics: dict[str, str] = {}
    # screener.in renders these in <ul class="company-ratios"> or similar
    for ul in soup.find_all("ul", id="top-ratios"):
        for li in ul.find_all("li"):
            name_tag = li.find("span", class_="name") or li.find("span")
            value_tag = li.find("span", class_="value") or li.find("strong")
            if name_tag and value_tag:
                key_metrics[name_tag.get_text(strip=True)] = value_tag.get_text(strip=True)

    return ProsConsData(pros=pros, cons=cons, about=about, key_metrics=key_metrics)
