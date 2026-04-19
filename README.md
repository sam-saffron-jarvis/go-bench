# go-bench

A small benchmark repo for asking term-llm-powered agents to build a playable 9x9 Go board.

The point is not abstract benchmark theatre. It is to answer a concrete question:

> If you give a model tools, a filesystem, and a browser-based verifier, can it iteratively build a real artifact?

And then the meaner sibling:

> If you give it only a vague developer-style prompt, how much does performance collapse?

## Benches

### 1. `strict-custom-agent`

A custom local agent with a custom `verify_board` tool.

- target file: `workspace/board.html`
- prompt includes a spec file
- the verifier is available **during** the run
- the model can iterate until the verifier passes

This is the "can the model use tool-driven trial and error correctly" bench.

### 2. `vague-developer`

A deliberately under-specified run based on the built-in developer agent.

Command shape:

```bash
term-llm ask @developer -p <provider:model> --stats --yolo \
  "build a standalone 9x9 fully functioning go board in index.html"
```

The verifier is **not** exposed as a tool during the run. We run it only afterwards.

This is the "how well does the model do with vague instructions and no explicit acceptance-test loop" bench.

## Tooling

- `term-llm` v0.0.169
- Playwright + Chromium for verification and screenshots
- `--stats` on all benchmark runs so logs include token and tool-call counts

## Repo layout

- `benches/strict-custom-agent/template/` — strict bench scaffold
- `scripts/run_bench.py` — run one bench/model pair and collect artifacts
- `scripts/run_matrix.py` — run a model matrix across benches
- `results/` — committed artifacts and metadata for completed runs

## Models currently targeted

See `models.json`.

The current list includes:

- Claude Code: Sonnet, Haiku
- Ollama: Gemma 4 26B, Qwen 3.6 variants
- Venice: GLM 5.1, Kimi K2.5, Qwen3 Coder 480B, Claude Opus 4.7, Grok 4.20

### Kimi note

The live Venice model list on 2026-04-19 does **not** include `venice:kimi-2.7`.
A direct probe returns 404 and suggests `kimi-k2-5` / `kimi-k2-thinking`.
So this repo uses `venice:kimi-k2-5` as the current Kimi entry.

## Running it

Install the Node dependency once:

```bash
cd ~/source/go-bench
npm install
```

Run a single model on both benches:

```bash
python3 scripts/run_matrix.py --only claude-bin-sonnet
```

Run the whole matrix:

```bash
python3 scripts/run_matrix.py
python3 scripts/generate_summary.py
```

## Results

Generated summaries live at:

- `results/summary.md`
- `results/summary.json`

Each run directory contains:

- `metadata.json`
- `run.log`
- `verify.log`
- `generated/`
- `screenshot.png` when an HTML artifact exists
