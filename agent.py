"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Usage:
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex patterns.

    Returns a dict with keys: description (str), size (str|None), max_price (float|None).
    """
    text = query

    # Extract max_price — handles "under $30", "below $40", "max $50", "$25 or less"
    price_match = re.search(
        r'(?:under|below|max|less than|up to|<)\s*\$?\s*(\d+(?:\.\d+)?)',
        text, re.IGNORECASE,
    )
    if not price_match:
        # Also catch bare "$30" at end of phrase
        price_match = re.search(
            r'\$\s*(\d+(?:\.\d+)?)\s*(?:or less|max|maximum)?',
            text, re.IGNORECASE,
        )
    max_price = float(price_match.group(1)) if price_match else None

    # Extract size — handles "size M", "in size M", standalone XS/S/M/L/XL/XXL,
    # and numeric sizes like "size 8"
    size_match = re.search(
        r'(?:in\s+)?size\s+([A-Za-z0-9]+(?:/[A-Za-z0-9]+)?)',
        text, re.IGNORECASE,
    )
    if not size_match:
        size_match = re.search(
            r'\b(XXS|XS|S/M|M/L|XL/XXL|XL|XXL)\b',
            text, re.IGNORECASE,
        )
    size = size_match.group(1).upper() if size_match else None

    # Build description by removing the matched price/size fragments and filler words
    description = text
    for match in filter(None, [price_match, size_match]):
        # Replace the entire matched span (including trigger words) with a space
        start = match.start()
        # Walk back to include trigger words like "under", "size", "in size"
        description = description[:start] + " " + description[match.end():]

    # Remove common filler phrases and leftover symbols
    filler = r"\b(i'?m\s+looking\s+for|looking\s+for|find\s+me|i\s+want|" \
             r"under|below|size|in\s+size|in|a\s+|an\s+|the\s+|for\s+a\s+|" \
             r"for\s+an\s+|i\s+mostly\s+wear|mostly\s+wear|i\s+wear|" \
             r"what'?s?\s+out\s+there|how\s+would\s+i\s+style\s+it|" \
             r"style\s+it|what\s+is\s+out\s+there)\b"
    description = re.sub(filler, " ", description, flags=re.IGNORECASE)
    description = re.sub(r"[\$,\.\!\?]+", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    # Fall back to original query if parsing strips everything useful
    if len(description.split()) < 2:
        description = re.sub(r'\s+', ' ', query).strip()

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query into structured parameters
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Search listings — branch on whether results come back
    results = search_listings(
        parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        parts = [f'"{parsed["description"]}"']
        if parsed["size"]:
            parts.append(f"in size {parsed['size']}")
        if parsed["max_price"] is not None:
            parts.append(f"under ${parsed['max_price']:.0f}")
        session["error"] = (
            f"No listings found for {' '.join(parts)}. "
            "Try broadening your search: remove the size filter, raise your "
            "price limit, or use different keywords."
        )
        return session

    # Step 4: Select the top result
    session["selected_item"] = results[0]

    # Step 5: Generate outfit suggestion
    outfit = suggest_outfit(session["selected_item"], wardrobe)
    session["outfit_suggestion"] = outfit

    # Step 6: Generate fit card caption
    fit_card = create_fit_card(outfit, session["selected_item"])
    session["fit_card"] = fit_card

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
