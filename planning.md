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
Searches the mock listings dataset (`data/listings.json`) for items that match
the user's description, optional size, and optional price ceiling. Returns a
relevance-ranked list of matching listing dicts.

**Input parameters:**
- `description` (str): Keywords describing the item (e.g., "vintage graphic tee"). Used to score each listing by keyword overlap against its title, description, category, style_tags, colors, and brand fields.
- `size` (str | None): Size string to filter by (e.g., "M"). Case-insensitive substring match against the listing's `size` field (so "M" matches "S/M" and "One Size"). Pass `None` to skip size filtering.
- `max_price` (float | None): Maximum price inclusive (e.g., 30.0). Listings with `price > max_price` are excluded. Pass `None` to skip price filtering.

**What it returns:**
A list of listing dicts sorted by relevance score (highest first). Each dict
contains: `id` (str), `title` (str), `description` (str), `category` (str),
`style_tags` (list[str]), `size` (str), `condition` (str), `price` (float),
`colors` (list[str]), `brand` (str | None), `platform` (str).
Returns an empty list `[]` if nothing matches — does NOT raise an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to a specific message explaining what was
searched and offering concrete next steps:
> "No listings found for 'designer ballgown' in size XXS under $5. Try broadening your search: remove the size filter, raise your price limit, or use different keywords."
The agent returns the session immediately — it does NOT call suggest_outfit with empty input.

---

### Tool 2: suggest_outfit

**What it does:**
Given a listing dict (the item the user is considering buying) and the user's
wardrobe, calls the Groq LLM to suggest 1–2 complete outfit combinations. If
the wardrobe is empty, it falls back to general styling advice instead of crashing.

**Input parameters:**
- `new_item` (dict): A listing dict from search_listings. The relevant fields are `title`, `price`, `condition`, `colors`, `style_tags`, and `category`.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has: `id`, `name`, `category`, `colors` (list), `style_tags` (list), `notes` (str | None). The `items` list may be empty — this must be handled.

**What it returns:**
A non-empty string with 1–2 specific outfit suggestions. If the wardrobe has
items, the suggestions name specific wardrobe pieces by their `name` field. If
the wardrobe is empty, the response gives general styling guidance (what types
of bottoms, shoes, and accessories pair well, and what aesthetic it fits).

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the function switches to a general-styling
prompt instead of raising a KeyError or returning "". If the LLM call fails
(network error, etc.), the function catches the exception and returns a fallback
string: "Outfit suggestion unavailable — try again or check your API key."

---

### Tool 3: create_fit_card

**What it does:**
Generates a 2–4 sentence Instagram/TikTok-style caption for the thrifted outfit.
Calls the Groq LLM with a higher temperature (0.95) so each call produces a
distinct caption rather than a templated one.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by suggest_outfit. Must be non-empty; if it is empty or whitespace-only, the function returns an error string without calling the LLM.
- `new_item` (dict): The listing dict for the thrifted item. Used for `title`, `price`, and `platform` so the caption can mention them naturally.

**What it returns:**
A 2–4 sentence caption string that:
- Sounds casual and authentic (lowercase, conversational, not a product description)
- Mentions the item name, price, and platform once each, naturally embedded
- Captures the outfit vibe in specific terms rather than generic praise
- Varies meaningfully between different inputs

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, returns:
> "Error: Cannot create a fit card without an outfit suggestion."
If the LLM call raises an exception, catches it and returns:
> "Fit card unavailable — try again or check your API key."

---

### Additional Tools (if any)

