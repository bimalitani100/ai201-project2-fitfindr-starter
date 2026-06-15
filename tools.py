"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

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
    # 1. Load all listings
    listings = load_listings()

    # Small stopword set so common words don't inflate relevance scores
    stopwords = {"a", "an", "the", "and", "or", "for", "with", "in",
                 "of", "to", "i", "my", "me", "is", "it"}
    query_words = [
        w for w in description.lower().split()
        if w not in stopwords and len(w) > 1
    ]

    scored = []
    for item in listings:
        # 2a. Price filter (inclusive)
        if max_price is not None and item["price"] > max_price:
            continue

        # 2b. Size filter — case-insensitive, lenient substring match.
        #     "M" matches "S/M" or "M"; won't match "W30 L30".
        if size is not None and size.lower() not in str(item["size"]).lower():
            continue

        # 3. Score by keyword overlap against title + description + style_tags
        haystack = " ".join([
            item["title"],
            item["description"],
            " ".join(item["style_tags"]),
        ]).lower()
        score = sum(1 for w in query_words if w in haystack)

        # 4. Drop listings with no keyword match
        if score > 0:
            scored.append((score, item))

    # 5. Sort by score, highest first; return just the listing dicts.
    #    (Sorting by the score key only — never compares the dicts.)
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    # Pull the item details we'll feed the model
    item_desc = (
        f"{new_item['title']} "
        f"(category: {new_item['category']}, "
        f"colors: {', '.join(new_item['colors'])}, "
        f"style: {', '.join(new_item['style_tags'])})"
    )

    items = wardrobe.get("items", [])

    # 1 + 2. Empty-wardrobe branch → general styling advice, no crash
    if not items:
        prompt = (
            f"A user is considering thrifting this item:\n{item_desc}\n\n"
            "They haven't told us what's already in their wardrobe. "
            "Suggest how to style this piece in general terms: what kinds of "
            "items pair well with it, what colors work, and what vibe or "
            "occasion it suits. Keep it to 2-3 sentences, casual and practical."
        )
    # 3. Non-empty branch → pair with specific named wardrobe pieces
    else:
        wardrobe_lines = "\n".join(
            f"- {w['name']} (category: {w['category']}, "
            f"colors: {', '.join(w['colors'])}, "
            f"style: {', '.join(w['style_tags'])})"
            for w in items
        )
        prompt = (
            f"A user is considering thrifting this item:\n{item_desc}\n\n"
            f"Here is their current wardrobe:\n{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfits that pair the new item with specific "
            "pieces from their wardrobe. Refer to the wardrobe pieces by name. "
            "Keep it to 2-3 sentences, casual and practical, like advice from "
            "a stylish friend."
        )

    # 4. Call the LLM; on any API error, return a graceful fallback string
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return (
            f"Couldn't generate a styling suggestion right now ({e}). "
            f"The item itself: {new_item['title']}, ${new_item['price']}."
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    # 1. Guard against an empty/whitespace-only outfit → return a string, never raise
    if not outfit or not outfit.strip():
        return (
            "Couldn't generate a fit card without outfit details. "
            "Try running the outfit suggestion step first."
        )

    # 2. Build the prompt with item details + the outfit to caption
    prompt = (
        "Write a short, fun social media caption (like an Instagram or TikTok "
        "OOTD post) for a thrifted outfit. Make it sound like a real person "
        "excited about a find — casual, authentic, NOT a product description.\n\n"
        f"The thrifted item: {new_item['title']}, ${new_item['price']}, "
        f"found on {new_item['platform']}.\n"
        f"The outfit: {outfit}\n\n"
        "Mention the item name, price, and platform naturally (once each). "
        "Keep it to 2-4 sentences. One emoji or two is fine."
    )

    # 3. Call the LLM at a higher temperature so captions vary run to run
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # Fallback caption built from item details if the API call fails
        return (
            f"thrifted this {new_item['title']} for ${new_item['price']} "
            f"on {new_item['platform']} and i'm obsessed 🛍️ "
            f"(caption generator hiccuped: {e})"
        )
