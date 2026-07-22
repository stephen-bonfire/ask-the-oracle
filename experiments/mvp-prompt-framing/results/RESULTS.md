# MVP Prompt Framing — Results

**What:** Scored output of the 15-cell DOE (5 framings × 3 probe tasks). **Provenance:** fleet of 30 Opus subagents (15 blind responders → 15 uniform scorers), run 2026-07-21. **Status:** analysis only; `chatbot_launcher.py` unchanged. Raw deliverables in `results/<condition>__<prompt>/`.

## Line count (over-engineering proxy — lower = leaner)

| Condition | P1 images | P2 web app | P3 nginx log | Total | Files (P1/P2/P3) |
|---|---|---|---|---|---|
| none (control) | 139 | 186 | 112 | **437** | 1 / 1 / 1 |
| current (baseline) | 74 | 146 | 107 | **327** | 1 / 1 / 1 |
| E (time + scope-cut) | 41 | 63 | 36 | **140** | 2 / 1 / 1 |
| F (one-shot / one-file) | 187 | 108 | 75 | **370** | 1 / 1 / 1 |
| EF (combined) | 56 | 70 | 41 | **167** | 2 / 1 / 1 |

## Correctness (the guard — did the aggressive framings break anything)

| Condition | P1 images | P2 web app | P3 nginx log |
|---|---|---|---|
| none | ✅ correct | ✅ correct | ✅ correct |
| current | ❌ **EXIF bug** — `getexif()` misses `DateTimeOriginal`; falls back to mtime | ✅ correct | ✅ correct |
| E | ✅ correct | ✅ correct | ⚠️ cross-month row ordering (string-sorted; disclosed) |
| F | ✅ correct (hand-rolled EXIF parser) | ✅ correct | ⚠️ cross-month ordering (disclosed) |
| EF | ❌ **EXIF bug** (same as current) | ✅ correct | ❌ **fatally broken** — regex never matches; prints "no parseable lines" |

## What each corner resolved

- **P1 (the signal — over-engineering suppression).** `none` was correct but the most verbose (139 lines). `E` and `F` both got it correct *and* short-ish — but note `F` went the wrong way: its "single file / minimal dependencies" mandate forced it to **hand-roll a 187-line EXIF/TIFF byte parser** rather than call Pillow. Constraint satisfied, complexity *up*. `E` (41 lines, Pillow allowed) is the clean win. `current` and `EF` produced terse code that silently broke the headline feature.

- **P2 (domain-fit).** A reading-time app is naturally one HTML file, so the one-shot constraint never bit. Everyone correct; `E`/`EF` leanest (63/70 lines) vs `none` at 186. This is where framing helps cheaply.

- **P3 (the over-suppression guard).** The smoking gun. `EF` — the most aggressive framing — cut scope so hard the regex never matched a real nginx line; the tool runs but returns nothing on its own documented input. `E` had only a minor, self-disclosed ordering issue. `F`/`current`/`none` were correct.

## Verdict

**Ship `E`.** It delivered the largest concision gain (140 total lines vs 327 baseline, ~57% leaner) with **no correctness regressions** — and on P1 it was one of only two framings to get the EXIF feature *right* where the current string got it wrong.

Two framings to avoid:
- **`F` / one-file-no-deps** backfires: when the natural solution needs a library, the hard constraint induces a from-scratch reimplementation (P1's 187-line EXIF parser). More code, not less.
- **`EF`** over-suppresses into broken output (P1 EXIF bug + P3 fatally broken regex). Combining the time-box with the one-file mandate is worse than either alone.

The lever that worked is **E's "simplest thing that works + name the things to skip," while still allowing a sensible dependency and a second file.** The one-shot/one-file idea, though appealing in theory, is the thing that broke correctness in practice.

## Caveat

All responders were Opus 4.8. The launcher targets other models (Gemini, etc.) where raw over-engineering may be stronger, so absolute line counts won't transfer — but the *relative* ranking (E leanest-and-safe, EF over-cuts, F self-inflates) should hold.
