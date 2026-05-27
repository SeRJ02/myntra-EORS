# Myntra EORS Deal Tracker

Scrapes Myntra category pages on a schedule (GitHub Actions cron) and appends each product's price snapshot to a Google Sheet. Driven entirely from a `schedule` tab in the sheet — no terminal needed.

## How it works

1. You maintain a `schedule` tab listing categories to watch and their sale windows.
2. A GitHub Actions cron runs `run.py` every 15 minutes.
3. For each row whose `start_ts ≤ now ≤ end_ts` (IST), the scraper hits Myntra's JSON gateway and appends rows to the `deals` tab.

## Setup (all in the browser)

### 1. Google Sheet
Create a sheet with two tabs:

**`schedule`** (header row exactly as below):

| category_name | url | date | start_ts | end_ts |
|---|---|---|---|---|
| Men Tshirts | https://www.myntra.com/men-tshirts | 2026-05-30 | 09:00 | 12:00 |
| Men Tshirts | https://www.myntra.com/men-tshirts | 2026-05-30 | 18:00 | 21:00 |
| Women Kurtas | https://www.myntra.com/women-kurtas | 2026-05-31 | 00:00 | 23:59 |

One row per (category, date, time-window). Add multiple rows for the same category to cover multiple days or multiple drops per day. All times are **IST**. `date` is `YYYY-MM-DD`; `start_ts` / `end_ts` are `HH:MM` (24h).

**`deals`** — leave empty, the script writes the header on first run.

Copy the sheet ID from the URL (`docs.google.com/spreadsheets/d/<SHEET_ID>/edit`).

### 2. Service account
1. Go to https://console.cloud.google.com → create a project.
2. APIs & Services → enable **Google Sheets API** and **Google Drive API**.
3. IAM & Admin → Service Accounts → Create → give any name → Done.
4. Open the service account → Keys → Add Key → JSON → download.
5. Copy the `client_email` from the JSON and share the sheet with that address (Editor).

### 3. GitHub secrets
Repo → Settings → Secrets and variables → Actions → New repository secret:
- `GCP_SA_KEY` → paste the entire JSON file contents
- `SHEET_ID` → the sheet ID from step 1

### 4. Enable Actions
Actions tab → enable workflows. The cron will start running automatically. Use **Run workflow** on `Scrape Myntra Deals` to trigger a test run.

## Columns written to `deals`

`scraped_at, category, product_id, brand, name, mrp, sale_price, discount_pct, rating, ratings_count, sizes, product_url`

Each run appends — so you get a time-series of prices across the sale window. Pivot in the sheet to see lowest price per product, biggest drops, etc.

## Notes

- GitHub cron is "best effort" and can drift a few minutes; fine for 15-min cadence.
- If Myntra starts blocking the JSON endpoint, the scraper will log HTTP errors. Fall back: switch `scraper.py` to Playwright (heavier, but renders as a real browser).
- All times in the sheet are interpreted as **IST**.
