# MVP Prompt Framing Experiment

**What:** A design-of-experiments test of candidate `MVP_CONTEXT` injection strings for `chatbot_launcher.py`. **Provenance:** designed in chat 2026-07-21; run by a fleet of subagents. **Status:** experiment only — `chatbot_launcher.py` is NOT modified.

## Problem

The current MVP string ("working prototype by end of day today") anchors higher-effort models on ~8 hours of runway, so they over-engineer. Goal: a framing that yields something runnable in <30 min (1 hr max).

## Design

Two-stage per cell: a **responder** agent role-plays a coding assistant answering the user's message (blind to the experiment) and writes its deliverable to disk; a **scorer** agent reads the deliverable and scores it uniformly.

### Factors driving variation (the resolution space)

| Factor | Low | High |
|---|---|---|
| Scope openness | bounded | open-ended |
| Structural shape | single-file-natural | multi-file / web-natural |
| Intrinsic complexity floor | trivial | high (real irreducible logic) |

### Probe tasks (one per corner)

| ID | Prompt | Isolates |
|---|---|---|
| P1 | Build a tool that takes a folder of images and renames them by date taken. | The signal — over-engineering suppression when scope is open + floor is low |
| P2 | Build a web app where I paste in text and it shows me the reading time. | Domain-fit — does a one-file constraint fight a multi-file domain |
| P3 | Build a tool that parses an nginx access log and shows me the error rate per hour. | Over-suppression — does aggressive framing cut necessary logic into wrongness |

### Conditions (framings appended to the prompt)

| ID | Framing |
|---|---|
| none | (nothing appended — raw behavior control) |
| current | Existing `MVP_CONTEXT` — the baseline to beat |
| E | Time-box + explicit scope cuts |
| F | One-shot / single-file deliverable constraint |
| EF | E + F combined (chat recommendation) |

5 conditions × 3 prompts = **15 cells**.

### Metrics (scored per cell)

- `file_count`, `dep_count`, `line_count` — objective bloat proxies
- `runs_as_is` — would it run with no edits
- `scope_verdict` — under-built / right-sized / over-engineered
- `correctness_notes`, `over_engineering_signals`

### Reading the corners

- **P1** shows where the framing helps most.
- **P2** shows where it distorts structural shape.
- **P3** shows where it goes too far.

Ship the framing that wins P1, survives P2, and does not break P3.

## Caveat

Responder agents are all the current session model (Opus), so this measures the framing's effect on one model — a proxy for the multi-model launcher (Gemini, etc.). Directional, not absolute.

## Output

Per-cell deliverables under `results/<condition>__<prompt>/`; synthesized comparison in `results/RESULTS.md`.

---

## Round 2 (2026-07-21)

Round 1 conflated two axes under "one-shot": output shape (one file / minimal deps — over-constrains, tested) vs interaction/completeness (one well-scoped prompt → model self-scopes and delivers finished end-to-end — untested). Round 2 tests the second axis, with framings written in all-positive phrasing (no negatives) since LLMs follow positive instructions more reliably.

### Conditions

| ID | Framing |
|---|---|
| none | control |
| E | Round-1 winner, with second "minimal" → "working" |
| G | Self-scoped one-shot completeness (all-positive; no file/dep cap) |
| H | Scope-first one-shot (states scope/assumptions, then builds) |

### Probes

P1–P3 carried over; **P4** added — an expense tracker web app (add expense w/ category+amount, running list, per-category totals, persist across reloads) — a genuine multi-component project so the one-shot idea has planning headroom to prove itself.

### Metric added

`feature_complete` — are ALL requested features implemented and wired end-to-end (nothing stubbed/faked/TODO). This is the axis the one-shot framing is meant to win.

### Setup

All responders at Opus **high effort** (honors the extended-thinking-frontier premise); output to `results/round2/`.
