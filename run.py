"""Entry point: read schedule, scrape categories whose window is currently active."""
from __future__ import annotations

from datetime import datetime

from dateutil import parser, tz

from scraper import scrape_category
from sheets import bump_run_count, get_run_count, prepend_new_deals, read_schedule

IST = tz.gettz("Asia/Kolkata")
MAX_SCRAPES_PER_WINDOW = 2


def _parse_window(date: str, start_ts: str, end_ts: str):
    day = parser.parse(str(date)).date()
    start = parser.parse(f"{day} {start_ts}").replace(tzinfo=IST)
    end = parser.parse(f"{day} {end_ts}").replace(tzinfo=IST)
    return start, end


def _window_key(name: str, date: str, start_ts: str, end_ts: str) -> str:
    return f"{name}|{date}|{start_ts}|{end_ts}"


def main():
    now = datetime.now(tz=IST)
    schedule = read_schedule()
    print(f"Loaded {len(schedule)} schedule rows; now={now.isoformat()}")

    for row in schedule:
        name = row.get("category_name")
        url = row.get("url")
        if not url:
            continue
        try:
            start, end = _parse_window(row.get("date"), row.get("start_ts"), row.get("end_ts"))
        except (ValueError, TypeError):
            print(f"[{name}] bad date/time, skipping")
            continue
        if not (start <= now <= end):
            print(f"[{name}] outside window, skipping")
            continue

        key = _window_key(name, row.get("date"), row.get("start_ts"), row.get("end_ts"))
        count = get_run_count(key)
        if count >= MAX_SCRAPES_PER_WINDOW:
            print(f"[{name}] already scraped {count} times this window, skipping")
            continue

        print(f"[{name}] scraping {url} (run {count + 1}/{MAX_SCRAPES_PER_WINDOW})")
        try:
            deals = scrape_category(url, category=name)
        except Exception as e:
            print(f"[{name}] error: {e}")
            continue
        added = prepend_new_deals(deals)
        bump_run_count(key)
        print(f"[{name}] got {len(deals)} products, {added} new added to deals")


if __name__ == "__main__":
    main()
