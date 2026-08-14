from __future__ import annotations

import html
import json
import re
import unicodedata
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin


USER_AGENT = "Mozilla/5.0 (compatible; EventRadar/1.0; student-project)"


@dataclass
class ImportedEvent:
    title: str
    cat: str
    loc: str
    date_raw: str
    source: str
    source_url: str
    external_id: str
    description: str = ""
    details: str = ""
    poster: str | None = None
    price: str = ""

    def to_event_payload(self) -> dict[str, Any]:
        ticket = {"site": self.source, "url": self.source_url, "price": self.price or "See source"}
        return {
            "title": self.title,
            "cat": self.cat,
            "loc": self.loc,
            "dist": 0,
            "date_raw": self.date_raw,
            "description": self.description or f"{self.title} - imported from {self.source}.",
            "details": self.details or f"Ticket and schedule details were imported from {self.source}.",
            "poster": self.poster,
            "source": self.source,
            "status": "active",
            "icon": category_icon(self.cat),
            "tickets": json.dumps([ticket], ensure_ascii=False),
        }


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7"})
    with urllib.request.urlopen(req, timeout=18) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "ignore")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = unicodedata.normalize("NFKC", value)
    return " ".join(value.split()).strip()


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value or "event"


def category_icon(cat: str) -> str:
    return {"theater": "🎭", "cinema": "🎬", "sports": "⚽", "concerts": "🎸"}.get(cat, "📅")


def guess_category(*parts: str) -> str:
    text = " ".join(parts).lower()
    if any(word in text for word in ["tiyatro", "theater", "opera", "bale", "stand up", "stand-up", "sahne", "oyun"]):
        return "theater"
    if any(word in text for word in ["sinema", "film", "movie"]):
        return "cinema"
    if any(word in text for word in ["spor", "futbol", "basketbol", "voleybol", "sports", "match"]):
        return "sports"
    return "concerts"


MONTHS = {
    "ocak": 1,
    "january": 1,
    "şubat": 2,
    "subat": 2,
    "february": 2,
    "mart": 3,
    "march": 3,
    "nisan": 4,
    "april": 4,
    "mayıs": 5,
    "mayis": 5,
    "may": 5,
    "haziran": 6,
    "june": 6,
    "temmuz": 7,
    "july": 7,
    "ağustos": 8,
    "agustos": 8,
    "august": 8,
    "eylül": 9,
    "eylul": 9,
    "september": 9,
    "ekim": 10,
    "october": 10,
    "kasım": 11,
    "kasim": 11,
    "november": 11,
    "aralık": 12,
    "aralik": 12,
    "december": 12,
}


def parse_date(day: str, month: str, year: str | None = None, time_text: str | None = None) -> str | None:
    month_key = clean_text(month).lower()
    month_key = unicodedata.normalize("NFKD", month_key).encode("ascii", "ignore").decode("ascii")
    month_no = MONTHS.get(month_key) or MONTHS.get(clean_text(month).lower())
    if not month_no:
        return None
    hour, minute = 20, 0
    if time_text and re.search(r"\d{1,2}:\d{2}", time_text):
        hour, minute = [int(x) for x in re.search(r"(\d{1,2}):(\d{2})", time_text).groups()]
    now = datetime.now(timezone.utc)
    event_year = int(year or now.year)
    return datetime(event_year, month_no, int(day), hour, minute, tzinfo=timezone.utc).isoformat()


def parse_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def dedupe(events: list[ImportedEvent]) -> list[ImportedEvent]:
    seen: set[tuple[str, str]] = set()
    unique: list[ImportedEvent] = []
    for event in events:
        key = (event.source, event.external_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    return unique


def import_mobilet(limit: int = 40) -> list[ImportedEvent]:
    url = "https://mobilet.com/tr"
    page = fetch_url(url)
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page, re.S)
    if not match:
        return []
    data = json.loads(html.unescape(match.group(1)))
    event_nodes: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("eventName") and node.get("eventId"):
                event_nodes.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    events: list[ImportedEvent] = []
    for node in event_nodes:
        dates = node.get("eventDates") or []
        date_raw = parse_iso_date((dates[0] or {}).get("eventStartDate") if dates else None)
        if not date_raw:
            continue
        title = clean_text(str(node.get("eventName", "")))
        location_data = ((node.get("eventLocation") or {}).get("data") or {}).get("attributes") or {}
        loc = clean_text(location_data.get("locationName")) or "Istanbul"
        event_id = str(node.get("eventId"))
        image = find_first_image(node)
        source_url = f"https://mobilet.com/tr/event/{event_id}/"
        events.append(
            ImportedEvent(
                title=title,
                cat=guess_category(title, loc),
                loc=loc,
                date_raw=date_raw,
                source="Mobilet",
                source_url=source_url,
                external_id=event_id,
                poster=image,
                price="See Mobilet",
            )
        )
    return dedupe(events)[:limit]


