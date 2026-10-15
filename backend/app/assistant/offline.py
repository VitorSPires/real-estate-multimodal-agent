"""A rule-based stand-in for the chat model, used in offline mode (no API key).

It understands just enough of the demo conversation — bedrooms, amenities, "good price?",
"compare" — to call the same tools a real model would and phrase their results. It exists so the
whole UI can be explored and tested without keys; it is not meant to be clever.
"""

import re

from app.assistant.tools import run_tool

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4}
AMENITY_WORDS = {
    "bbq_grill": ("bbq", "barbecue", "grill"),
    "pool": ("pool",),
    "gym": ("gym",),
    "gourmet_balcony": ("balcony",),
    "pet_friendly": ("pet", "dog", "cat"),
    "doorman": ("doorman", "concierge"),
    "elevator": ("elevator", "lift"),
}


def offline_reply(messages: list[dict]) -> tuple[str, list[dict]]:
    steps: list[dict] = []

    def call(tool: str, **arguments) -> dict:
        result = run_tool(tool, arguments)
        steps.append({"tool": tool, "arguments": arguments, "result": result})
        return result

    user_texts = [m["content"].lower() for m in messages if m["role"] == "user"]
    latest = user_texts[-1] if user_texts else ""
    criteria = _criteria(" ".join(user_texts))  # requirements accumulate over the conversation

    if any(word in latest for word in ("price", "deal", "worth", "expensive", "cheap")):
        target = _mentioned_listing(latest) or _last_single_match(criteria, call)
        if target:
            return _price_answer(call("neighborhood_price_check", listing=target)), steps

    if "compare" in latest:
        listings = [item["id"] for item in call("list_listings")["listings"]]
        rows = call("compare_listings", listings=listings)["comparison"]
        parts = [f"{r['title']}: {r['bedrooms']} bedrooms, {r['area_m2']} m², about {_money(r['price_usd'])}" for r in rows]
        return "Here they are side by side. " + "; ".join(parts) + ".", steps

    if not criteria:
        listings = call("list_listings")["listings"]
        if not listings:
            return "I don't have any documents yet. Drop the broker's files on the left, or try the sample documents.", steps
        names = ", ".join(f"{item['title']} in {item['neighborhood']}" for item in listings)
        return (f"I read your documents and found {len(listings)} apartments: {names}. "
                "What matters most to you — bedrooms, budget, amenities?"), steps

    result = call("filter_listings", **criteria)
    matches = result["matches"]
    if not matches:
        closest = result["excluded"][0] if result["excluded"] else None
        hint = f" The closest is {closest['title']} ({', '.join(closest['why_not'])})." if closest else ""
        return "None of the apartments meets all of that." + hint, steps
    if len(matches) > 1:
        names = _join([m["title"] for m in matches])
        return f"{len(matches)} options fit: {names}. Anything else that's a must-have for you?", steps

    best = matches[0]
    decisive = (criteria.get("required_amenities") or ["bedrooms"])[-1]
    call("show_evidence", listing=best["id"], field=decisive)
    reply = (f"Then {best['title']} in {best['neighborhood']} is the one: {best['bedrooms']} bedrooms, "
             f"{best['area_m2']} m², about {_money(best['price_usd'])}. I've opened the document that shows it.")
    if best["conflicts"]:
        reply += f" One thing to check: {best['conflicts'][0].split(': ', 1)[1]}."
    return reply, steps


def _criteria(text: str) -> dict:
    criteria: dict = {}
    bedrooms = re.search(r"(\d|one|two|three|four)\s*(?:\w+\s)?bed", text)
    if bedrooms:
        word = bedrooms.group(1)
        criteria["min_bedrooms"] = int(word) if word.isdigit() else NUMBER_WORDS[word]
    amenities = [key for key, words in AMENITY_WORDS.items() if any(w in text for w in words)]
    if amenities:
        criteria["required_amenities"] = amenities
    return criteria


def _mentioned_listing(text: str) -> str | None:
    for word in re.findall(r"[a-z]+", text):
        if len(word) > 4 and run_tool("get_listing", {"listing": word}).get("id"):
            return word
    return None


def _last_single_match(criteria: dict, call) -> str | None:
    if not criteria:
        return None
    matches = run_tool("filter_listings", criteria)["matches"]
    return matches[0]["id"] if len(matches) == 1 else None


def _price_answer(check: dict) -> str:
    if not check.get("available"):
        return check.get("reason", "I couldn't find price data for that neighborhood.")
    diff = check["difference_pct"]
    position = "below" if diff < 0 else "above"
    return (f"{check['listing']} costs about {_money(check['listing_price_per_m2'])} per m², {abs(diff)}% {position} "
            f"the {check['neighborhood']} average of {_money(check['neighborhood_avg_price_per_m2'])} in {check['year']}. "
            f"Prices there rose {check['trend_since_first_year_pct']}% over the period in the brochure's chart.")


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _money(value: int | None) -> str:
    if value is None:
        return "an unknown price"
    return f"{value / 1000:,.0f} thousand dollars" if value >= 10_000 else f"{value:,} dollars"
