"""Scrape Myntra category pages via their internal JSON gateway."""
from __future__ import annotations

import re
import time
from urllib.parse import urlparse, parse_qs

import requests

GATEWAY = "https://www.myntra.com/gateway/v2/search/{slug}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.myntra.com/",
    "x-myntraweb": "Yes",
    "x-requested-with": "browser",
}


def slug_from_url(url: str) -> tuple[str, dict]:
    """Extract category slug + filter query params from a Myntra category URL."""
    parsed = urlparse(url)
    slug = parsed.path.strip("/")
    filters = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    return slug, filters


def fetch_page(slug: str, filters: dict, page: int, rows: int = 100) -> dict:
    params = {**filters, "p": page, "rows": rows, "o": (page - 1) * rows}
    r = requests.get(
        GATEWAY.format(slug=slug),
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("application/json"):
        snippet = r.text[:200].replace("\n", " ")
        raise RuntimeError(
            f"non-JSON response status={r.status_code} "
            f"ct={r.headers.get('content-type')} body={snippet!r}"
        )
    return r.json()


def normalise(p: dict, category: str) -> dict:
    pid = p.get("productId") or p.get("id")
    landing = p.get("landingPageUrl") or ""
    mrp = p.get("mrp")
    price = p.get("price") or p.get("discountedPrice") or mrp
    discount_pct = None
    if mrp and price and mrp > 0:
        discount_pct = round((1 - price / mrp) * 100, 1)
    sizes = ",".join(s for s in (p.get("sizes") or []))
    return {
        "category": category,
        "product_id": pid,
        "brand": p.get("brand"),
        "name": p.get("productName") or p.get("product"),
        "mrp": mrp,
        "sale_price": price,
        "discount_pct": discount_pct,
        "rating": p.get("rating"),
        "ratings_count": p.get("ratingCount"),
        "sizes": sizes,
        "product_url": f"https://www.myntra.com/{landing}" if landing else None,
    }


def scrape_category(url: str, category: str, max_pages: int = 20, sleep: float = 1.5) -> list[dict]:
    slug, filters = slug_from_url(url)
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        try:
            data = fetch_page(slug, filters, page)
        except requests.HTTPError as e:
            print(f"[{category}] page {page} HTTP {e.response.status_code}; stopping")
            break
        products = data.get("products") or []
        if not products:
            break
        out.extend(normalise(p, category) for p in products)
        total_count = data.get("totalCount") or 0
        if len(out) >= total_count:
            break
        time.sleep(sleep)
    return out
