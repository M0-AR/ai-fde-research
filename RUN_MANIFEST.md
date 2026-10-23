# Run manifest

## Live run (completed)

- Start: 2026-10-22 10:53:53 UTC (recorded at launch as 13:53:53 local, Asia/Riyadh UTC+03)
- First episode: 2026-10-22T10:55:00+00:00
- Last episode: 2026-10-22T17:10:38+00:00
- Command: `PYTHONPATH=src python3 -m fde_research.benchmark --models qwen2.5-1.5b --no-resume`
- Screen session: `fdebench` (PID 739927)
- Python process: PID 739930
- Model: `qwen2.5:1.5b` (Ollama ID `65ec06548149`, 986 MB)
- Ollama: 0.23.2
- Python: 3.12.13
- Seed: 20261022
- Temperature: 0.0
- Max tokens: 900
- Request timeout: 180 s
- Total planned episodes: 192 (1 model x 4 policies x 48 tasks)
- Completed episodes: 192
- Status: complete; analysis uses the frozen archive below
- Live file: `results/benchmark_episodes.jsonl` (append-only run log)

## Protective snapshot

- Path: mid-run snapshot (not distributed; superseded by the final freeze)
- SHA-256: `2fbabc59f6c591de5c5bb289231a99aaf59a88d27893e0bf3496f295cca2697c`
- Rows: 132
- Note: this is a mid-run copy, not the final analysis snapshot.

## Final freeze

- Path: `results/frozen/benchmark_episodes_final.jsonl`
- SHA-256: `20a6739ab4511d4264426a12edef0fbd684628caa5310f5af52ae0a3c0e38a21`
- Rows: 192
- Policies: `ungoverned` (48), `verified` (48), `governed` (48), `fde_disciplined` (48)
- Model IDs: `qwen2.5-1.5b` (192)
- Schema version: 2
- Errors: 15
- Frozen at: 2026-10-23T10:57:48Z
- Summary: `results/frozen/benchmark_summary_final.json`
- Manifest: `results/frozen/manifest_final.json`

## Provenance notes

- The original launch note labelled local time as UTC. The corrected UTC start is approximately 10:53, consistent with the first episode at 10:55 UTC.
- The original note recorded PID 739930; the historical `.pid` file records 595465. Both are process identifiers, not data.
- The live JSONL was not overwritten by the freeze tool. The frozen archive is normalized to schema v2 and hashed.
- The 15 parse errors are preserved in the frozen archive and reported as warnings, not discarded.
