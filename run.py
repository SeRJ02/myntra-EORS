"""Entry point: read schedule, scrape categories whose window is currently active."""
from __future__ import annotations

from datetime import datetime

from dateutil import parser, tz

from scraper import scrape_category
from sheets import SheetSession

IST = tz.gettz("Asia/Kolkata")
MAX_SCRAPES_PER_WINDOW = 2


def _parse_window(date, start_ts, end_ts):
    day = parser.parse(str(date)).date()
    start = parser.parse(f"{day} {start_ts}").replace(tzinfo=IST)
    end = parser.parse(f"{day} {end_ts}").replace(tzinfo=IST)
    return start, end


def _window_key(name, date, start_ts, end_ts) -> str:
    return f"{name}|{date}|{start_ts}|{end_ts}"


def main():
    now = datetime.now(tz=IST)
    s = SheetSession()
    print(f"Loaded {len(s.schedule)} schedule rows; now={now.isoformat()}")

    for row in s.schedule:
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
        count = s.run_count(key)
        if count >= MAX_SCRAPES_PER_WINDOW:
            print(f"[{name}] already scraped {count} times this window, skipping")
            continue

        print(f"[{name}] scraping {url} (run {count + 1}/{MAX_SCRAPES_PER_WINDOW})")
        try:
            deals = scrape_category(url, category=name)
        except Exception as e:
            print(f"[{name}] error: {e}")
            continue
        added = s.stage_deals(deals)
        s.stage_run_bump(key)
        print(f"[{name}] got {len(deals)} products, {added} new staged")

    s.flush()
    print("flushed batch writes")


if __name__ == "__main__":
    main()
