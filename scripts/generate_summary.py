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


def artifact_links(meta: dict) -> str:
    rel = meta["_path"].parent.relative_to(REPO_ROOT)
    artifacts = meta.get("artifacts") or {}
    links = [f"[dir]({rel.as_posix()})"]

    final_text = artifacts.get("final_text")
    if final_text:
        links.append(f"[final]({rel.as_posix()}/{final_text})")

    events_jsonl = artifacts.get("events_jsonl")
    run_log = artifacts.get("run_log")
    if events_jsonl:
        links.append(f"[events]({rel.as_posix()}/{events_jsonl})")
    elif run_log:
        links.append(f"[log]({rel.as_posix()}/{run_log})")

    stderr_log = artifacts.get("stderr_log")
    if stderr_log:
        links.append(f"[stderr]({rel.as_posix()}/{stderr_log})")

    screenshot = artifacts.get("screenshot")
    if screenshot:
        links.append(f"[shot]({rel.as_posix()}/{screenshot})")

    judgment = meta.get("judgment") or {}
    judge_artifacts = judgment.get("artifacts") or {}
    if judge_artifacts.get("judgment_json"):
        links.append(f"[judge]({rel.as_posix()}/{judge_artifacts['judgment_json']})")
    if judge_artifacts.get("evidence_json"):
        links.append(f"[evidence]({rel.as_posix()}/{judge_artifacts['evidence_json']})")
    if judge_artifacts.get("judge_events_jsonl"):
        links.append(f"[judge-events]({rel.as_posix()}/{judge_artifacts['judge_events_jsonl']})")
    return " ".join(links)


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
        if bench == "strict-custom-agent":
            lines.append("| Model | Status | Time | Tokens in→out | Tools | LLM calls | Artifacts |")
            lines.append("|---|---:|---:|---:|---:|---:|---|")
            for meta in bench_rows:
                elapsed, tokens, tools, llm_calls = fmt_stats(meta)
                status = "PASS" if meta["verification"]["passed"] else "FAIL"
                links = artifact_links(meta)
                lines.append(
                    f"| {meta['display']} | {status} | {elapsed} | {tokens} | {tools} | {llm_calls} | {links} |"
                )
        else:
            lines.append(
                "| Model | Hidden verifier | Judge | Band | Confidence | Time | Tokens in→out | Tools | LLM calls | Artifacts |"
            )
            lines.append("|---|---:|---:|---|---|---:|---:|---:|---:|---|")
            for meta in bench_rows:
                elapsed, tokens, tools, llm_calls = fmt_stats(meta)
                strict_status = "PASS" if meta["verification"]["passed"] else "FAIL"
                judgment = meta.get("judgment") or {}
                judge_score = "—"
                band = "—"
                confidence = "—"
                if judgment:
                    score = judgment.get("score")
                    if score is not None:
                        judge_score = f"{score}/20"
                    band = judgment.get("band") or "—"
                    confidence = judgment.get("confidence") or "—"
                links = artifact_links(meta)
                lines.append(
                    f"| {meta['display']} | {strict_status} | {judge_score} | {band} | {confidence} | {elapsed} | {tokens} | {tools} | {llm_calls} | {links} |"
                )
        lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- The strict bench uses a custom agent plus a custom verifier tool.")
    lines.append("- The vague bench uses a frozen local copy of the built-in developer agent, not the floating `@developer` alias.")
    lines.append("- Vague bench headline scores come from Playwright evidence plus a pinned LLM judge; the hidden strict verifier is shown separately.")
    lines.append("- Visual Go fundamentals matter in the vague judge: hoshi placement and stones landing on intersections, not square centers.")
    lines.append("- Benchmark telemetry comes from `term-llm ask --json`; newer runs store raw events in `events.jsonl`.")
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