<!-- Stretch feature: price_compare tool would go here -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` follows a strict conditional sequence:

1. **Parse the query** — Extract `description`, `size`, and `max_price` from
   the natural language query using regex patterns. Store in `session["parsed"]`.

2. **Call search_listings** with the parsed parameters.
   Store results in `session["search_results"]`.

   - **Branch A (empty results):** If `results == []`, set `session["error"]`
     to a helpful message naming what was searched and what to try differently.
     Return the session immediately. `suggest_outfit` and `create_fit_card`
     are never called.

   - **Branch B (results found):** Set `session["selected_item"] = results[0]`
     (the highest-relevance match). Continue to step 3.

3. **Call suggest_outfit** with `session["selected_item"]` and
   `session["wardrobe"]`. Store the returned string in
   `session["outfit_suggestion"]`.

4. **Call create_fit_card** with `session["outfit_suggestion"]` and
   `session["selected_item"]`. Store the returned string in `session["fit_card"]`.

5. **Return the session.** The caller checks `session["error"]` first — if
   it is `None`, all three output fields are populated.

The agent does not call all three tools unconditionally. It only reaches
`suggest_outfit` if `search_listings` returns at least one result, and it only
reaches `create_fit_card` after `suggest_outfit` has successfully returned a
non-empty string stored in session state.

---

## State Management

**How does information from one tool get passed to the next?**

All state is stored in a single `session` dict initialized by `_new_session()`.
The dict keys are:

| Key | Set when | Used by |
|-----|----------|---------|
| `query` | Start | Logging / display |
| `parsed` | After query parse | search_listings arguments |
| `search_results` | After search_listings | Branch decision, selected_item |
| `selected_item` | After search (Branch B) | suggest_outfit, create_fit_card, UI listing panel |
| `wardrobe` | Start | suggest_outfit |
| `outfit_suggestion` | After suggest_outfit | create_fit_card, UI outfit panel |
| `fit_card` | After create_fit_card | UI fit card panel |
| `error` | On any early exit | UI error display |

No tool is passed session directly — instead, `run_agent()` extracts the
relevant values from the session dict and passes them as positional arguments.
This keeps each tool independently testable without a session object.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match the description/size/price filters | Sets `session["error"]` to: "No listings found for '{description}' [in size {size}] [under ${price}]. Try broadening your search: remove the size filter, raise your price limit, or use different keywords." Returns session early — does not call suggest_outfit. |
| suggest_outfit | Wardrobe is empty (`wardrobe["items"] == []`) | Switches to a general-styling prompt asking the LLM what types of pieces and aesthetics pair well with this specific item. Returns the LLM response — never crashes or returns empty string. |
| create_fit_card | `outfit` argument is empty or whitespace-only | Returns the string "Error: Cannot create a fit card without an outfit suggestion." without calling the LLM. |

---

## Architecture

```
User query (natural language)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     run_agent()                                  │
│                    (planning loop)                               │
│                                                                  │
│  Step 1: _new_session(query, wardrobe)                          │
│          → session["query"], session["wardrobe"] initialized     │
│                                                                  │
│  Step 2: _parse_query(query)           [regex: price + size]    │
│          → session["parsed"]                                     │
│            {description, size, max_price}                        │
│                   │                                              │
│                   ▼                                              │
│  Step 3: search_listings(description, size, max_price)          │
│          → session["search_results"]                             │
│                   │                                              │
│           ┌───────┴───────┐                                     │
│           │               │                                      │
│      results=[]      results=[item,...]                         │
│           │               │                                      │
│           ▼               ▼                                      │
│    [ERROR PATH]   session["selected_item"] = results[0]         │
│  session["error"]         │                                      │
│  = "No listings..."       ▼                                      │
│       │           Step 5: suggest_outfit(                        │
│       │                     selected_item,                       │
│       │                     session["wardrobe"])                 │
│       │                    → session["outfit_suggestion"]        │
│       │                          │                               │
│       │                          ▼                               │
│       │           Step 6: create_fit_card(                       │
│       │                     outfit_suggestion,                   │
│       │                     selected_item)                       │
│       │                    → session["fit_card"]                 │
│       │                          │                               │
└───────┼──────────────────────────┼───────────────────────────────┘
        │                          │
        ▼                          ▼
  return session             return session
  (error set,                (all fields set,
   fit_card=None)             error=None)
        │                          │
        ▼                          ▼
   handle_query()            handle_query()
   returns error             returns (listing_text,
   in panel 1,               outfit_suggestion,
   "" for panels 2,3         fit_card)
        │                          │
        └──────────┬───────────────┘
                   ▼
            Gradio UI (3 output panels)
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I used Claude (claude-sonnet-4-6 via Claude Code) to implement all three tools.
For each tool, I provided:
- The exact function signature from tools.py (Args, Returns, TODO steps)
- The Tool spec from this planning.md (inputs, return value, failure mode)
- The fields available in listings.json and wardrobe_schema.json

