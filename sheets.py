"""Google Sheets I/O via a service account."""
from __future__ import annotations

import json
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DEALS_HEADER = [
    "scraped_at", "category", "brand", "name",
    "mrp", "sale_price", "discount_pct", "rating", "product_url",
]


def _client() -> gspread.Client:
    raw = os.environ["GCP_SA_KEY"]
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def open_sheet():
    return _client().open_by_key(os.environ["SHEET_ID"])


def read_schedule() -> list[dict]:
    """schedule tab columns: category_name | url | start_ts | end_ts (IST, ISO format)."""
    ws = open_sheet().worksheet("schedule")
    rows = ws.get_all_records()
    return rows


def ensure_deals_header(ws):
    first_row = ws.row_values(1)
    if first_row != DEALS_HEADER:
        ws.update("A1", [DEALS_HEADER])


def append_deals(rows: list[dict]):
    if not rows:
        return
    ws = open_sheet().worksheet("deals")
    ensure_deals_header(ws)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    values = [
        [now] + [r.get(col) for col in DEALS_HEADER[1:]]
        for r in rows
    ]
    ws.append_rows(values, value_input_option="RAW")
