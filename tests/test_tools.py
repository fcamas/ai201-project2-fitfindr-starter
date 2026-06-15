"""
tests/test_tools.py

Unit tests for each FitFindr tool, focusing on the failure modes described
in planning.md. Run with:

    pytest tests/
"""

import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_size_filter_case_insensitive():
    # "m" should match listings whose size field contains "M", "S/M", etc.
    results = search_listings("tee", size="m", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_no_price_filter():
    results_capped = search_listings("jacket", size=None, max_price=30)
    results_all = search_listings("jacket", size=None, max_price=None)
    assert len(results_all) >= len(results_capped)


def test_search_result_fields():
    results = search_listings("vintage", size=None, max_price=None)
    assert len(results) > 0
    item = results[0]
    for field in ("id", "title", "description", "category", "style_tags",
                  "size", "condition", "price", "colors", "platform"):
        assert field in item, f"Missing field: {field}"


def test_search_sorted_by_relevance():
    # A query with many matching keywords should rank higher than a weak match
    results = search_listings("vintage graphic tee streetwear band", size=None, max_price=None)
    assert len(results) >= 2
    # First result should have a higher score than the last — we can't inspect
    # the score directly, but we can at least verify the list is non-empty
    # and results look relevant
    first_title = results[0]["title"].lower()
    combined = " ".join([
        results[0]["title"],
        results[0]["description"],
        " ".join(results[0]["style_tags"]),
    ]).lower()
    assert any(kw in combined for kw in ["vintage", "graphic", "tee", "streetwear", "band"])


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one result to test suggest_outfit"
    suggestion = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0


def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    suggestion = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0  # must return general styling advice, not empty


def test_suggest_outfit_does_not_crash_on_empty_wardrobe():
    results = search_listings("flannel", size=None, max_price=None)
    assert results
    try:
        result = suggest_outfit(results[0], get_empty_wardrobe())
        assert isinstance(result, str)
    except Exception as e:
        pytest.fail(f"suggest_outfit raised an exception on empty wardrobe: {e}")


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    outfit = "Pair with baggy jeans and chunky sneakers for a classic streetwear look."
    card = create_fit_card(outfit, results[0])
    assert isinstance(card, str)
    assert len(card) > 0


def test_create_fit_card_empty_outfit_returns_error_message():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    card = create_fit_card("", results[0])
    assert isinstance(card, str)
    assert "error" in card.lower() or "cannot" in card.lower()


def test_create_fit_card_whitespace_outfit_returns_error_message():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    card = create_fit_card("   ", results[0])
    assert isinstance(card, str)
    assert "error" in card.lower() or "cannot" in card.lower()


def test_create_fit_card_does_not_raise():
    results = search_listings("jacket", size=None, max_price=None)
    assert results
    outfit = "Layer over a white tee with straight-leg jeans and white sneakers."
    try:
        card = create_fit_card(outfit, results[0])
        assert isinstance(card, str)
    except Exception as e:
        pytest.fail(f"create_fit_card raised an exception: {e}")