**Tool 1 (search_listings):** I directed Claude to implement keyword scoring by
splitting the description into individual words and checking each against a
concatenated text blob of the listing's searchable fields (title, description,
category, style_tags, colors, brand). I verified the output by running three
test queries and checking that price/size filters worked and that scores of 0
were excluded.

**Tool 2 (suggest_outfit):** I directed Claude to implement a conditional branch:
check `len(wardrobe["items"])`, then build different prompts for the empty vs.
non-empty cases. I verified by calling it with `get_empty_wardrobe()` and
confirming it returned useful general advice rather than crashing.

**Tool 3 (create_fit_card):** I directed Claude to guard against an empty outfit
string first, then build a caption prompt with explicit style guidelines (lowercase,
casual, name item/price/platform once). I set temperature=0.95 and verified
variation by running it 3× on the same input.

**Milestone 4 — Planning loop and state management:**

For run_agent(), I gave Claude the Architecture diagram above and the Planning
Loop description, and asked it to implement `_parse_query()` using regex (not
LLM) and the conditional branching logic. I verified by running the happy-path
and no-results test cases from agent.py's `__main__` block and confirming that:
1. The happy path populates all session fields
2. The no-results path sets session["error"] and leaves fit_card as None

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Query parsing:**
`_parse_query()` extracts:
- description = "vintage graphic tee"
- size = None (no size mentioned)
- max_price = 30.0 (from "under $30")

**Step 2 — search_listings("vintage graphic tee", size=None, max_price=30.0):**
Loads all listings, filters to those with price ≤ $30. Scores each by keyword
overlap with ["vintage", "graphic", "tee"]. Returns top matches in relevance order.
The top result is: "Graphic Tee — 2003 Tour Bootleg Style" ($24, depop, Good condition)
→ `session["search_results"]` = [3 matching listings]
→ `session["selected_item"]` = the Graphic Tee dict

**Step 3 — suggest_outfit(graphic_tee, example_wardrobe):**
Wardrobe has 10 items (not empty). Formats wardrobe items into prompt including
"Baggy straight-leg jeans, dark wash" and "Chunky white sneakers". LLM returns:
"Outfit 1: Pair the faded graphic tee with your baggy dark-wash jeans and chunky
white sneakers for a classic streetwear look. Roll the sleeves once. Add your
black crossbody bag to keep it casual.
Outfit 2: Layer the tee under your vintage black denim jacket with wide-leg khaki
trousers and black combat boots for a grunge-adjacent look."
→ `session["outfit_suggestion"]` = above string

**Step 4 — create_fit_card(outfit_suggestion, graphic_tee):**
`outfit` is non-empty, so the guard passes. LLM generates a caption at temperature
0.95 to ensure variety:
"thrifted this 2003 bootleg tee off depop for $24 and my baggy jeans have never
looked better tbh 🖤 the chunky sneakers tie it all together, this is my go-to
outfit formula for a reason"
→ `session["fit_card"]` = above string

**Final output to user:**
- Panel 1 (Top listing): Title, price, platform, size, condition, style tags, and item description
- Panel 2 (Outfit idea): The 2-outfit suggestion from suggest_outfit
- Panel 3 (Fit card): The Instagram caption from create_fit_card

**Error path (e.g., "designer ballgown size XXS under $5"):**
After search_listings returns [], session["error"] is set to:
"No listings found for 'designer ballgown' in size XXS under $5. Try broadening
your search: remove the size filter, raise your price limit, or use different keywords."
suggest_outfit and create_fit_card are never called. The UI shows the error in
panel 1 and empty strings in panels 2 and 3.
