# go-bench summary

Generated from `results/*/*/metadata.json`.

## strict-custom-agent

| Model | Status | Time | Tokens in→out | Tools | LLM calls | Artifacts |
|---|---:|---:|---:|---:|---:|---|
| Claude Code Sonnet | PASS | 47.9s | 9→3100 | 2 | 3 | [dir](results/strict-custom-agent/claude-bin-sonnet) [log](results/strict-custom-agent/claude-bin-sonnet/run.log) [shot](results/strict-custom-agent/claude-bin-sonnet/screenshot.png) |
| Claude Code Haiku | PASS | 29.2s | 30→4200 | 2 | 3 | [dir](results/strict-custom-agent/claude-bin-haiku) [log](results/strict-custom-agent/claude-bin-haiku/run.log) [shot](results/strict-custom-agent/claude-bin-haiku/screenshot.png) |
| Ollama Gemma 4 26B | FAIL | 256.6s | 468000→27000 | 22 | 23 | [dir](results/strict-custom-agent/ollama-gemma4-26b) [log](results/strict-custom-agent/ollama-gemma4-26b/run.log) [shot](results/strict-custom-agent/ollama-gemma4-26b/screenshot.png) |
| Venice Kimi K2.5 | PASS | 58.2s | 12000→4100 | 2 | 3 | [dir](results/strict-custom-agent/venice-kimi-k2-5) [log](results/strict-custom-agent/venice-kimi-k2-5/run.log) [shot](results/strict-custom-agent/venice-kimi-k2-5/screenshot.png) |
| Venice GLM 5.1 | PASS | 17.5s | 6870→2695 | 2 | 3 | [dir](results/strict-custom-agent/venice-glm-5-1) [final](results/strict-custom-agent/venice-glm-5-1/final.txt) [events](results/strict-custom-agent/venice-glm-5-1/events.jsonl) [shot](results/strict-custom-agent/venice-glm-5-1/screenshot.png) |
| Venice Minimax M27 | PASS | 59.6s | 12203→3556 | 2 | 3 | [dir](results/strict-custom-agent/venice-minimax-m27) [final](results/strict-custom-agent/venice-minimax-m27/final.txt) [events](results/strict-custom-agent/venice-minimax-m27/events.jsonl) [shot](results/strict-custom-agent/venice-minimax-m27/screenshot.png) |
| Venice Qwen 3.6 Plus | PASS | 58.0s | 19349→2686 | 2 | 3 | [dir](results/strict-custom-agent/venice-qwen-3-6-plus) [final](results/strict-custom-agent/venice-qwen-3-6-plus/final.txt) [events](results/strict-custom-agent/venice-qwen-3-6-plus/events.jsonl) [shot](results/strict-custom-agent/venice-qwen-3-6-plus/screenshot.png) |
| Venice Qwen3 Coder 480B | FAIL | 13.5s | 0→0 | 0 | 0 | [dir](results/strict-custom-agent/venice-qwen3-coder-480b) [events](results/strict-custom-agent/venice-qwen3-coder-480b/events.jsonl) [stderr](results/strict-custom-agent/venice-qwen3-coder-480b/stderr.log) |
| Venice Claude Opus 4.7 | PASS | 51.2s | 24000→4600 | 4 | 5 | [dir](results/strict-custom-agent/venice-claude-opus-4-7) [log](results/strict-custom-agent/venice-claude-opus-4-7/run.log) [shot](results/strict-custom-agent/venice-claude-opus-4-7/screenshot.png) |
| Venice Grok 4.20 | PASS | 103.6s | 25000→13000 | 7 | 8 | [dir](results/strict-custom-agent/venice-grok-4-20) [log](results/strict-custom-agent/venice-grok-4-20/run.log) [shot](results/strict-custom-agent/venice-grok-4-20/screenshot.png) |

## vague-developer

| Model | Status | Time | Tokens in→out | Tools | LLM calls | Artifacts |
|---|---:|---:|---:|---:|---:|---|
| Claude Code Haiku | FAIL | 29.9s | 20→4400 | 1 | 2 | [dir](results/vague-developer/claude-bin-haiku) [log](results/vague-developer/claude-bin-haiku/run.log) [shot](results/vague-developer/claude-bin-haiku/screenshot.png) |
| Venice Kimi K2.5 | FAIL | 45.8s | 8300→4613 | 1 | 2 | [dir](results/vague-developer/venice-kimi-k2-5) [final](results/vague-developer/venice-kimi-k2-5/final.txt) [events](results/vague-developer/venice-kimi-k2-5/events.jsonl) [shot](results/vague-developer/venice-kimi-k2-5/screenshot.png) |
| Venice GLM 5.1 | FAIL | 50.2s | 4012→6262 | 4 | 5 | [dir](results/vague-developer/venice-glm-5-1) [final](results/vague-developer/venice-glm-5-1/final.txt) [events](results/vague-developer/venice-glm-5-1/events.jsonl) [shot](results/vague-developer/venice-glm-5-1/screenshot.png) |
| Venice Minimax M27 | FAIL | 103.6s | 17618→5765 | 7 | 8 | [dir](results/vague-developer/venice-minimax-m27) [final](results/vague-developer/venice-minimax-m27/final.txt) [events](results/vague-developer/venice-minimax-m27/events.jsonl) |
| Venice Qwen 3.6 Plus | FAIL | 122.1s | 26235→6273 | 2 | 3 | [dir](results/vague-developer/venice-qwen-3-6-plus) [final](results/vague-developer/venice-qwen-3-6-plus/final.txt) [events](results/vague-developer/venice-qwen-3-6-plus/events.jsonl) [shot](results/vague-developer/venice-qwen-3-6-plus/screenshot.png) |
| Venice Qwen3 Coder 480B | FAIL | 18.9s | 4897→73 | 1 | 1 | [dir](results/vague-developer/venice-qwen3-coder-480b) [final](results/vague-developer/venice-qwen3-coder-480b/final.txt) [events](results/vague-developer/venice-qwen3-coder-480b/events.jsonl) [stderr](results/vague-developer/venice-qwen3-coder-480b/stderr.log) |
| Venice Claude Opus 4.7 | FAIL | 80.8s | 14508→7592 | 1 | 2 | [dir](results/vague-developer/venice-claude-opus-4-7) [final](results/vague-developer/venice-claude-opus-4-7/final.txt) [events](results/vague-developer/venice-claude-opus-4-7/events.jsonl) [shot](results/vague-developer/venice-claude-opus-4-7/screenshot.png) |
| Venice Grok 4.20 | FAIL | 69.2s | 15692→12872 | 7 | 6 | [dir](results/vague-developer/venice-grok-4-20) [final](results/vague-developer/venice-grok-4-20/final.txt) [events](results/vague-developer/venice-grok-4-20/events.jsonl) [shot](results/vague-developer/venice-grok-4-20/screenshot.png) |

## Notes

- The strict bench uses a custom agent plus a custom verifier tool.
- The vague bench uses a frozen local copy of the built-in developer agent, not the floating `@developer` alias.
- Benchmark telemetry comes from `term-llm ask --json`; newer runs store raw events in `events.jsonl`.
- `venice:kimi-2.7` was probed separately and returned 404; Venice currently suggests `kimi-k2-5` or `kimi-k2-thinking`.

