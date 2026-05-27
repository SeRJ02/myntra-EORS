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
    "Title", "Description1", "Description2", "Description",
    "logo", "Image", "ButtonText", "Link", "CopyLink",
    "scraped_at", "category",
]
DEALS_CAP = 50
RUNS_HEADER = ["window_key", "count", "last_run_at"]

MYNTRA_LOGO = "https://asset21.ckassets.com/resources/image/stores/myntra-new-t-1777980142.png"
MYNTRA_COMMISSION = "Upto 8% profit"
BUTTON_TEXT = "Convert Link"
EARNKARO_LINK = "https://earnkaro.com/create-earn-link"


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
        ws = sheet.add_worksheet(title=title, rows=100, cols=max(15, len(header)))
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
        all_rows = ws.get_all_values()
        for i, row in enumerate(all_rows[1:], start=2):
            if row and row[0] == window_key:
                ws.update(
                    f"A{i}:C{i}",
                    [[window_key, int(counts[window_key]["count"]) + 1, now]],
                )
                return
    ws.append_row([window_key, 1, now], value_input_option="RAW")


# ---------- deals ----------

def _existing_keys(ws) -> set[tuple]:
    """(CopyLink, Description2) tuples already in deals (= product_url, sale_price)."""
    rows = ws.get_all_records()
    keys = set()
    for r in rows:
        url = r.get("CopyLink")
        price = r.get("Description2")
        if url:
            keys.add((url, price))
    return keys


def _to_row(deal: dict, scraped_at: str) -> list:
    return [
        deal.get("name"),            # Title
        deal.get("mrp"),             # Description1
        deal.get("sale_price"),      # Description2
        MYNTRA_COMMISSION,           # Description
        MYNTRA_LOGO,                 # logo
        deal.get("image_url"),       # Image
        BUTTON_TEXT,                 # ButtonText
        EARNKARO_LINK,               # Link
        deal.get("product_url"),     # CopyLink
        scraped_at,                  # scraped_at (hide in UI)
        deal.get("category"),        # category (hide in UI)
    ]


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
        new_values.append(_to_row(r, now))

    if not new_values:
        return 0

    ws.insert_rows(new_values, row=2, value_input_option="RAW")

    used_rows = len(ws.col_values(1))
    max_allowed = DEALS_CAP + 1
    if used_rows > max_allowed:
        ws.delete_rows(max_allowed + 1, used_rows)

    return len(new_values)
