"""Scrape Myntra category pages via Firecrawl /scrape, parse embedded JSON."""
from __future__ import annotations

import json
import os
import re

import requests

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"
TOP_N = 10

MYX_RE = re.compile(r"window\.__myx\s*=\s*(\{.*?\});", re.DOTALL)


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
    state = json.loads(m.group(1))
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
    discount_pct = None
    if mrp and price and mrp > 0:
        discount_pct = round((1 - price / mrp) * 100, 1)
    landing = p.get("landingPageUrl") or ""
    return {
        "category": category,
        "brand": p.get("brand"),
        "name": p.get("productName") or p.get("product"),
        "mrp": mrp,
        "sale_price": price,
        "discount_pct": discount_pct,
        "rating": p.get("rating"),
        "product_url": f"https://www.myntra.com/{landing}" if landing else None,
    }


def scrape_category(url: str, category: str) -> list[dict]:
    html = _fetch_html(url)
    products = _extract_products(html)[:TOP_N]
    return [_normalise(p, category) for p in products]
