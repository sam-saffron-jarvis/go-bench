#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STRICT_TEMPLATE = REPO_ROOT / "benches" / "strict-custom-agent" / "template"
VAGUE_TEMPLATE = REPO_ROOT / "benches" / "vague-developer" / "template"
STRICT_VERIFIER = STRICT_TEMPLATE / "agent" / "scripts" / "verify-board.mjs"
RESULTS_ROOT = REPO_ROOT / "results"
RUNS_ROOT = REPO_ROOT / ".runs"
JUDGE_VAGUE = REPO_ROOT / "scripts" / "judge_vague.py"

STRICT_PROMPT = (
    "Build the board described in SPEC.md. Create or replace workspace/board.html. "
    "Use the verify_board tool repeatedly until it passes. When the board passes, reply DONE."
)
VAGUE_PROMPT = "build a standalone 9x9 fully functioning go board in index.html"


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


def term_llm_version() -> str:
    proc = sh(["term-llm", "--version"], cwd=REPO_ROOT)
    return proc.stdout.strip()


def unload_ollama() -> None:
    proc = sh(["bash", "-lc", "ollama ps | awk 'NR>1 {print $1}'"], cwd=REPO_ROOT)
    names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    for name in names:
        sh(["ollama", "stop", name], cwd=REPO_ROOT, timeout=60)
    if names:
        time.sleep(1)


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
            errors.append(
                {
                    "line": line_no,
                    "error": str(exc),
                    "text": raw_line[:500],
                }
            )
            continue
        if not isinstance(parsed, dict):
            errors.append(
                {
                    "line": line_no,
                    "error": f"expected object, got {type(parsed).__name__}",
                    "text": raw_line[:500],
                }
            )
            continue
        events.append(parsed)
    return events, errors


def last_event(events: list[dict], event_type: str) -> dict | None:
    for event in reversed(events):
        if event.get("type") == event_type:
            return event
    return None


def first_event(events: list[dict], event_type: str) -> dict | None:
    for event in events:
        if event.get("type") == event_type:
            return event
    return None


def compact_int(value: int) -> str:
    if value >= 1_000_000:
        text = f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{text}m"
    if value >= 1_000:
        text = f"{value / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"{text}k"
    return str(value)


def format_stats_summary(stats: dict | None) -> str:
    if not stats:
        return "no stats"
    duration_ms = stats.get("duration_ms")
    if isinstance(duration_ms, (int, float)):
        duration = f"{duration_ms / 1000:.1f}s"
    else:
        duration = "?s"
    parts = [duration]
    if "input_tokens" in stats and "output_tokens" in stats:
        parts.append(f"{compact_int(int(stats['input_tokens']))} in → {compact_int(int(stats['output_tokens']))} out")
    if "tool_calls" in stats:
        parts.append(f"{stats['tool_calls']} tools")
    if "llm_calls" in stats:
        parts.append(f"{stats['llm_calls']} llm calls")
    return " | ".join(parts)


def prepare_temp_dir(bench: str, slug: str) -> Path:
    temp_dir = RUNS_ROOT / bench / slug
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.parent.mkdir(parents=True, exist_ok=True)
    if bench == "strict-custom-agent":
        shutil.copytree(STRICT_TEMPLATE, temp_dir)
        (temp_dir / "workspace").mkdir(exist_ok=True)
    elif bench == "vague-developer":
        shutil.copytree(VAGUE_TEMPLATE, temp_dir)
    else:
        raise ValueError(f"unknown bench: {bench}")
    return temp_dir


def generated_output_path(bench: str, temp_dir: Path) -> Path:
    if bench == "strict-custom-agent":
        return temp_dir / "workspace" / "board.html"
    if bench == "vague-developer":
        return temp_dir / "index.html"
    raise ValueError(f"unknown bench: {bench}")


def command_for(bench: str, provider: str) -> list[str]:
    common = ["--no-session", "--json", "--yolo", "--provider", provider]
    if bench == "strict-custom-agent":
        return [
            "term-llm",
            "ask",
            *common,
            "--max-turns",
            "30",
            "--agent",
            "./agent",
            "--read-dir",
            ".",
            "--write-dir",
            "./workspace",
            "-f",
            "./SPEC.md",
            STRICT_PROMPT,
        ]
    if bench == "vague-developer":
        return [
            "term-llm",
            "ask",
            *common,
            "--agent",
            "./agent",
            "--read-dir",
            ".",
            "--write-dir",
            ".",
            VAGUE_PROMPT,
        ]
    raise ValueError(f"unknown bench: {bench}")


def copy_generated_tree(temp_dir: Path, bench: str, result_dir: Path) -> None:
    generated_dir = result_dir / "generated"
    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    generated_dir.mkdir(parents=True)
    if bench == "strict-custom-agent":
        for name in ["agent", "SPEC.md", "workspace"]:
            src = temp_dir / name
            dest = generated_dir / name
            if src.is_dir():
                shutil.copytree(src, dest)
            elif src.exists():
                shutil.copy2(src, dest)
    else:
        for child in temp_dir.iterdir():
            dest = generated_dir / child.name
            if child.is_dir():
                shutil.copytree(child, dest)
            else:
                shutil.copy2(child, dest)


def verify_output(html_path: Path, result_dir: Path) -> tuple[bool, str, int]:
    proc = sh(["node", str(STRICT_VERIFIER), str(html_path)], cwd=REPO_ROOT, timeout=180)
    (result_dir / "verify.log").write_text(proc.stdout, encoding="utf-8")
    return proc.returncode == 0, proc.stdout, proc.returncode


