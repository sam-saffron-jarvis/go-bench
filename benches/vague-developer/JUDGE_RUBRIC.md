# Vague Go board judge rubric

## Original prompt

`build a standalone 9x9 fully functioning go board in index.html`

## What this judge is for

This is **not** the strict hidden-spec bench.

Judge the artifact against the vague prompt above, using only the supplied Playwright evidence.
Do **not** require hidden hooks like `data-cell`, `window.__goGame__`, exact button IDs, or any private verifier contract.

## Scoring

Score out of **20** using these buckets:

- **board** — 0 to 3
  - Does the page visibly look like a 9x9 Go board or a credible Go game UI?
  - Correct visual fundamentals matter here: stones rendered on **intersections** instead of square centers, and **hoshi points** in the right places on a 9x9 board matter a lot.
- **interaction** — 0 to 4
  - Do clicks appear to place stones? Does the board react? Does the page seem usable?
- **move_handling** — 0 to 3
  - Is there evidence that turns alternate and occupied points are handled sensibly?
- **rules** — 0 to 6
  - Is there evidence of liberties, capture, suicide prevention, ko, or other real Go logic?
  - Missing capture evidence should cap this category aggressively.
- **completeness** — 0 to 4
  - Is it reasonably complete and self-contained for the prompt?
  - Helpful controls like reset/new game/status/undo/score count here.
  - If the page depends on failing external requests for core functionality, deduct here.

## Score bands

- **0–4:** broken
- **5–8:** toy
- **9–12:** partial
- **13–16:** playable
- **17–20:** strong

## Guidance

- Be fair to the vague prompt.
- Be conservative when evidence is weak.
- Prefer observed behavior over optimistic interpretation.
- If the page crashes, hangs, or never shows meaningful interaction, score low.
- If it clearly places stones and alternates turns but there is no convincing capture evidence, it can still be **partial** or low **playable**, but not **strong**.
- If evidence strongly suggests occupied-point rejection, capture, useful controls, and the board **looks like actual Go** rather than checkerboard-ish approximation, reward it.
- Visual quality is not the whole score, but bad fundamentals like missing/misplaced hoshi points or stones centered in cells instead of intersections should meaningfully hold down the total.

## Output format

Return **one JSON object only** with this exact shape:

```json
{
  "score": 0,
  "band": "broken",
  "subscores": {
    "board": 0,
    "interaction": 0,
    "move_handling": 0,
    "rules": 0,
    "completeness": 0
  },
  "confidence": "low",
  "summary": "short plain-English verdict",
  "evidence_highlights": [
    "bullet 1",
    "bullet 2"
  ],
  "evidence_gaps": [
    "bullet 1",
    "bullet 2"
  ]
}
```

Rules for the JSON:

- `score` must be an integer 0–20.
- `band` must be one of: `broken`, `toy`, `partial`, `playable`, `strong`.
- `confidence` must be one of: `low`, `medium`, `high`.
- `summary` should be one sentence.
- `evidence_highlights` and `evidence_gaps` should each contain 1–4 short strings.
- No markdown fences. No extra commentary.
