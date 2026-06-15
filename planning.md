# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Filters the mock listings dataset down to items matching a free-text description,
an optional size, and a maximum price, and returns them ranked by relevance.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): Free-text of what the user wants, e.g. "vintage graphic tee". Matched against each listing's `title`, `description`, and `style_tags`.
- `size` (str): Desired size, e.g. "M". Optional — if `None`, no size filter
  is applied. (Sizes are not uniform across categories — tops use S/M/L, bottoms use formats like "W30 L30" — so size matching is lenient, not a strict equality check.)
- `max_price` (float): Inclusive upper price bound. Listings with `price > max_price` are excluded.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A list of listing dicts, sorted most-relevant first. Each dict has the full listing
shape from listings.json: `id`, `title`, `description`, `category`, `style_tags`,
`size`, `condition`, `price`, `colors`, `brand`, `platform`. Relevance = how many
query terms appear in the listing's combined text (title + description + style_tags);
higher overlap ranks higher. Returns an empty list `[]` if nothing matches — never
raises.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
Returns `[]`. The planning loop detects the empty list, sets an error message telling the user what to adjust (raise the budget, drop the size filter, or use broader terms), and stops — it does NOT call `suggest_outfit` with an empty item.
---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Given a found item and the user's current wardrobe, asks the LLM to compose a complete outfit pairing the new item with specific existing wardrobe pieces, and returns a short styling suggestion.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A single listing dict (the item selected from search_listings).The tool uses its `title`, `category`, `style_tags`, and `colors` to inform pairing.
- `wardrobe` (dict): The wardrobe, with key `items` (a list of wardrobe-item dicts, each with `id`, `name`, `category`, `colors`, `style_tags`, `notes`). The list may be empty.


**What it returns:**
<!-- Describe the return value -->
A string: a short styling suggestion that names specific wardrobe pieces (by their
`name`) and how to wear them — e.g. "Pair this with your baggy straight-leg jeans and chunky sneakers for a 90s-grunge look; tuck the front hem for shape."

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If `wardrobe['items']` is empty, the tool does NOT crash — it returns general styling advice for the item (what kinds of pieces to pair it with) instead of referencing specific wardrobe items. If the LLM call itself errors, it catches the exception and returns a graceful fallback string so the agent can still show the found item.
---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Generates a short, shareable, caption-style description of the complete look — the kind of thing someone would post with an outfit photo.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (...): The styling suggestion produced by suggest_outfit.
- `new_item` (dict): The listing dict, used to ground the caption in real details
  (item name, price, platform).
**What it returns:**
<!-- Describe the return value -->
A string: a short, social-caption-style fit card (1–2 sentences, casual tone). Generated at a higher LLM temperature so the output varies across runs for the same input.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If `outfit` is empty or falsy, the tool returns a descriptive error-message string (e.g."Couldn't generate a fit card without outfit details") rather than calling the LLM or raising. If the LLM call errors, it catches the exception and returns a simple fallback caption built from the item's details.
---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
The planning loop runs inside `run_agent()` and decides each next step by checking what the previous tool returned, not by running a fixed sequence:

1. Parse the user query into `description`, `size`, and `max_price`.
2. Call `search_listings(description, size, max_price)`.
3. Check the result:
   - If `results == []` (empty): set `session["error"]` to a message telling the user
     what to adjust, and RETURN immediately. `suggest_outfit` and `create_fit_card` are
     NOT called. This is the early-exit branch.
   - If `results` is non-empty: set `session["listings"] = results` and
     `session["selected_item"] = results[0]`, then proceed.
4. Call `suggest_outfit(session["selected_item"], wardrobe)` and store the returned
   string in `session["outfit_suggestion"]`. (suggest_outfit handles its own empty-
   wardrobe case internally, so the loop continues either way.)
5. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])` and
   store the result in `session["fit_card"]`.
6. Return `session`.

The loop is "done" when `session["fit_card"]` is set (happy path) or when the empty-search branch returns early (error path). The agent's behavior visibly changes based on the search result: matches → full three-tool flow; no matches → stop after one tool.
---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
State lives in a single `session` dict owned by `run_agent()` for the duration of one query. After each tool call, the loop writes the return value into the session; the next tool reads what it needs from the session — the user never re-enters anything, and no values are hardcoded between steps.

Fields tracked:
- `query` — the original user input / parsed parameters
- `listings` — the full list returned by search_listings
- `selected_item` — `results[0]`; flows into BOTH suggest_outfit and create_fit_card
- `outfit_suggestion` — the string from suggest_outfit; flows into create_fit_card
- `fit_card` — the string from create_fit_card
- `error` — a message string if a step short-circuits, otherwise `None`

The flow of state is the proof the agent works: `selected_item` found by search_listings is the exact same dict passed into suggest_outfit, and the `outfit_suggestion` string is the exact text passed into create_fit_card.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query |"No listings found for 'vintage graphic tee' under $30. Try raising your budget, removing the size filter, or using broader terms like 'tee'." → then stop; don't call suggest_outfit or create_fit_card. |
| suggest_outfit | Wardrobe is empty |If wardrobe['items'] is empty, return general styling advice instead of naming specific pieces ("Your wardrobe's empty, so here's how to style this generally: ..."); if the LLM call fails, return a fallback string so the found item still shows. |
| create_fit_card | Outfit input is missing or incomplete |If outfit is empty/falsy, return a descriptive string ("Couldn't generate a fit card without outfit details") instead of raising; if the LLM call fails, return a simple fallback caption built from the item's name, price, and platform. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

User query
("vintage graphic tee under $30, I wear baggy jeans + chunky sneakers")
    │
    ▼
Planning Loop  (run_agent in agent.py) ─────────────────────────────────────┐
    │                                                                       │
    │  parse → description, size, max_price                                 │
    │                                                                       │
    ├─► search_listings(description, size, max_price)                       │
    │       │                                                               │
    │       │ results == []                                                 │
    │       ├──► [ERROR] session["error"] = "No listings found — raise      │
    │       │            budget / drop size / broaden terms"  → RETURN      │
    │       │            (suggest_outfit & create_fit_card NOT called)      │
    │       │                                                               │
    │       │ results == [item, ...]                                        │
    │       ▼                                                               │
    │   Session: listings = results ;  selected_item = results[0]           │
    │       │                                                               │
    ├─► suggest_outfit(selected_item, wardrobe)                             │
    │       │   (empty wardrobe → general advice, no crash)                 │
    │       ▼                                                               │
    │   Session: outfit_suggestion = "..."                                  │
    │       │                                                               │
    └─► create_fit_card(outfit_suggestion, selected_item)                   │
            │   (empty outfit → error-message string, no crash)             │
            ▼                                                      error path returns here
        Session: fit_card = "..."
            │
            ▼
    Return session  →  app.py maps it to 3 panels:
                       [1] Found item   [2] Outfit suggestion   [3] Fit card

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
Tool: Claude. I'll paste each tool's block from the Tools section above — one tool at a time — including its inputs (with types), return value, and failure mode. For
search_listings I'll also tell it to use `load_listings()` from utils/data_loader.py(not re-open the file) and to treat `size` as optional since size formats vary across categories. I expect one function per tool in tools.py matching the stub signature. Before running each, I'll check: does it filter by all three parameters? does it return `[]` instead of crashing on no match? For the two LLM tools, does it call Groq llama-3.3-70b-versatile, read GROQ_API_KEY from .env, and handle the empty-wardrobe / empty-outfit cases? Then I'll run my pytest tests, and run create_fit_card 3× on the same input to confirm the output varies.
**Milestone 4 — Planning loop and state management:**
Tool: Claude. I'll give it the Architecture diagram plus the Planning Loop and State Management sections, and ask it to implement `run_agent()` in agent.py following the numbered TODOs. I expect a `session` dict that branches on the search_listings result (empty → set session["error"] and return early), stores selected_item / outfit_suggestion / fit_card across calls, and does NOT call all three tools unconditionally. Before trusting it I'll verify: the empty-search path leaves session["fit_card"] as None, and the selected_item passed into suggest_outfit is the same dict search returned. Then I'll implement handle_query() in app.py to map the session to the three output panels.
---

## A Complete Interaction (Step by Step)

FitFindr is a multi-tool agent that takes a natural-language thrifting
request — a description, a size, and a budget — and carries it all the way to a
shareable outfit. When the user describes what they're after, search_listings
filters the mock listings for matches and the agent picks the top one; that item
flows into suggest_outfit, which pairs it against the user's existing wardrobe to
propose a complete look; and the look plus the item flow into create_fit_card,
which writes a short caption-style description to post. If search_listings returns
no matches, the agent stops there and tells the user what to adjust — loosen the
budget, drop the size filter — instead of calling suggest_outfit with an empty item.


**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
The agent parses the query into search parameters: description="vintage graphic tee",
size=None (the user didn't give a size, so no size filter is applied), and
max_price=30.0. It calls search_listings("vintage graphic tee", size=None, max_price=30.0),
which filters the 40 listings down to those whose text/style match "vintage graphic tee"
and whose price is ≤ 30.0, returning a list of matching listing dicts sorted by relevance.
The agent stores the full list and selects the top result as selected_item — for example:
`{"id": "lst_0XX", "title": "Faded Band Tee", "category": "tops", "price": 22.0,
"style_tags": ["vintage", "grunge", "graphic"], "size": "M", "condition": "good",
"platform": "depop", ...}`. (Exact item depends on the dataset and ranking.)

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
Because Step 1 returned at least one match, the agent proceeds. It calls
suggest_outfit(new_item=selected_item, wardrobe=<user's wardrobe>), passing the band
tee from Step 1 and the user's wardrobe (the example wardrobe in testing, which includes
baggy denim and chunky sneakers — matching what the user described). The tool prompts the
LLM to pair the tee with real wardrobe pieces and returns a short styling suggestion string,
e.g. "Pair this faded band tee with your baggy straight-leg jeans and chunky sneakers for an
easy 90s-grunge look. Tuck the front hem slightly for shape." The agent stores this as
outfit_suggestion.
**Step 3:**
<!-- Continue until the full interaction is complete -->
The agent calls create_fit_card(outfit=outfit_suggestion, new_item=selected_item), passing
the styling suggestion and the item. The tool prompts the LLM (at a higher temperature, so
output varies run to run) to write a short, caption-style description suitable for a social
post, e.g. "found this faded band tee on depop for $22 and it's already my favorite — pairing
it with my baggy jeans + chunky sneakers all week 🖤". The agent stores this as fit_card.

**Final output to user:**
<!-- What does the user actually see at the end? -->
The user sees three things, mapped to the three output panels: (1) the item FitFindr found —
title, price, condition, platform; (2) the outfit suggestion from Step 2; and (3) the
shareable fit card from Step 3. If Step 1 had returned no matches instead, the user would see
only an error message explaining what to adjust (raise the budget or broaden the description),
and Steps 2 and 3 would never run