def render_screenshot(html_path: Path, result_dir: Path) -> str | None:
    if not html_path.exists():
        return None
    out = result_dir / "screenshot.png"
    proc = sh(["bash", str(REPO_ROOT / "scripts" / "render_screenshot.sh"), str(html_path), str(out)], cwd=REPO_ROOT, timeout=180)
    if proc.returncode != 0:
        (result_dir / "screenshot.log").write_text(proc.stdout, encoding="utf-8")
        return None
    return out.name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", required=True, choices=["strict-custom-agent", "vague-developer"])
    parser.add_argument("--provider", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--display", default="")
    parser.add_argument("--timeout-seconds", type=int, default=1500)
    parser.add_argument("--judge-provider", default="claude-bin:sonnet")
    parser.add_argument("--note", default="")
    parser.add_argument("--requested", default="")
    args = parser.parse_args()

    bench = args.bench
    provider = args.provider
    slug = args.slug
    result_dir = RESULTS_ROOT / bench / slug
    if result_dir.exists():
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = prepare_temp_dir(bench, slug)
    if provider.startswith("ollama:"):
        unload_ollama()

    command = command_for(bench, provider)
    command_text = subprocess.list2cmdline(command)
    (result_dir / "command.txt").write_text(command_text + "\n", encoding="utf-8")

    start = time.time()
    timed_out = False
    stdout_text = ""
    stderr_text = ""
    try:
        proc = sh(command, cwd=temp_dir, timeout=args.timeout_seconds, merge_stderr=False)
        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        return_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        _raw_out = exc.stdout or b""
        _raw_err = exc.stderr or b""
        stdout_text = _raw_out.decode("utf-8", errors="replace") if isinstance(_raw_out, bytes) else _raw_out
        stderr_text = (_raw_err.decode("utf-8", errors="replace") if isinstance(_raw_err, bytes) else _raw_err) + "\nTIMEOUT\n"
        return_code = 124
    elapsed = time.time() - start

    (result_dir / "events.jsonl").write_text(stdout_text.decode("utf-8", errors="replace") if isinstance(stdout_text, bytes) else stdout_text, encoding="utf-8")
    stderr_name = None
    if stderr_text.strip():
        stderr_name = "stderr.log"
        (result_dir / stderr_name).write_text(stderr_text, encoding="utf-8")

    events, parse_errors = parse_json_events(stdout_text)
    stats = last_event(events, "stats")
    done = last_event(events, "done")
    session_started = first_event(events, "session.started")
    final_text = "".join(event.get("text", "") for event in events if event.get("type") == "text.delta")
    final_text_name = None
    if final_text:
        final_text_name = "final.txt"
        (result_dir / final_text_name).write_text(final_text, encoding="utf-8")

    event_counts = Counter(event.get("type") for event in events if event.get("type"))
    tool_counts = Counter(event.get("name") for event in events if event.get("type") == "tool.started" and event.get("name"))
    tool_success = Counter()
    for event in events:
        if event.get("type") != "tool.completed" or not event.get("name"):
            continue
        key = "success" if event.get("success") else "failure"
        tool_success[f"{event['name']}:{key}"] += 1

    html_path = generated_output_path(bench, temp_dir)
    verified, verify_output_text, verify_returncode = verify_output(html_path, result_dir)
    screenshot_name = render_screenshot(html_path, result_dir)
    copy_generated_tree(temp_dir, bench, result_dir)

    metadata = {
        "bench": bench,
        "slug": slug,
        "display": args.display or slug,
        "provider": provider,
        "requested": args.requested or None,
        "note": args.note or None,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "term_llm_version": term_llm_version(),
        "command": command,
        "command_text": command_text,
        "prompt": STRICT_PROMPT if bench == "strict-custom-agent" else VAGUE_PROMPT,
        "timeout_seconds": args.timeout_seconds,
        "run": {
            "exit_code": return_code,
            "timed_out": timed_out,
            "elapsed_seconds": round(elapsed, 3),
            "stats": stats,
            "event_count": len(events),
            "event_counts": dict(event_counts),
            "tool_counts": dict(tool_counts),
            "tool_outcomes": dict(tool_success),
            "json_parse_errors": parse_errors,
            "session_started": session_started,
            "done": done,
        },
        "verification": {
            "passed": verified,
            "exit_code": verify_returncode,
            "output": verify_output_text.strip(),
        },
        "artifacts": {
            "events_jsonl": "events.jsonl",
            "stderr_log": stderr_name,
            "final_text": final_text_name,
            "verify_log": "verify.log",
            "generated_dir": "generated",
            "screenshot": screenshot_name,
        },
        "output": {
            "expected_file": str(html_path.relative_to(temp_dir)),
            "exists": html_path.exists(),
        },
    }
    (result_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    if bench == "vague-developer":
        judge_proc = sh(
            [
                sys.executable,
                str(JUDGE_VAGUE),
                "--result-dir",
                str(result_dir),
                "--judge-provider",
                args.judge_provider,
            ],
            cwd=REPO_ROOT,
            timeout=900,
            merge_stderr=False,
        )
        if judge_proc.stdout.strip():
            print(judge_proc.stdout.strip())
        if judge_proc.stderr.strip():
            print(judge_proc.stderr.strip(), file=sys.stderr)
        if judge_proc.returncode != 0:
            raise SystemExit(judge_proc.returncode)
        metadata = json.loads((result_dir / "metadata.json").read_text(encoding="utf-8"))

    status = "PASS" if verified else "FAIL"
    if bench == "vague-developer" and metadata.get("judgment"):
        judgment = metadata["judgment"]
        print(
            f"[{bench}] {slug}: strict {status} | judged {judgment.get('score')}/20 {judgment.get('band')} | "
            f"{format_stats_summary(stats)}"
        )
    else:
        print(f"[{bench}] {slug}: {status} | {format_stats_summary(stats)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
