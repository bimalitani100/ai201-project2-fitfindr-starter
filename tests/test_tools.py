# tests/test_tools.py
import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ──────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    # Impossible query → empty list, NOT an exception
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


# ── suggest_outfit ───────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe():
    # Empty wardrobe → still returns a non-empty string, no crash
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_outfit_with_wardrobe():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


# ── create_fit_card ──────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    # Empty outfit string → descriptive error string, NOT an exception
    item = {"title": "Test Tee", "price": 20.0, "platform": "depop"}
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_valid():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("Pair it with jeans and sneakers.", item)
    assert isinstance(result, str)
    assert len(result) > 0