from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from scrapling.fetchers import StealthyFetcher


@dataclass(frozen=True)
class Config:
    bark_base_url: str
    bark_key: str
    bark_group: str
    urls_file: Path
    state_file: Path


@dataclass(frozen=True)
class Drop:
    title: str
    url: str
    old_price: str
    new_price: str
    delta: float
    delta_pct: float


def load_config() -> Config:
    load_dotenv()
    bark_key = os.getenv("BARK_KEY", "").strip()
    if not bark_key or bark_key == "your_device_key_here":
        raise SystemExit("BARK_KEY not configured in .env")
    return Config(
        bark_base_url=os.getenv("BARK_BASE_URL", "https://bark.troublesis.win").rstrip("/"),
        bark_key=bark_key,
        bark_group=os.getenv("BARK_GROUP", "Coles Price Tracker"),
        urls_file=Path(os.getenv("URLS_FILE", "urls.txt")),
        state_file=Path(os.getenv("STATE_FILE", "state.json")),
    )


def _first_text(page, selectors: list[str]) -> str | None:
    for sel in selectors:
        value = page.css(sel).get()
        if value:
            return value.strip()
    return None


def parse_price_value(price_str: str | None) -> float | None:
    if not price_str:
        return None
    match = re.search(r"\$?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)", price_str)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def fetch_coles_product(url: str) -> dict:
    page = StealthyFetcher.fetch(
        url,
        headless=True,
        solve_cloudflare=True,
        network_idle=True,
        google_search=False,
    )
    if page.status != 200:
        raise RuntimeError(f"Failed to fetch {url}: status={page.status}")

    title = _first_text(
        page,
        [
            "h1[data-testid='product-title']::text",
            "h1.product__title::text",
            "h1::text",
        ],
    )
    price = _first_text(
        page,
        [
            "[data-testid='product-pricing'] .price__value::text",
            "[data-testid='product-price']::text",
            ".price__value::text",
            "span.price::text",
        ],
    )
    unit_price = _first_text(
        page,
        [
            "[data-testid='unit-price']::text",
            ".price__calculation_method::text",
        ],
    )

    now = datetime.now().astimezone()
    return {
        "url": url,
        "title": title,
        "price": price,
        "price_value": parse_price_value(price),
        "unit_price": unit_price,
        "checked_date": now.strftime("%Y-%m-%d"),
        "checked_time": now.strftime("%H:%M:%S"),
        "checked_at": now.isoformat(timespec="seconds"),
    }


def load_state(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: Path, state: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_urls(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"URLs file not found: {path}")
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    if not urls:
        raise SystemExit(f"No URLs found in {path}")
    return urls


def check_urls(config: Config) -> tuple[list[Drop], dict]:
    urls = read_urls(config.urls_file)
    state = load_state(config.state_file)
    drops: list[Drop] = []

    for url in urls:
        try:
            info = fetch_coles_product(url)
        except Exception as exc:
            print(f"✗ {url} — {exc}", file=sys.stderr)
            continue

        previous = state.get(url, {})
        prev_value = previous.get("price_value")
        prev_price = previous.get("price")

        new_value = info["price_value"]
        new_price = info["price"]

        if (
            prev_value is not None
            and new_value is not None
            and new_value < prev_value
        ):
            delta = new_value - prev_value
            delta_pct = (delta / prev_value) * 100.0
            drops.append(
                Drop(
                    title=info.get("title") or url,
                    url=url,
                    old_price=prev_price or f"${prev_value:.2f}",
                    new_price=new_price or f"${new_value:.2f}",
                    delta=delta,
                    delta_pct=delta_pct,
                )
            )

        info["previous_price"] = prev_price
        state[url] = info

        prev_note = f" (was {prev_price})" if prev_price else ""
        print(f"✓ {info.get('title') or url} — {new_price}{prev_note}")

    return drops, state


def format_summary(drops: list[Drop]) -> tuple[str, str]:
    title = f"Coles: {len(drops)} price drop{'s' if len(drops) != 1 else ''}"
    lines: list[str] = []
    for d in drops:
        lines.append(f"📉 {d.title}")
        lines.append(
            f"   {d.old_price} → {d.new_price} "
            f"(−${abs(d.delta):.2f}, {d.delta_pct:+.1f}%)"
        )
    return title, "\n".join(lines)


def send_bark_notification(config: Config, drops: list[Drop]) -> None:
    if not drops:
        return
    title, body = format_summary(drops)
    payload = {
        "title": title,
        "body": body,
        "group": config.bark_group,
        "level": "active",
    }
    endpoint = f"{config.bark_base_url}/{config.bark_key}"
    response = httpx.post(endpoint, json=payload, timeout=15.0)
    response.raise_for_status()
    print(f"→ Bark notified: {title}")


def main() -> None:
    config = load_config()
    drops, state = check_urls(config)
    save_state(config.state_file, state)

    if drops:
        send_bark_notification(config, drops)
        print(f"{len(drops)} drop(s) detected")
    else:
        print("No price drops")


if __name__ == "__main__":
    main()
