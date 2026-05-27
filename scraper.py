"""Scrape Myntra category pages via Firecrawl /scrape, parse embedded JSON."""
from __future__ import annotations

import json
import os
import re

import requests

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"
TOP_N = 10

MYX_RE = re.compile(r"window\.__myx\s*=\s*")


def _extract_json_object(text: str, start: int) -> str:
    """Return the JSON object starting at text[start] (which must be '{'), respecting strings."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unterminated JSON object")


def _api_key() -> str:
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        raise RuntimeError("FIRECRAWL_API_KEY env var is not set")
    return key


def _fetch_html(url: str) -> str:
    r = requests.post(
        FIRECRAWL_URL,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        json={
            "url": url,
            "formats": ["rawHtml"],
            "onlyMainContent": False,
            "waitFor": 2000,
        },
        timeout=120,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"Firecrawl scrape failed: {body}")
    return (body.get("data") or {}).get("rawHtml") or ""


def _extract_products(html: str) -> list[dict]:
    m = MYX_RE.search(html)
    if not m:
        return []
    brace_idx = html.find("{", m.end())
    if brace_idx < 0:
        return []
    raw = _extract_json_object(html, brace_idx)
    state = json.loads(raw)
    search = state.get("searchData") or state.get("search") or {}
    results = (
        search.get("results", {}).get("products")
        or search.get("products")
        or []
    )
    return results


def _normalise(p: dict, category: str) -> dict:
    mrp = p.get("mrp")
    price = p.get("price") or p.get("discountedPrice") or mrp
    landing = p.get("landingPageUrl") or ""
    image = (
        p.get("searchImage")
        or p.get("image")
        or (p.get("images") or [{}])[0].get("src")
    )
    return {
        "category": category,
        "brand": p.get("brand"),
        "name": p.get("productName") or p.get("product"),
        "mrp": mrp,
        "sale_price": price,
        "product_url": f"https://www.myntra.com/{landing}" if landing else None,
        "image_url": image,
    }


def scrape_category(url: str, category: str) -> list[dict]:
    html = _fetch_html(url)
    products = _extract_products(html)[:TOP_N]
    return [_normalise(p, category) for p in products]
