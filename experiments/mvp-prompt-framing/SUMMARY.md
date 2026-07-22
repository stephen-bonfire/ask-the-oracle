# POC Prompt Framing Experiment — Summary

**What:** A two-round design-of-experiments study to rewrite the launcher's POC (formerly "MVP") context-injection string so higher-effort models stop over-engineering throwaway prototypes. **Provenance:** designed and run in Claude Code on 2026-07-21; 62 subagents total across two workflow fleets. **Status:** complete — winning framing shipped to `chatbot_launcher.py` (`POC_CONTEXT`). Full per-cell deliverables and per-round write-ups in `results/` and `results/round2/`.

## Problem

The original string — *"This is for a minimum viable product (MVP) where we want a working prototype working by end of day today."* — anchored models on ~8 hours of runway, so extended-thinking models spent that budget and over-built. Goal: a framing that yields something runnable in under 30 minutes (1 hr max) without cutting so far that the result is wrong.

## Method

Design-of-experiments: pick probe tasks that sit at different corners of the space where a framing can succeed or fail (scope openness × structural shape × intrinsic complexity floor), then run every candidate framing through every probe. Each cell used a **blind responder** subagent (role-plays a coding assistant answering the user, unaware of the experiment, writes its real deliverable to disk) followed by a **uniform scorer** subagent (reads the files, grades objectively: line/file/dependency counts, runs-as-is, feature-complete, scope verdict, correctness notes).

### Probes

| ID | Task | Isolates |
|---|---|---|
| P1 | Rename a folder of images by date taken | Over-engineering suppression (open scope, low floor) + a hidden EXIF correctness trap |
| P2 | Web app: paste text → reading time | Domain-fit for a single-file constraint |
| P3 | Parse nginx access log → error rate per hour | Over-suppression guard (real irreducible parsing/aggregation logic) |
| P4 | Expense tracker web app (add, list, per-category totals, persist) | Higher-ceiling multi-component project (round 2 only) |

## Round 1 — five framings, three probes

Framings: `none` (control), `current` (original string), `E` (time-box + explicit scope cuts), `F` (one-shot / single-file / minimal-deps), `EF` (E+F combined).

**Key results:**
- **`F` and `EF` backfired via an *output-shape* constraint.** Forcing "one self-contained file, minimal dependencies" made `F` hand-roll a 187-line EXIF byte-parser instead of calling Pillow (complexity *up*), and made `EF` cut so hard its nginx regex never matched a real log line (`P3` fatally broken, silently returned nothing).
- **`current` and `EF` silently broke the P1 EXIF feature.**
- **`E` was leanest with no correctness regressions** — ~57% fewer lines than the baseline.
- **Lesson:** don't over-suppress the floor; the winning lever is "simplest thing that works + name what to skip," not a hard file/dependency cap.

## Round 2 — testing the *real* one-shot idea

Round 1 conflated two axes under "one-shot": **output shape** (one file/minimal deps — tested, over-constrains) vs **interaction/completeness** (one well-scoped prompt → the model self-scopes and delivers a finished project end-to-end, no round-trips — untested). Round 2 tested the second axis with all-positive phrasing (LLMs follow positive instructions more reliably than negatives).

Framings: `none`, `E` (fixed: second "minimal" → "working"), `G` (self-scoped one-shot completeness), `H` (scope-first: state assumptions, then build). Added `P4` so the one-shot idea had planning headroom, and a `feature_complete` metric.

**Total lines (leanness proxy):** `E` = **193**, `none` = 774, `G` = 1621, `H` = 1563.

**Key results:**
- **The one-shot-completeness framings backfired in a POC context.** "Deliver a finished project end-to-end, as many files as needed" read as *build the production version*: installable packages, pytest suites, CSV/JSON output, ANSI color, a SQLite client-server for P4. `G`'s log parser was 10 files/371 lines; `H`'s renamer 8 files/410 lines — ~8× `E`.
- **P4 did not rescue the idea.** The higher-ceiling probe was meant to expose `E` under-delivering on real multi-component work. Instead `E` shipped a feature-complete, correctly-persisting expense app in **76 lines / 1 file**, while `G` spent 451 lines + a SQLite server for the same functional bar.
- **One nugget:** `H`'s scope-first framing was the *only* condition to read the EXIF sub-IFD correctly on P1 (all others hit the pervasive `getexif()`-only-IFD0 trap) — an explicit reasoning pass improved correctness on the one hard bit, but arrived bundled with the worst over-engineering.

## Conclusions

1. **Winner: `E`.** Leanest by a wide margin and feature-complete across all probes including the higher-ceiling P4. Shipped as `POC_CONTEXT`.
2. **Reframe deadlines as minutes, not "today."** Any full-day anchor invites a full day of scope.
3. **Name what to skip.** Explicit omissions (auth, tests, error handling, config, abstractions) constrain harder than a deadline alone.
4. **Do not constrain output shape.** Hard "one file / no dependencies" rules either inflate code (reinventing libraries) or break correctness.
5. **One-shot-completeness ≠ POC.** Telling a frontier model to "deliver a finished project end-to-end" produces production-grade builds — completeness at the cost of exactly the over-engineering the POC tag exists to prevent.
6. **Open thread:** a hybrid of `E` + a lightweight "state key decisions first" nudge (without G/H's finished-project language) might capture `H`'s correctness win without the bloat — untested.

## Shipped framing

> This is a throwaway proof-of-concept that needs to be running in under 30 minutes — 1 hour absolute max. Do the simplest thing that works: single file if possible, hardcode where reasonable, minimal dependencies. Skip auth, tests, error handling, config, and abstractions unless they're essential to demonstrate the core idea. Getting a working version running now beats doing it "right."

## Caveat

All responders were Opus 4.8 (round 2 at high effort). The launcher targets other models where absolute sizes differ, but the ranking (E leanest-and-complete; one-shot framings over-build) should hold.
