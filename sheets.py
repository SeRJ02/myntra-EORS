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
    "mrp", "sale_price", "product_url", "image_url",
]
DEALS_CAP = 50
RUNS_HEADER = ["window_key", "count", "last_run_at"]


def _client() -> gspread.Client:
    raw = os.environ["GCP_SA_KEY"]
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def open_sheet():
    return _client().open_by_key(os.environ["SHEET_ID"])


def read_schedule() -> list[dict]:
    ws = open_sheet().worksheet("schedule")
    return ws.get_all_records()


def _ensure_header(ws, header: list[str]):
    first_row = ws.row_values(1)
    if first_row != header:
        ws.update("A1", [header])


def _get_or_create_ws(sheet, title: str, header: list[str]):
    try:
        ws = sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=100, cols=max(10, len(header)))
    _ensure_header(ws, header)
    return ws


# ---------- runs counter ----------

def _run_counts(ws) -> dict[str, dict]:
    rows = ws.get_all_records()
    return {r["window_key"]: r for r in rows if r.get("window_key")}


def get_run_count(window_key: str) -> int:
    sheet = open_sheet()
    ws = _get_or_create_ws(sheet, "runs", RUNS_HEADER)
    rec = _run_counts(ws).get(window_key)
    return int(rec["count"]) if rec else 0


def bump_run_count(window_key: str):
    sheet = open_sheet()
    ws = _get_or_create_ws(sheet, "runs", RUNS_HEADER)
    counts = _run_counts(ws)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    if window_key in counts:
        # update existing row
        all_rows = ws.get_all_values()
        for i, row in enumerate(all_rows[1:], start=2):
            if row and row[0] == window_key:
                ws.update(f"A{i}:C{i}", [[window_key, int(counts[window_key]["count"]) + 1, now]])
                return
    ws.append_row([window_key, 1, now], value_input_option="RAW")


# ---------- deals ----------

def _existing_keys(ws) -> set[tuple]:
    """(product_url, sale_price) tuples already in deals."""
    rows = ws.get_all_records()
    keys = set()
    for r in rows:
        url = r.get("product_url")
        price = r.get("sale_price")
        if url:
            keys.add((url, price))
    return keys


def prepend_new_deals(rows: list[dict]):
    if not rows:
        return 0
    sheet = open_sheet()
    ws = _get_or_create_ws(sheet, "deals", DEALS_HEADER)
    existing = _existing_keys(ws)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    new_values = []
    for r in rows:
        key = (r.get("product_url"), r.get("sale_price"))
        if not key[0] or key in existing:
            continue
        existing.add(key)
        new_values.append([now] + [r.get(c) for c in DEALS_HEADER[1:]])

    if not new_values:
        return 0

    # Insert at row 2 (below header). insert_rows inserts BEFORE given index.
    ws.insert_rows(new_values, row=2, value_input_option="RAW")

    # Enforce cap: keep header + DEALS_CAP rows, delete the rest.
    total_rows = ws.row_count
    used_rows = len(ws.col_values(1))  # includes header
    max_allowed = DEALS_CAP + 1  # +1 for header
    if used_rows > max_allowed:
        ws.delete_rows(max_allowed + 1, used_rows)

    return len(new_values)
