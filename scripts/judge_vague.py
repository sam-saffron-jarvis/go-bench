#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = REPO_ROOT / "results" / "vague-developer"
COLLECTOR = REPO_ROOT / "scripts" / "collect_vague_evidence.mjs"
RUBRIC = REPO_ROOT / "benches" / "vague-developer" / "JUDGE_RUBRIC.md"
DEFAULT_JUDGE_PROVIDER = "claude-bin:sonnet"
JUDGE_PROMPT = (
    "Judge the supplied Playwright evidence for the vague Go-board prompt. "
    "Score the artifact against the vague prompt, not the hidden strict verifier. "
    "Visual correctness matters: hoshi placement and stones rendered on intersections matter. "
    "Return only the JSON object required by the rubric."
)


def sh(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
    merge_stderr: bool = True,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def parse_json_events(stdout_text: str) -> tuple[list[dict], list[dict]]:
    events: list[dict] = []
    errors: list[dict] = []
    for line_no, raw_line in enumerate(stdout_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({"line": line_no, "error": str(exc), "text": raw_line[:500]})
            continue
        if not isinstance(parsed, dict):
            errors.append(
                {"line": line_no, "error": f"expected object, got {type(parsed).__name__}", "text": raw_line[:500]}
            )
            continue
        events.append(parsed)
    return events, errors


def last_event(events: list[dict], event_type: str) -> dict | None:
    for event in reversed(events):
        if event.get("type") == event_type:
            return event
    return None


def extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in judge output")
    return json.loads(stripped[start : end + 1])


def validate_judgment(data: dict) -> None:
    required = ["score", "band", "subscores", "confidence", "summary", "evidence_highlights", "evidence_gaps"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"judgment missing keys: {', '.join(missing)}")
    if not isinstance(data["score"], int) or not 0 <= data["score"] <= 20:
        raise ValueError("judgment.score must be an integer between 0 and 20")
    if data["band"] not in {"broken", "toy", "partial", "playable", "strong"}:
        raise ValueError("judgment.band has invalid value")
    if data["confidence"] not in {"low", "medium", "high"}:
        raise ValueError("judgment.confidence has invalid value")


def direct_missing_output_judgment(expected_file: str) -> dict:
    return {
        "score": 0,
        "band": "broken",
        "subscores": {
            "board": 0,
            "interaction": 0,
            "move_handling": 0,
            "rules": 0,
            "completeness": 0,
        },
        "confidence": "high",
        "summary": f"No usable {expected_file} was produced.",
        "evidence_highlights": ["Expected output file is missing."],
        "evidence_gaps": ["No rendered board could be inspected."],
    }


def judge_result(result_dir: Path, judge_provider: str, timeout_seconds: int, force: bool) -> None:
    meta_path = result_dir / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"metadata.json missing in {result_dir}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not force and meta.get("judgment") and meta["judgment"].get("score") is not None:
        print(f"skip {result_dir.name}: judgment already exists")
        return

    generated_dir = result_dir / (meta.get("artifacts") or {}).get("generated_dir", "generated")
    expected_file = (meta.get("output") or {}).get("expected_file") or "index.html"
    html_path = generated_dir / expected_file

    evidence_path = result_dir / "judge_evidence.json"
    judgment_path = result_dir / "judgment.json"
    judge_events_path = result_dir / "judge-events.jsonl"
    judge_final_path = result_dir / "judge-final.txt"
    judge_stderr_path = result_dir / "judge-stderr.log"
    judge_artifacts_dir = result_dir / "judge-artifacts"
    judge_artifacts_dir.mkdir(exist_ok=True)

    if not html_path.exists():
        evidence = {
            "html_path": str(html_path),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "collector_error": "expected output file is missing",
        }
        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        judgment = direct_missing_output_judgment(expected_file)
        judgment_path.write_text(json.dumps(judgment, indent=2) + "\n", encoding="utf-8")
        meta["judgment"] = {
            "judge_provider": None,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "score": judgment["score"],
            "band": judgment["band"],
            "subscores": judgment["subscores"],
            "confidence": judgment["confidence"],
            "summary": judgment["summary"],
            "evidence_highlights": judgment["evidence_highlights"],
            "evidence_gaps": judgment["evidence_gaps"],
            "run": None,
            "artifacts": {
                "evidence_json": evidence_path.name,
                "judgment_json": judgment_path.name,
                "judge_artifacts_dir": judge_artifacts_dir.name,
                "judge_events_jsonl": None,
                "judge_final_text": None,
                "judge_stderr_log": None,
            },
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        print(f"[judge] {result_dir.name}: 0/20 broken | missing output")
        return

    evidence_proc = sh(
        ["node", str(COLLECTOR), str(html_path), str(judge_artifacts_dir)],
        cwd=REPO_ROOT,
        timeout=240,
        merge_stderr=False,
    )
    evidence_stdout = evidence_proc.stdout or ""
    evidence_stderr = evidence_proc.stderr or ""
    evidence_path.write_text(evidence_stdout, encoding="utf-8")
    if evidence_stderr.strip():
        (result_dir / "judge-evidence.stderr.log").write_text(evidence_stderr, encoding="utf-8")
    if evidence_proc.returncode != 0:
        raise RuntimeError(f"evidence collector failed for {result_dir.name} with exit {evidence_proc.returncode}")

    try:
        evidence = json.loads(evidence_stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to parse evidence JSON for {result_dir.name}: {exc}") from exc

    judge_cmd = [
        "term-llm",
        "ask",
        "--no-session",
        "--json",
        "--skills",
        "none",
        "--provider",
        judge_provider,
        "--max-output-tokens",
        "1200",
        "-f",
        str(RUBRIC),
        "-f",
        str(evidence_path),
        JUDGE_PROMPT,
    ]

    start = time.time()
    judge_proc = sh(judge_cmd, cwd=REPO_ROOT, timeout=timeout_seconds, merge_stderr=False)
    elapsed = time.time() - start
    judge_events_path.write_text(judge_proc.stdout or "", encoding="utf-8")
    if (judge_proc.stderr or "").strip():
        judge_stderr_path.write_text(judge_proc.stderr or "", encoding="utf-8")

    events, parse_errors = parse_json_events(judge_proc.stdout or "")
    stats = last_event(events, "stats")
    final_text = "".join(event.get("text", "") for event in events if event.get("type") == "text.delta")
    judge_final_path.write_text(final_text, encoding="utf-8")

    if judge_proc.returncode != 0:
        raise RuntimeError(f"judge LLM failed for {result_dir.name} with exit {judge_proc.returncode}")

    judgment = extract_json_object(final_text)
    validate_judgment(judgment)
    judgment_path.write_text(json.dumps(judgment, indent=2) + "\n", encoding="utf-8")

    meta["judgment"] = {
        "judge_provider": judge_provider,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "score": judgment["score"],
        "band": judgment["band"],
        "subscores": judgment["subscores"],
        "confidence": judgment["confidence"],
        "summary": judgment["summary"],
        "evidence_highlights": judgment["evidence_highlights"],
        "evidence_gaps": judgment["evidence_gaps"],
        "run": {
            "exit_code": judge_proc.returncode,
            "elapsed_seconds": round(elapsed, 3),
            "stats": stats,
            "event_count": len(events),
            "json_parse_errors": parse_errors,
        },
        "artifacts": {
            "evidence_json": evidence_path.name,
            "judgment_json": judgment_path.name,
            "judge_artifacts_dir": judge_artifacts_dir.name,
            "judge_events_jsonl": judge_events_path.name,
            "judge_final_text": judge_final_path.name,
            "judge_stderr_log": judge_stderr_path.name if judge_stderr_path.exists() else None,
        },
        "collector_error": evidence.get("collector_error"),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"[judge] {result_dir.name}: {judgment['score']}/20 {judgment['band']} | {judgment['summary']}")


def iter_result_dirs(only: set[str]) -> list[Path]:
    dirs = [path.parent for path in RESULTS_ROOT.glob("*/metadata.json")]
    dirs.sort(key=lambda path: path.name)
    if only:
        dirs = [path for path in dirs if path.name in only]
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", default="")
    parser.add_argument("--only", default="")
    parser.add_argument("--judge-provider", default=DEFAULT_JUDGE_PROVIDER)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    only = {item.strip() for item in args.only.split(",") if item.strip()}
    if args.result_dir:
        result_dirs = [Path(args.result_dir).resolve()]
    else:
        result_dirs = iter_result_dirs(only)

    if not result_dirs:
        print("no vague-developer result dirs selected", file=sys.stderr)
        return 1

    failures = 0
    for result_dir in result_dirs:
        try:
            judge_result(result_dir, args.judge_provider, args.timeout_seconds, args.force)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"judge failed for {result_dir}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
