"""Entry point: read schedule, scrape categories whose window is currently active."""
from __future__ import annotations

from datetime import datetime

from dateutil import parser, tz

from scraper import scrape_category
from sheets import append_deals, read_schedule

IST = tz.gettz("Asia/Kolkata")


def is_active(date: str, start_ts: str, end_ts: str, now: datetime) -> bool:
    """date is YYYY-MM-DD (IST). start_ts/end_ts may be HH:MM or full timestamps."""
    try:
        day = parser.parse(str(date)).date()
        start = parser.parse(f"{day} {start_ts}")
        end = parser.parse(f"{day} {end_ts}")
    except (ValueError, TypeError):
        return False
    start = start.replace(tzinfo=IST)
    end = end.replace(tzinfo=IST)
    return start <= now <= end


def main():
    now = datetime.now(tz=IST)
    schedule = read_schedule()
    print(f"Loaded {len(schedule)} schedule rows; now={now.isoformat()}")

    for row in schedule:
        name = row.get("category_name")
        url = row.get("url")
        if not url:
            continue
        if not is_active(row.get("date"), row.get("start_ts"), row.get("end_ts"), now):
            print(f"[{name}] outside window, skipping")
            continue
        print(f"[{name}] scraping {url}")
        try:
            deals = scrape_category(url, category=name)
        except Exception as e:
            print(f"[{name}] error: {e}")
            continue
        print(f"[{name}] got {len(deals)} products")
        append_deals(deals)


if __name__ == "__main__":
    main()
