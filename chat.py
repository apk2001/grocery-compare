"""Conversational layer for the WhatsApp-style grocery-compare chat.

A small per-session state machine:
  greet -> take grocery list -> search + compare -> show per-store totals
  -> user picks a store -> hand over a cart with deep links to that store.

It reuses the existing compare engine (agent1) and the AgenticOrg matcher.
`parse_list` is deliberately isolated so an AgenticOrg "parse" agent can be
dropped in later in place of the local heuristic.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from agent1 import agent1
from models import ListItem, Location

# --- session state (in-memory; fine for a demo, resets on restart) ---
SESSIONS: dict[str, dict] = {}

CITY_COORDS = {
    "chennai": (13.0827, 80.2707),
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "hyderabad": (17.3850, 78.4867),
    "pune": (18.5204, 73.8567),
}
DEFAULT_CITY = "chennai"

STORE_LABELS = {"zepto": "Zepto", "blinkit": "Blinkit", "instamart": "Swiggy Instamart"}

SIZE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:kg|g|gm|gms|grams?|l|ltr|litre|liter|ml|pcs?|pieces?|dozen)\b",
    re.I,
)
QTY_RE = re.compile(r"(?:x\s?(\d+)\b|\bx\s?(\d+)|\b(\d+)\s?(?:x|nos?|units?|packs?)\b)", re.I)


def _greeting() -> dict:
    return {
        "messages": [
            {"text": "👋 Hi! I'm your grocery price assistant."},
            {
                "text": (
                    "Send me your grocery list and I'll compare live prices across "
                    "quick-commerce apps, then help you buy from the cheapest.\n\n"
                    "For example:\n_milk 500ml x2, brown bread, eggs 6 pcs_\n\n"
                    f"📍 Using *{DEFAULT_CITY.title()}* by default — say _city: bangalore_ to change it."
                )
            },
        ]
    }


def parse_list(text: str) -> list[ListItem]:
    """Turn a free-text grocery list into structured items.

    Hook point: swap this for an AgenticOrg parse agent later. Keep the
    return type (list[ListItem]) the same and the rest of the flow works.
    """
    chunks = re.split(r"[,\n;]+", text)
    items: list[ListItem] = []
    for raw in chunks:
        chunk = raw.strip()
        if not chunk:
            continue
        size_m = SIZE_RE.search(chunk)
        size_hint = size_m.group(0).strip() if size_m else None
        rest = SIZE_RE.sub(" ", chunk) if size_m else chunk
        qty = 1
        qty_m = QTY_RE.search(rest)
        if qty_m:
            qty = int(next(g for g in qty_m.groups() if g))
            rest = QTY_RE.sub(" ", rest)
        query = re.sub(r"\s+", " ", rest).strip(" -*")
        if not query:
            continue
        items.append(ListItem(id=f"i{len(items) + 1}", query=query, qty=qty, size_hint=size_hint))
    return items


def _location(city: str) -> Location:
    lat, lng = CITY_COORDS.get(city, CITY_COORDS[DEFAULT_CITY])
    return Location(lat=lat, lng=lng, city=city)


def _store_search_url(platform: str, query: str) -> str:
    q = quote(query)
    if platform == "instamart":
        return f"https://www.swiggy.com/instamart/search?custom_back=true&query={q}"
    if platform == "blinkit":
        return f"https://blinkit.com/s/?q={q}"
    return f"https://www.zeptonow.com/search?query={q}"


def _found_count(r) -> int:
    return sum(1 for it in r.items if it.sku_id)


def _format_results(results) -> dict:
    """Build the comparison message + per-store choice buttons.

    Only include stores that actually matched at least one item, so a store
    blocked by the Apify free plan (pay-per-event) is hidden rather than shown
    as an empty ₹0 cart.
    """
    ok = [r for r in results if r.error is None and _found_count(r) > 0]
    if not ok:
        return {
            "messages": [
                {"text": "😕 I couldn't find prices for that list right now. Try different wording, or send the list again."}
            ]
        }
    # Best = most items found, then cheapest.
    ranked = sorted(ok, key=lambda r: (len(r.missing), r.subtotal))
    best = ranked[0]

    lines = ["💰 *Price comparison*\n"]
    for i, r in enumerate(ranked):
        label = STORE_LABELS.get(r.platform, r.platform.title())
        tag = "  ✅ best pick" if i == 0 and len(ranked) > 1 else ""
        lines.append(f"*{label}* — ₹{r.subtotal:.0f}  ({_found_count(r)}/{len(r.items)} items){tag}")
    # Only claim a saving against a store covering the SAME number of items (apples-to-apples).
    same = [r for r in ranked[1:] if len(r.missing) == len(best.missing)]
    if same:
        saving = same[0].subtotal - best.subtotal
        if saving > 0:
            lines.append(f"\n{STORE_LABELS.get(best.platform, best.platform.title())} is cheaper by ₹{saving:.0f} for the same items.")
    lines.append("\nWhich store do you want to buy from?")

    buttons = [
        {"label": f"{STORE_LABELS.get(r.platform, r.platform.title())} · ₹{r.subtotal:.0f}", "value": f"choose:{r.platform}"}
        for r in ranked
    ]
    return {"messages": [{"text": "\n".join(lines), "buttons": buttons}]}


def _format_cart(result) -> dict:
    label = STORE_LABELS.get(result.platform, result.platform.title())
    lines = [f"🛒 *Your cart on {label}* — ₹{result.subtotal:.0f}\n"]
    links = []
    for it in result.items:
        if it.sku_id and it.name:
            lines.append(f"• {it.name} — ₹{it.unit_price:.0f} × {it.qty}")
            links.append({"label": f"Open: {it.name[:28]}", "url": _store_search_url(result.platform, it.name)})
        else:
            lines.append("• _(no match for one item — add it manually)_")
    if result.missing:
        lines.append(f"\n⚠️ {len(result.missing)} item(s) had no match.")
    lines.append(
        f"\nTap each product to open it in {label}, add it to your cart, then pay in the app."
    )
    return {
        "messages": [
            {"text": "\n".join(lines), "links": links},
            {
                "text": f"👉 Open {label} to review and pay:",
                "links": [{"label": f"Open {label}", "url": _store_search_url(result.platform, result.items[0].name if result.items else "")}],
            },
            {"text": "Want to compare another list? Just send it. 🙂"},
        ]
    }


async def handle(session_id: str, text: str) -> dict:
    text = (text or "").strip()
    sess = SESSIONS.setdefault(session_id, {"city": DEFAULT_CITY, "stage": "start", "last": None})

    low = text.lower()
    if low in ("__start__", "", "hi", "hello", "hey", "start"):
        sess["stage"] = "await_list"
        return _greeting()

    if low in ("reset", "new", "new list", "restart"):
        sess["stage"] = "await_list"
        return {"messages": [{"text": "Fresh start! 🧹 Send me your grocery list."}]}

    m = re.match(r"city\s*[:=]\s*(.+)", low)
    if m:
        city = m.group(1).strip()
        sess["city"] = city if city in CITY_COORDS else DEFAULT_CITY
        used = sess["city"].title()
        note = "" if city in CITY_COORDS else f" (I don't have {city.title()} yet, using {used})"
        return {"messages": [{"text": f"📍 Location set to *{used}*{note}. Now send your grocery list."}]}

    # Picking a store after a comparison
    if low.startswith("choose:") or (sess.get("stage") == "chosen_pending"):
        platform = low.split("choose:", 1)[1].strip() if low.startswith("choose:") else low
        results = sess.get("last") or []
        match = next((r for r in results if r.platform == platform or STORE_LABELS.get(r.platform, "").lower() == platform), None)
        if match is None and len(results) == 1:
            match = results[0]
        if match is None:
            names = ", ".join(STORE_LABELS.get(r.platform, r.platform.title()) for r in results if r.error is None)
            sess["stage"] = "chosen_pending"
            return {"messages": [{"text": f"Please pick one of: {names}."}]}
        sess["stage"] = "await_list"
        return _format_cart(match)

    # Otherwise: treat the message as a grocery list
    items = parse_list(text)
    if not items:
        return {"messages": [{"text": "Hmm, I couldn't read a grocery list there. Try: _milk 500ml x2, eggs 6 pcs, bread_"}]}

    loc = _location(sess["city"])
    results = await agent1(items, loc)
    sess["last"] = results
    sess["stage"] = "chosen_pending"
    summary = {"text": f"🔎 Searching {len(items)} item(s) in {sess['city'].title()}…"}
    out = _format_results(results)
    out["messages"] = [summary] + out["messages"]
    return out
