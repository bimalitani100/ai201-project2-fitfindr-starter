# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

---

## Tool Inventory

### `search_listings(description, size, max_price)` -> `list[dict]`

**Inputs:**
- `description` (str): keywords describing the desired item (e.g. "vintage graphic tee"). Matched against each listing's `title`, `description`, and `style_tags`.
- `size` (str or None): size to filter by (e.g. "M"). Optional — if `None`, no size filter is applied. Matching is case-insensitive and lenient (substring), because sizes are not uniform across categories (tops use `S`/`M`/`L`, bottoms use formats like `W30 L30`).
- `max_price` (float or None): inclusive upper price bound. Optional — if `None`, no price filter is applied.

**Output:** a list of listing dicts (full listing shape: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`), sorted by relevance — the number of query keywords that appear in the listing's combined text. Returns an empty list `[]` if nothing matches.

**Purpose:** the entry point of every interaction; narrows 40 listings down to the most relevant matches under the user's constraints.

### `suggest_outfit(new_item, wardrobe)` -> `str`

**Inputs:**
- `new_item` (dict): a single listing dict (the item selected from `search_listings`).
- `wardrobe` (dict): a wardrobe dict with an `items` key holding a list of wardrobe-item dicts (each with `id`, `name`, `category`, `colors`, `style_tags`, `notes`). The list may be empty.

**Output:** a string with 1–2 outfit suggestions. With a populated wardrobe, the suggestion names specific pieces by their `name`. With an empty wardrobe, it returns general styling advice instead.

**Purpose:** turns a found item into a wearable outfit grounded in what the user already owns.

### `create_fit_card(outfit, new_item)` -> `str`

**Inputs:**
- `outfit` (str): the styling suggestion produced by `suggest_outfit`.
- `new_item` (dict): the listing dict, used to ground the caption in real details (name, price, platform).

**Output:** a short, casual, social-media-style caption (2–4 sentences) that mentions the item name, price, and platform once each. Generated at a higher LLM temperature so output varies across runs for the same input.

**Purpose:** produces the shareable end-product of the interaction — the kind of caption someone would post with an outfit photo.

---

## How the Planning Loop Works

The planning loop lives in `run_agent()` in `agent.py`. It does **not** call all three tools in a fixed sequence — it branches on what `search_listings` returns, which is what makes it an agent rather than a pipeline.

1. **Initialize** a fresh `session` dict.
2. **Parse** the natural-language query into `description`, `size`, and `max_price` using deterministic regex/string parsing (no LLM), so the same query always produces the same parameters.
3. **Search** by calling `search_listings` with the parsed parameters.
4. **Branch on the result — this is the key decision point:**
   - If `search_results` is **empty**: set `session["error"]` to a specific message telling the user what to adjust (raise the budget, drop the size filter, broaden the terms) and **return immediately**. `suggest_outfit` and `create_fit_card` are never called.
   - If `search_results` is **non-empty**: store the full list, select the top result as `selected_item`, and continue.
5. **Suggest an outfit** by passing `selected_item` and the wardrobe into `suggest_outfit`.
6. **Create the fit card** by passing the outfit suggestion and `selected_item` into `create_fit_card`.
7. **Return** the completed session.

The loop is "done" when `fit_card` is set (happy path) or when the empty-search branch returns early (error path). Because of step 4, the agent's behavior visibly changes with the input: matches -> all three tools run; no matches -> it stops after one.

---

## State Management

All state for one interaction lives in a single `session` dict created by `_new_session()` and owned by `run_agent()`. After each tool runs, its return value is written into the session; the next tool reads what it needs from the session, so the user never re-enters anything and no values are hardcoded between steps.

Fields tracked:
- `query` — the original user input
- `parsed` — the extracted `description` / `size` / `max_price`
- `search_results` — the full list returned by `search_listings`
- `selected_item` — `search_results[0]`; flows into **both** `suggest_outfit` and `create_fit_card`
- `outfit_suggestion` — the string from `suggest_outfit`; flows into `create_fit_card`
- `fit_card` — the string from `create_fit_card`
- `error` — a message string if the interaction ended early, otherwise `None`

The flow of state is verifiable: `session["selected_item"] is session["search_results"][0]` is `True` (the same object, not a copy), confirming the item found by search is the exact item passed to the outfit step.

---

## Error Handling

Each tool handles its own failure mode and returns a usable value rather than crashing or returning nothing.

| Tool | Failure mode | Response |
|------|-------------|----------|
| `search_listings` | No listings match the query | Returns `[]`. The planning loop detects this, sets a specific error message naming what to change, and stops before calling the other two tools. |
| `suggest_outfit` | Wardrobe is empty (or the LLM call errors) | If `wardrobe["items"]` is empty, returns general styling advice instead of naming specific pieces. If the API call fails, catches the exception and returns a fallback string so the found item still shows. |
| `create_fit_card` | `outfit` string is empty/missing (or the LLM call errors) | If `outfit` is empty or whitespace-only, returns a descriptive error string without calling the LLM. If the API call fails, returns a fallback caption built from the item's name, price, and platform. |

**Concrete example (from testing):** running the agent with the query `"designer ballgown size XXS under $5"` causes `search_listings` to return `[]`. The loop sets:

```
"No listings found for 'designer ballgown size XXS under $5' under $5 in size XXS.
 Try raising your budget, removing the size filter, or using broader terms."
```

and returns early — `outfit_suggestion` and `fit_card` both stay `None`, confirmed by an identity check. In the UI, only the "Top listing found" panel fills with this message; the outfit and fit-card panels stay empty.

---

## Spec Reflection

**One way the spec helped:** writing out the planning loop in `planning.md` as explicit conditional branches — "if `search_results` is empty, set the error and return; otherwise select `results[0]` and continue" — meant the implementation was almost a transcription. The early-exit branch existed in the spec before any code, so there was never a moment of building a fixed pipeline and retrofitting the branch.

**One way implementation diverged:** the spec described `search_listings` ranking by keyword overlap, which held up. But two refinements emerged only during implementation. First, inspecting the data revealed that sizes are not uniform across categories (`"M"` for a tee vs. `"W30 L30"` for jeans), so a strict equality size match would have silently dropped most of the catalog — the size filter became a lenient, case-insensitive substring match instead. Second, a stopword list was added so common words ("a", "the", "for") wouldn't inflate relevance scores. Neither was in the original spec; both came from working with the actual dataset.

---

## AI Usage

I used Claude as a coding assistant throughout, working one component at a time and verifying each output against my `planning.md` spec before trusting it.

**Instance 1 — `search_listings`:** I gave Claude the Tool 1 block from `planning.md` (inputs with types, return value, failure mode) and asked it to implement the function using `load_listings()` from the data loader. The generated code sorted results correctly, but I kept a specific detail it flagged: sorting by an explicit score key (`key=lambda pair: pair[0]`) rather than sorting raw `(score, item)` tuples, because tied scores would otherwise make Python try to compare the listing dicts and raise a `TypeError`. I verified the function against three test queries (happy path, impossible query, price filter) before moving on.

**Instance 2 — the planning loop (`run_agent`):** I gave Claude my architecture diagram plus the Planning Loop and State Management sections of `planning.md`, along with the `agent.py` stub, and asked it to implement the branching loop. Before trusting the result I verified two things myself with identity checks: that `selected_item is search_results[0]` (proving state flowed rather than being copied) and that on a no-results query, `fit_card` and `outfit_suggestion` both remained `None` (proving the early-exit branch actually skipped the downstream tools). Both passed, confirming the loop branched rather than running all three tools unconditionally.
