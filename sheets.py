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
    info = json.loads(os.environ["GCP_SA_KEY"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _rupees(amount) -> str | None:
    if amount in (None, ""):
        return None
    return f"₹{amount}"


def _to_row(deal: dict, scraped_at: str) -> list:
    return [
        deal.get("name"),
        _rupees(deal.get("mrp")),
        _rupees(deal.get("sale_price")),
        MYNTRA_COMMISSION,
        MYNTRA_LOGO,
        deal.get("image_url"),
        BUTTON_TEXT,
        EARNKARO_LINK,
        deal.get("product_url"),
        scraped_at,
        deal.get("category"),
    ]


class SheetSession:
    """Open the sheet once, read all tabs upfront, batch writes at the end."""

    def __init__(self):
        self.sheet = _client().open_by_key(os.environ["SHEET_ID"])
        self._schedule_ws = self.sheet.worksheet("schedule")
        self._deals_ws = self._ensure_tab("Deals", DEALS_HEADER)
        self._runs_ws = self._ensure_tab("runs", RUNS_HEADER)

        self.schedule = self._schedule_ws.get_all_records()

        deal_rows = self._deals_ws.get_all_records()
        self._existing_deal_keys = {
            (r.get("CopyLink"), r.get("Description2"))
            for r in deal_rows
            if r.get("CopyLink")
        }
        self._existing_deal_count = len(deal_rows)

        run_rows = self._runs_ws.get_all_records()
        self._run_counts = {
            r["window_key"]: int(r["count"])
            for r in run_rows
            if r.get("window_key")
        }
        self._run_row_index = {
            r["window_key"]: i
            for i, r in enumerate(run_rows, start=2)
            if r.get("window_key")
        }

        self._new_deals: list[list] = []
        self._run_updates: dict[str, int] = {}

    def _ensure_tab(self, title: str, header: list[str]):
        try:
            ws = self.sheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self.sheet.add_worksheet(title=title, rows=100, cols=max(15, len(header)))
        first_row = ws.row_values(1)
        if first_row != header:
            ws.update("A1", [header])
        return ws

    def run_count(self, window_key: str) -> int:
        return self._run_counts.get(window_key, 0) + self._run_updates.get(window_key, 0)

    def stage_deals(self, deals: list[dict]) -> int:
        if not deals:
            return 0
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        added = 0
        for d in deals:
            key = (d.get("product_url"), _rupees(d.get("sale_price")))
            if not key[0] or key in self._existing_deal_keys:
                continue
            self._existing_deal_keys.add(key)
            self._new_deals.append(_to_row(d, now))
            added += 1
        return added

    def stage_run_bump(self, window_key: str):
        self._run_updates[window_key] = self._run_updates.get(window_key, 0) + 1

    def flush(self):
        """One batch write for deals + runs."""
        if self._new_deals:
            self._deals_ws.insert_rows(self._new_deals, row=2, value_input_option="RAW")
            used = len(self._deals_ws.col_values(1))
            max_allowed = DEALS_CAP + 1
            if used > max_allowed:
                self._deals_ws.delete_rows(max_allowed + 1, used)

        if self._run_updates:
            now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            updates = []
            appends = []
            for key, delta in self._run_updates.items():
                new_count = self._run_counts.get(key, 0) + delta
                if key in self._run_row_index:
                    i = self._run_row_index[key]
                    updates.append({"range": f"A{i}:C{i}", "values": [[key, new_count, now]]})
                else:
                    appends.append([key, new_count, now])
            if updates:
                self._runs_ws.batch_update(updates, value_input_option="RAW")
            if appends:
                self._runs_ws.append_rows(appends, value_input_option="RAW")
