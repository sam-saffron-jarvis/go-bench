# 9x9 Go board benchmark spec

Build `workspace/board.html`.

## Output format
- One self-contained HTML file.
- Inline CSS and inline JavaScript only.
- No network access.
- No external libraries.

## Functional requirements
- Render a playable **9x9 Go board**.
- **Black moves first**.
- Turns alternate between black and white.
- Clicking an **occupied point** must do nothing.
- **Captures** must remove groups with no liberties.
- **Suicide is illegal** unless the move captures opposing stones and therefore gains liberties.
- Provide a **Reset** button that restores a fresh empty board.
- Ko, scoring, pass, SGF import/export, and move history are **not required**.

## Test hooks required for verification
- Every playable intersection must be clickable and have a `data-cell="x,y"` attribute using **0-based coordinates**.
  - Example: top-left is `data-cell="0,0"`.
  - Bottom-right is `data-cell="8,8"`.
- Add a reset button with `id="reset"`.
- Expose a global object `window.__goGame__` with a function `getState()`.
- `window.__goGame__.getState()` must return an object shaped like:

```json
{
  "size": 9,
  "currentPlayer": "black",
  "board": [[null, null], [null, "black"]],
  "captured": {
    "black": 0,
    "white": 0
  }
}
```

## State contract
- `size` must be `9`.
- `currentPlayer` must be either `"black"` or `"white"`.
- `board` must be a 9x9 2D array indexed as `board[y][x]`.
- Each board value must be `"black"`, `"white"`, or `null`.
- `captured.black` = number of stones captured by black.
- `captured.white` = number of stones captured by white.

## UX
- Make it visually pleasant enough to demo.
- Show whose turn it is.
- Show capture counts.