def find_first_image(node: Any) -> str | None:
    if isinstance(node, dict):
        url = node.get("url")
        if isinstance(url, str) and url.startswith("http") and any(ext in url.lower() for ext in [".png", ".jpg", ".jpeg", ".webp"]):
            return url
        for value in node.values():
            found = find_first_image(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_first_image(value)
            if found:
                return found
    return None


def jsonld_nodes(page: str) -> list[Any]:
    nodes: list[Any] = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page,
        re.S | re.I,
    ):
        try:
            data = json.loads(html.unescape(raw).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            nodes.extend(data)
        else:
            nodes.append(data)
    return nodes


def walk_json_events(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        node_type = node.get("@type") or node.get("type")
        type_values = node_type if isinstance(node_type, list) else [node_type]
        if any(str(value).lower() == "event" for value in type_values) and node.get("name"):
            found.append(node)
        for value in node.values():
            found.extend(walk_json_events(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(walk_json_events(value))
    return found


def image_from_jsonld(value: Any) -> str | None:
    if isinstance(value, str):
        return value if value.startswith("http") else None
    if isinstance(value, list):
        for item in value:
            found = image_from_jsonld(item)
            if found:
                return found
    if isinstance(value, dict):
        return image_from_jsonld(value.get("url") or value.get("contentUrl"))
    return None


def location_from_jsonld(location: Any) -> str:
    if isinstance(location, str):
        return clean_text(location)
    if isinstance(location, dict):
        name = clean_text(location.get("name"))
        address = location.get("address")
        if isinstance(address, dict):
            address_text = clean_text(
                ", ".join(
                    str(address.get(key) or "")
                    for key in ["streetAddress", "addressLocality", "addressRegion"]
                    if address.get(key)
                )
            )
        else:
            address_text = clean_text(str(address or ""))
        return name or address_text
    return ""


def price_from_jsonld(offers: Any, fallback: str) -> str:
    offer = offers[0] if isinstance(offers, list) and offers else offers
    if isinstance(offer, dict):
        price = offer.get("price") or offer.get("lowPrice")
        currency = offer.get("priceCurrency") or "TL"
        if price:
            return clean_text(f"{price} {currency}")
    return fallback


def import_jsonld_source(source: str, url: str, limit: int = 30) -> list[ImportedEvent]:
    page = fetch_url(url)
    events: list[ImportedEvent] = []
    for root in jsonld_nodes(page):
        for item in walk_json_events(root):
            title = clean_text(item.get("name"))
            date_raw = parse_iso_date(item.get("startDate"))
            if not title or not date_raw:
                continue
            source_url = item.get("url") or url
            if isinstance(source_url, dict):
                source_url = source_url.get("@id") or url
            source_url = urljoin(url, str(source_url))
            loc = location_from_jsonld(item.get("location")) or "Istanbul"
            events.append(
                ImportedEvent(
                    title=title,
                    cat=guess_category(title, loc),
                    loc=loc,
                    date_raw=date_raw,
                    source=source,
                    source_url=source_url,
                    external_id=slugify(source + "-" + source_url + "-" + date_raw),
                    description=clean_text(item.get("description")),
                    details=clean_text(item.get("description")),
                    poster=image_from_jsonld(item.get("image")),
                    price=price_from_jsonld(item.get("offers"), f"See {source}"),
                )
            )
    return dedupe(events)[:limit]


def import_biletinial(limit: int = 40) -> list[ImportedEvent]:
    base = "https://biletinial.com"
    page = fetch_url(base + "/tr-tr/")
    blocks = re.findall(r'<a\b(?=[^>]*(?:splitItem|data-slider-item))[^>]*>.*?</a>', page, re.S | re.I)
    events: list[ImportedEvent] = []
    for block in blocks:
        href = attr(block, "href")
        title = clean_text(attr(block, "data-slider-item") or first_tag(block, "strong"))
        if not href or not title:
            continue
        loc = clean_text(first_tag(block, "span")) or "Istanbul"
        date_block = regex_one(r'<div[^>]*class="date"[^>]*>(.*?)</div>', block, re.S | re.I)
        spans = [clean_text(x) for x in re.findall(r"<span[^>]*>(.*?)</span>", date_block, re.S | re.I)]
        day_index = next((i for i, value in enumerate(spans) if re.fullmatch(r"\d{1,2}", value)), -1)
        if day_index < 0 or day_index + 1 >= len(spans):
            continue
        year = next((value for value in spans[day_index + 2 :] if re.fullmatch(r"\d{4}", value)), None)
        date_raw = parse_date(spans[day_index], spans[day_index + 1], year)
        if not date_raw:
            continue
        group = clean_text(attr(block, "data-slider-group"))
        img = attr(block, "src") or regex_one(r"background-image:url\((.*?)\)", block)
        source_url = urljoin(base, href)
        events.append(
            ImportedEvent(
                title=title,
                cat=guess_category(group, title, href),
                loc=loc,
                date_raw=date_raw,
                source="Biletinial",
                source_url=source_url,
                external_id=slugify(source_url),
                poster=img,
                price="See Biletinial",
            )
        )
    return dedupe(events)[:limit]


def import_biletix(limit: int = 30) -> list[ImportedEvent]:
    venue_urls = [
        ("https://www.biletix.com/mekan/340TQ/ISTANBUL/en", "Zorlu PSM - Turkcell Sahnesi"),
        ("https://www.biletix.com/mekan/340DB/ISTANBUL/en", "Zorlu PSM - Turkcell Platinum Sahnesi"),
        ("https://www.biletix.com/mekan/SS/ISTANBUL/en", "Ses 1885 - Ortaoyuncular Tiyatrosu"),
    ]
    events: list[ImportedEvent] = []
    for url, loc in venue_urls:
        try:
            page = fetch_url(url)
        except Exception:
            continue
        month_match = re.search(r'class="month".*?<p[^>]*>([A-Za-zğüşöçıİĞÜŞÖÇ]+)</p><p[^>]*>\s*&nbsp;\s*(\d{4})</p>', page, re.S)
        if not month_match:
            continue
        month, year = month_match.groups()
        day_blocks = re.findall(r'class="mat-menu-trigger day.*?(?=class="mat-menu-trigger day|</btx-calendar>)', page, re.S)
        for block in day_blocks:
            if "On sale" not in block:
                continue
            day = regex_one(r'class="Body-Bold"[^>]*>\s*(\d{1,2})\s*</p>', block)
            title = clean_text(regex_one(r'<li[^>]*class="[^"]*list[^"]*"[^>]*>\s*(.*?)\s*</li>', block))
            time_text = regex_one(r'<p[^>]*class="[^"]*bottom-right[^"]*"[^>]*>\s*(\d{1,2}:\d{2})', block)
            if not day or not title:
                continue
            date_raw = parse_date(day, month, year, time_text)
            if not date_raw:
                continue
            events.append(
                ImportedEvent(
                    title=title,
                    cat=guess_category(title, loc),
                    loc=loc,
                    date_raw=date_raw,
                    source="Biletix",
                    source_url=url,
                    external_id=slugify(url + "-" + title + "-" + date_raw),
                    price="See Biletix",
                )
            )
    return dedupe(events)[:limit]


def import_bubilet(limit: int = 30) -> list[ImportedEvent]:
    page = fetch_url("https://www.bubilet.com.tr/istanbul")
    card_pattern = re.compile(r'<a\b[^>]*href=["\'](/istanbul/etkinlik/[^"\']+)["\'][^>]*>.*?</a>', re.S | re.I)
    events: list[ImportedEvent] = []
    for match in card_pattern.finditer(page):
        block = match.group(0)
        href = match.group(1)
        title = clean_text(attr(block, "title") or first_tag(block, "h3"))
        paragraphs = [clean_text(p) for p in re.findall(r"<p\b[^>]*>(.*?)</p>", block, re.S | re.I)]
        loc = paragraphs[0] if paragraphs else "Istanbul"
        date_text = paragraphs[1] if len(paragraphs) > 1 else ""
        date_match = re.search(r"(\d{1,2})\s+([A-Za-zğüşöçıİĞÜŞÖÇ]+)", date_text)
        if not title or not date_match:
            continue
        date_raw = parse_date(date_match.group(1), date_match.group(2))
        if not date_raw:
            continue
        img = attr(block, "src")
        price = clean_text(regex_one(r'<span[^>]*class="[^"]*font-bold[^"]*"[^>]*>(.*?)</span>', block, re.S | re.I))
        source_url = urljoin("https://www.bubilet.com.tr", href)
        events.append(
            ImportedEvent(
                title=title,
                cat=guess_category(title, loc),
                loc=loc,
                date_raw=date_raw,
                source="Bubilet",
                source_url=source_url,
                external_id=slugify(source_url),
                poster=img,
                price=price or "See Bubilet",
            )
        )
    if events:
        return dedupe(events)[:limit]

    # Bubilet is rendered dynamically, but event cards still appear in React payloads on many builds.
    pattern = re.compile(
        r'"name"\s*:\s*"([^"]{3,120})".{0,500}?"startDate"\s*:\s*"([^"]+)".{0,500}?"location".{0,200}?"name"\s*:\s*"([^"]+)"',
        re.S,
    )
    for title, date_text, loc in pattern.findall(page):
        date_raw = parse_iso_date(date_text)
        if not date_raw:
            continue
        title = clean_text(title)
        loc = clean_text(loc) or "Istanbul"
        events.append(
            ImportedEvent(
                title=title,
                cat=guess_category(title, loc),
                loc=loc,
                date_raw=date_raw,
                source="Bubilet",
                source_url="https://www.bubilet.com.tr/istanbul",
                external_id=slugify("bubilet-" + title + "-" + date_raw),
                price="See Bubilet",
            )
        )
    return dedupe(events)[:limit]


def import_passo(limit: int = 30) -> list[ImportedEvent]:
    urls = [
        "https://www.passo.com.tr/tr/etkinlikler",
        "https://www.passo.com.tr/tr/etkinlik",
    ]
    events: list[ImportedEvent] = []
    for url in urls:
        try:
            events.extend(import_jsonld_source("Passo", url, limit))
        except Exception:
            continue
        if len(events) >= limit:
            break
    return dedupe(events)[:limit]


def import_ticketmaster(limit: int = 30) -> list[ImportedEvent]:
    urls = [
        "https://www.ticketmaster.com.tr/",
        "https://www.ticketmaster.com/discover/concerts",
    ]
    events: list[ImportedEvent] = []
    for url in urls:
        try:
            events.extend(import_jsonld_source("Ticketmaster", url, limit))
        except Exception:
            continue
        if len(events) >= limit:
            break
    return dedupe(events)[:limit]


def attr(block: str, name: str) -> str:
    return clean_text(regex_one(rf'{re.escape(name)}=["\'](.*?)["\']', block))


def first_tag(block: str, tag: str) -> str:
    return clean_text(regex_one(rf"<{tag}\b[^>]*>(.*?)</{tag}>", block, re.S | re.I))


def regex_one(pattern: str, text: str, flags: int = 0) -> str:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else ""


def fetch_all_sources(limit_per_source: int = 30) -> tuple[list[ImportedEvent], list[dict[str, str]]]:
    sources = [
        ("Mobilet", import_mobilet),
        ("Biletinial", import_biletinial),
        ("Biletix", import_biletix),
        ("Bubilet", import_bubilet),
        ("Passo", import_passo),
        ("Ticketmaster", import_ticketmaster),
    ]
    events: list[ImportedEvent] = []
    errors: list[dict[str, str]] = []
    for name, fn in sources:
        try:
            events.extend(fn(limit_per_source))
        except Exception as exc:
            errors.append({"source": name, "error": str(exc)})
    return dedupe(events), errors


def events_as_dicts(events: list[ImportedEvent]) -> list[dict[str, Any]]:
    return [asdict(event) for event in events]
