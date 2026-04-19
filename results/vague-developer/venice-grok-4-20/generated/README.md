This directory is intentionally sparse: each vague benchmark run starts from a nearly blank working directory.

The important exception is `agent/`, which is a frozen copy of the built-in `developer` agent from term-llm.
It was copied into this repo on 2026-04-19 from:

- `internal/agents/builtin/developer/agent.yaml`
- `internal/agents/builtin/developer/system.md`
- source tree commit: `46e891e`

Why: `@developer` is a floating target that changes as term-llm evolves. The benchmark should pin the exact agent prompt/tool surface instead of silently drifting with upstream changes.
