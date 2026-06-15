# FitFindr

A multi-tool AI agent that helps users find secondhand clothing pieces and figure out how to wear them. You describe what you want in plain English; FitFindr searches the listings, suggests an outfit, and writes a shareable caption — or tells you exactly what to change if nothing comes up.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
```

Create a `.env` file in the project root (never commit this):

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Open the URL shown in your terminal (typically http://localhost:7860).

Run the tests:

```bash
pytest tests/
```

---

## Tool Inventory

### 1. search\_listings

**Signature:** `search_listings(description: str, size: str | None, max_price: float | None) -> list[dict]`

**Purpose:** Searches the mock listings dataset for secondhand items that match the user's request. Filters by price and size first, then ranks remaining items by keyword relevance.

**Inputs:**

| Parameter | Type | Meaning |
|-----------|------|---------|
| description | str | Keywords describing the item (e.g., "vintage graphic tee") |
| size | str or None | Size to filter by, case-insensitive substring match against the listing size field. "M" matches "S/M". None skips size filtering. |
| max_price | float or None | Maximum price inclusive. None skips price filtering. |

**Output:** A list of listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. Returns `[]` on no match — never raises an exception.

---

### 2. suggest\_outfit

**Signature:** `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

**Purpose:** Given the selected listing and the user's wardrobe, calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfit combinations using named pieces from the wardrobe. Falls back to general styling advice if the wardrobe is empty.

**Inputs:**

| Parameter | Type | Meaning |
|-----------|------|---------|
| new_item | dict | A listing dict from search\_listings |
| wardrobe | dict | A wardrobe dict with an `items` key (list of wardrobe item dicts). May be empty. |

**Output:** A non-empty string with 1–2 specific outfit suggestions. If the wardrobe has items, suggestions name actual wardrobe pieces by their `name` field. If the wardrobe is empty, returns general styling guidance (types of pieces, aesthetic, vibe).

---

### 3. create\_fit\_card

**Signature:** `create_fit_card(outfit: str, new_item: dict) -> str`

**Purpose:** Generates a 2–4 sentence Instagram/TikTok-style caption for the thrifted outfit. Runs at temperature 0.95 to produce meaningfully different captions for each input.

**Inputs:**

| Parameter | Type | Meaning |
|-----------|------|---------|
| outfit | str | The outfit suggestion string from suggest\_outfit. If empty or whitespace-only, returns an error string without calling the LLM. |
| new_item | dict | The listing dict for the thrifted item. Used for title, price, and platform. |

**Output:** A 2–4 sentence caption string written in a casual, lowercase OOTD style — mentions the item name, price, and platform once each, captures the specific outfit vibe.

---

## How the Planning Loop Works

The planning loop lives in `run_agent()` in `agent.py`. It does not call all three tools unconditionally — the sequence has a real conditional branch that determines whether execution continues or terminates early.

**Step 1:** Initialize a `session` dict that holds all state for the interaction.

**Step 2:** Parse the user's query using regex patterns (not an LLM call) to extract `description`, `size`, and `max_price`. Regular expressions handle common phrasings like "under $30", "below $40", "in size M", "size 8".

**Step 3:** Call `search_listings` with the parsed parameters.

**Branch A (no results):** If `search_listings` returns an empty list, the agent sets `session["error"]` to a specific message telling the user what was searched and what to try differently. It returns the session immediately. `suggest_outfit` and `create_fit_card` are never called.

**Branch B (results found):** The agent sets `session["selected_item"]` to `results[0]` (the highest-relevance match) and continues.

**Step 4:** Call `suggest_outfit` with the selected item and the user's wardrobe. Store the returned string in `session["outfit_suggestion"]`.

**Step 5:** Call `create_fit_card` with the outfit suggestion and the selected item. Store the result in `session["fit_card"]`.

**Step 6:** Return the completed session. The UI checks `session["error"]` first.

---

## State Management

A single `session` dict, initialized by `_new_session()`, holds all state for one interaction. No global state is used.

| Key | Set when | Consumed by |
|-----|----------|-------------|
| query | Immediately | Logging |
| parsed | After query parse | search\_listings arguments |
| search\_results | After search | Branch decision |
| selected\_item | After search (results found) | suggest\_outfit, create\_fit\_card, UI listing panel |
| wardrobe | Immediately | suggest\_outfit |
| outfit\_suggestion | After suggest\_outfit | create\_fit\_card, UI outfit panel |
| fit\_card | After create\_fit\_card | UI fit card panel |
| error | On early exit | UI error panel |

No tool receives the session object directly. `run_agent()` extracts the relevant values and passes them as arguments, which keeps each tool independently testable.

---

## Error Handling

### search\_listings: no results

When `search_listings` returns `[]`, the agent sets a specific error message in the session and returns early without calling the other tools:

> No listings found for "designer ballgown" in size XXS under $5. Try broadening your search: remove the size filter, raise your price limit, or use different keywords.

Tested by running: `python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"`
Result: `[]` — no exception raised.

### suggest\_outfit: empty wardrobe

When `wardrobe["items"]` is an empty list, the function switches to a general-styling prompt instead of crashing or returning an empty string. The LLM is asked what types of pieces pair well with the item and what aesthetic it suits.

Tested by calling `suggest_outfit(results[0], get_empty_wardrobe())` directly — returned a multi-sentence styling suggestion without raising any exception.

### create\_fit\_card: empty outfit string

When `outfit` is an empty string or whitespace-only, the function returns an error message string before calling the LLM at all:

> Error: Cannot create a fit card without an outfit suggestion.

Tested by calling `create_fit_card("", results[0])` and `create_fit_card("   ", results[0])` — both returned the error string, no exception.

---

## Spec Reflection

**One way the spec helped:** Writing the agent diagram in planning.md before touching agent.py forced me to think through the branch explicitly — the "no results" path and where it terminates. Without that diagram I would have written a linear sequence and added the branch as an afterthought, which tends to produce messier code.

**One way implementation diverged from the spec:** The spec said the query parser might use "regex, string splitting, or the LLM." I initially thought I'd use the LLM for parsing because it handles ambiguous phrasing. But adding an LLM call just for parsing would have added latency and a new failure mode to something that regex handles adequately for a fixed set of patterns. I kept the regex-only approach and documented it. If the query is very ambiguous, the search step's relevance scoring compensates — imperfect parsing still produces a relevant result because the keyword overlap scoring is forgiving.

---

## AI Usage

**Instance 1: Implementing search\_listings keyword scoring**

I gave Claude the Tool 1 spec from planning.md (inputs, return value, failure mode) and the field list from listings.json, and asked it to implement the scoring function using `load_listings()`. The initial version used `any()` instead of `sum()` for the keyword score, which meant all ties were collapsed — a listing matching 5 keywords ranked the same as one matching 1. I changed it to `sum(1 for kw in keywords if kw in blob)` so scores accumulate and better matches rank higher.

**Instance 2: Writing the suggest\_outfit LLM prompt**

I gave Claude the Tool 2 spec, the wardrobe\_schema.json structure, and a sample listing dict, and asked it to write the conditional prompt logic (empty wardrobe vs. non-empty wardrobe). The generated prompt for the non-empty case just said "suggest outfits using the wardrobe" without naming the wardrobe items specifically. I rewrote the prompt to explicitly format each wardrobe item as `- {name} ({colors}): {notes}` so the LLM could reference actual piece names in its suggestions rather than generic descriptions.
