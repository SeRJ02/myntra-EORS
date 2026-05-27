"""Scrape Myntra category pages via Firecrawl's /extract endpoint."""
from __future__ import annotations

import os
import time

import requests

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/extract"
TOP_N = 10

SCHEMA = {
    "type": "object",
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string"},
                    "name": {"type": "string"},
                    "mrp": {"type": "number"},
                    "sale_price": {"type": "number"},
                    "discount_pct": {"type": "number"},
                    "rating": {"type": "number"},
                    "product_url": {"type": "string"},
                },
                "required": ["brand", "name", "sale_price", "product_url"],
            },
        }
    },
    "required": ["products"],
}

PROMPT = (
    f"Extract the top {TOP_N} discounted products visible on this Myntra category page. "
    "For each product return brand, product name, MRP (original price in INR), "
    "sale_price (current discounted price in INR), discount_pct (percentage off), "
    "rating (out of 5), and product_url (absolute URL). "
    f"Return at most {TOP_N} products, ordered as shown on the page."
)


def _api_key() -> str:
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        raise RuntimeError("FIRECRAWL_API_KEY env var is not set")
    return key


def _start_extract(url: str) -> str:
    r = requests.post(
        FIRECRAWL_URL,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        json={"urls": [url], "schema": SCHEMA, "prompt": PROMPT},
        timeout=60,
    )
    r.raise_for_status()
    body = r.json()
    job_id = body.get("id")
    if not job_id:
        raise RuntimeError(f"Firecrawl did not return job id: {body}")
    return job_id


def _poll(job_id: str, timeout_s: int = 180) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = requests.get(
            f"{FIRECRAWL_URL}/{job_id}",
            headers={"Authorization": f"Bearer {_api_key()}"},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        status = body.get("status")
        if status == "completed":
            return body.get("data") or {}
        if status in ("failed", "cancelled"):
            raise RuntimeError(f"Firecrawl job {status}: {body}")
        time.sleep(3)
    raise RuntimeError(f"Firecrawl job {job_id} timed out after {timeout_s}s")


def scrape_category(url: str, category: str) -> list[dict]:
    job_id = _start_extract(url)
    data = _poll(job_id)
    products = (data.get("products") or [])[:TOP_N]
    return [
        {
            "category": category,
            "product_id": None,
            "brand": p.get("brand"),
            "name": p.get("name"),
            "mrp": p.get("mrp"),
            "sale_price": p.get("sale_price"),
            "discount_pct": p.get("discount_pct"),
            "rating": p.get("rating"),
            "ratings_count": None,
            "sizes": None,
            "product_url": p.get("product_url"),
        }
        for p in products
    ]
