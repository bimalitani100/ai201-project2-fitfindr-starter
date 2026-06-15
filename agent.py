"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize and return a fresh session dict for one user interaction."""
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


# ── query parsing ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract search parameters from a natural-language query.
    Deterministic regex/string parsing (no LLM) so results are predictable.
    Returns: {"description": str, "size": str|None, "max_price": float|None}
    """
    q = query.lower()

    # max_price: "$30", "under 30", "below $25", etc.
    max_price = None
    price_match = re.search(r"\$?\s*(\d+(?:\.\d+)?)", q)
    if price_match:
        max_price = float(price_match.group(1))

    # size: "size M", "size 9", "in size L"
    size = None
    size_match = re.search(r"size\s+([a-z0-9]+)", q)
    if size_match:
        size = size_match.group(1).upper()

    # description: the whole query works as keywords — search_listings
    # scores by overlap and filters noise words via its own stopword list.
    description = query

    return {"description": description, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """Run the FitFindr planning loop for one interaction; return the session."""
    # Step 1: fresh session
    session = _new_session(query, wardrobe)

    # Step 2: parse the query into search parameters
    session["parsed"] = _parse_query(query)
    parsed = session["parsed"]

    # Step 3: search
    session["search_results"] = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )

    # --- BRANCH: no results -> set error and exit early. The two LLM tools
    #     are NOT called. This is what makes the loop an agent, not a pipeline.
    if not session["search_results"]:
        price_note = f" under ${parsed['max_price']:.0f}" if parsed["max_price"] else ""
        size_note = f" in size {parsed['size']}" if parsed["size"] else ""
        session["error"] = (
            f"No listings found for '{parsed['description']}'{price_note}{size_note}. "
            "Try raising your budget, removing the size filter, or using broader terms."
        )
        return session

    # Step 4: select the top result
    session["selected_item"] = session["search_results"][0]

    # Step 5: suggest an outfit (handles empty wardrobe internally)
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], session["wardrobe"]
    )

    # Step 6: create the fit card
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: done
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