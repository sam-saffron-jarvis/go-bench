You are building a reproducible benchmark artifact.

Goal: create `workspace/board.html` as a single self-contained HTML file with inline CSS and JavaScript.

Rules:
- Work only inside `workspace/`.
- Do not introduce npm packages, CDNs, or external assets.
- Use the `verify_board` tool after changes.
- If verification fails, fix the page and run `verify_board` again.
- Keep iterating until the verifier passes.
- When finished, reply with exactly `DONE`.
