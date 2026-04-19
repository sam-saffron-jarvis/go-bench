#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS = json.loads((REPO_ROOT / "models.json").read_text(encoding="utf-8"))
MODEL_ORDER = {model["slug"]: idx for idx, model in enumerate(MODELS)}
BENCH_ORDER = ["strict-custom-agent", "vague-developer"]


def load_results() -> list[dict]:
    rows = []
    for meta_path in REPO_ROOT.glob("results/*/*/metadata.json"):
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        data["_path"] = meta_path
        rows.append(data)
    rows.sort(key=lambda row: (BENCH_ORDER.index(row["bench"]), MODEL_ORDER.get(row["slug"], 999)))
    return rows


def fmt_stats(meta: dict) -> tuple[str, str, str, str]:
    stats = (meta.get("run") or {}).get("stats") or {}
    tokens = "—"
    tools = "—"
    llm_calls = "—"
    elapsed = f"{meta['run'].get('elapsed_seconds', 0):.1f}s"
    if stats:
        if "input_tokens" in stats and "output_tokens" in stats:
            tokens = f"{stats['input_tokens']}→{stats['output_tokens']}"
        if "tool_calls" in stats:
            tools = str(stats["tool_calls"])
        if "llm_calls" in stats:
            llm_calls = str(stats["llm_calls"])
    return elapsed, tokens, tools, llm_calls


def result_link(meta: dict, name: str) -> str:
    rel = meta["_path"].parent.relative_to(REPO_ROOT)
    return f"[{name}]({rel.as_posix()})"


def build_markdown(rows: list[dict]) -> str:
    lines = []
    lines.append("# go-bench summary")
    lines.append("")
    lines.append("Generated from `results/*/*/metadata.json`.")
    lines.append("")
    for bench in BENCH_ORDER:
        bench_rows = [row for row in rows if row["bench"] == bench]
        if not bench_rows:
            continue
        lines.append(f"## {bench}")
        lines.append("")
        lines.append("| Model | Status | Time | Tokens in→out | Tools | LLM calls | Artifacts |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for meta in bench_rows:
            elapsed, tokens, tools, llm_calls = fmt_stats(meta)
            status = "PASS" if meta["verification"]["passed"] else "FAIL"
            rel = meta["_path"].parent.relative_to(REPO_ROOT)
            links = [f"[dir]({rel.as_posix()})", f"[log]({rel.as_posix()}/run.log)"]
            screenshot = meta.get("artifacts", {}).get("screenshot")
            if screenshot:
                links.append(f"[shot]({rel.as_posix()}/{screenshot})")
            lines.append(
                f"| {meta['display']} | {status} | {elapsed} | {tokens} | {tools} | {llm_calls} | {' '.join(links)} |"
            )
        lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- The strict bench uses a custom agent plus a custom verifier tool.")
    lines.append("- The vague bench uses `@developer` with the prompt `build a standalone 9x9 fully functioning go board in index.html` and verifies the result externally after the run.")
    lines.append("- `venice:kimi-2.7` was probed separately and returned 404; Venice currently suggests `kimi-k2-5` or `kimi-k2-thinking`.")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    rows = load_results()
    summary_json = []
    for row in rows:
        summary_json.append({k: v for k, v in row.items() if k != "_path"})
    (REPO_ROOT / "results" / "summary.json").write_text(json.dumps(summary_json, indent=2) + "\n", encoding="utf-8")
    (REPO_ROOT / "results" / "summary.md").write_text(build_markdown(rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
