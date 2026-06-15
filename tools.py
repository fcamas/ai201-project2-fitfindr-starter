"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    listings = load_listings()

    # Filter by price ceiling
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    # Filter by size — case-insensitive substring match so "M" hits "S/M"
    if size:
        size_lower = size.lower()
        listings = [l for l in listings if size_lower in l["size"].lower()]

    # Score each remaining listing by keyword overlap with description
    keywords = set(description.lower().split())

    def _score(listing: dict) -> int:
        # Build a single text blob from all searchable fields
        blob = " ".join([
            listing["title"],
            listing["description"],
            listing["category"],
            " ".join(listing["style_tags"]),
            " ".join(listing["colors"]),
            listing["brand"] or "",
        ]).lower()
        return sum(1 for kw in keywords if kw in blob)

    scored = [(s, l) for l in listings if (s := _score(l)) > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [l for _, l in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handled gracefully.

    Returns:
        A non-empty string with outfit suggestions or general styling advice.
    """
    try:
        client = _get_groq_client()
    except ValueError as e:
        return f"Outfit suggestion unavailable: {e}"

    item_desc = (
        f"{new_item['title']} "
        f"(${new_item['price']:.2f}, {new_item['condition']} condition, "
        f"colors: {', '.join(new_item['colors'])}, "
        f"style: {', '.join(new_item.get('style_tags', []))})"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            f"You are a fashion stylist. A customer is considering buying this "
            f"thrifted piece:\n\n{item_desc}\n\n"
            "They haven't shared their wardrobe yet. Suggest 1–2 outfit ideas "
            "that would work well with this item. Mention specific types of "
            "bottoms, shoes, and accessories that complement it, and describe "
            "the overall aesthetic/vibe. Be specific and practical, not generic."
        )
    else:
        wardrobe_lines = []
        for item in wardrobe_items:
            line = f"- {item['name']} ({', '.join(item['colors'])})"
            if item.get("notes"):
                line += f": {item['notes']}"
            wardrobe_lines.append(line)
        wardrobe_text = "\n".join(wardrobe_lines)

        prompt = (
            f"You are a fashion stylist. A customer found this thrifted piece "
            f"and wants outfit ideas using their existing wardrobe.\n\n"
            f"New item: {item_desc}\n\n"
            f"Their wardrobe:\n{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfit combinations using named pieces from "
            "the wardrobe above. For each outfit, describe the specific combination "
            "and the vibe/look it creates. Be concrete — reference actual item "
            "names from the wardrobe list."
        )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Outfit suggestion unavailable: try again or check your API key. ({e})"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message
        string — does NOT raise an exception.
    """
    if not outfit or not outfit.strip():
        return "Error: Cannot create a fit card without an outfit suggestion."

    try:
        client = _get_groq_client()
    except ValueError as e:
        return f"Fit card unavailable: {e}"

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
        f"Item found: {new_item['title']} — ${new_item['price']:.2f} on {new_item['platform']}\n"
        f"Outfit: {outfit}\n\n"
        "Style rules:\n"
        "- Write in lowercase, casual and conversational — sounds like a real person, not a brand\n"
        "- Mention the item name, price, and platform exactly once each, woven in naturally\n"
        "- Capture the specific vibe of this outfit (don't just say 'love this look')\n"
        "- 2–4 sentences total\n"
        "- Output only the caption — no hashtags, no intro like 'Caption:'"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.95,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Fit card unavailable: try again or check your API key. ({e})"
