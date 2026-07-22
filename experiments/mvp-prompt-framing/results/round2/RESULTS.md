# MVP Prompt Framing — Round 2 Results

**What:** Scored output of the round-2 DOE (4 framings × 4 probes) testing one-shot-*completeness* framings (G, H — all-positive) against E (round-1 winner, fixed) and a control. **Provenance:** 32 Opus subagents at high effort (16 blind responders → 16 uniform scorers), run 2026-07-21. **Status:** analysis only; `chatbot_launcher.py` unchanged. Raw deliverables in `results/round2/<condition>__<prompt>/`.

## Size (over-engineering proxy — lines / files / third-party deps)

| Condition | P1 images | P2 web app | P3 nginx log | P4 expense app | Total lines |
|---|---|---|---|---|---|
| none (control) | 160 / 1 / 1 | 173 / 3 / 0 | 107 / 1 / 0 | 334 / 3 / 0 | **774** |
| **E** (time+scope, fixed) | 35 / 2 / 1 | 45 / 1 / 0 | 37 / 1 / 0 | 76 / 1 / 0 | **193** |
| G (one-shot completeness) | 468 / 6 / 3 | 331 / 3 / 0 | 371 / 10 / 1 | 451 / 4 / 1 | **1621** |
| H (scope-first one-shot) | 410 / 8 / 3 | 340 / 5 / 0 | 356 / 9 / 1 | 457 / 3 / 0 | **1563** |

## Feature-complete + correct (the two things one-shot was meant to win)

| Condition | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| none | complete but **EXIF bug** | ✅ | ✅ | ✅ persistence genuine |
| E | complete but **EXIF bug** | ✅ | ✅ | ✅ persistence genuine (76 lines) |
| G | complete but **EXIF bug** | ✅ | ✅ | ✅ (SQLite server) |
| H | ✅ **EXIF correct** | ✅ | ✅ | ✅ (localStorage) |

Every condition was feature-complete on P2/P3/P4. Scorers marked *every* cell "right-sized" — that axis is too lenient (it rationalizes each addition as "defensible"); the `over_engineering_signals` list and the size table are the real signal.

## What we learned

**1. The one-shot-completeness framings backfire in an MVP context.** G and H unleashed full production builds: installable packages, pytest suites, ANSI color with TTY detection, CSV/JSON output formats, a SQLite client-server stack for P4. G's log parser is **10 files / 371 lines**; H's image renamer is **8 files / 410 lines**. That is ~8× E's size and is precisely the over-engineering the MVP tag exists to suppress. "Deliver a finished project end-to-end, as many files as the clean solution needs" reads to the model as "build the production version."

**2. The higher-ceiling probe (P4) did NOT rescue the one-shot idea.** The hypothesis was that E would under-deliver on a real multi-component project where end-to-end planning pays off. It didn't: **E delivered a feature-complete, correctly-persisting expense app in 76 lines / 1 file** — genuine localStorage persistence, correct per-category totals, no stubs. G spent 451 lines and a SQLite server to reach the same functional bar. On the exact task designed to expose E's weakness, E won.

**3. One real nugget for H.** The scope-first framing ("state assumptions, then build") was the *only* condition to get the EXIF sub-IFD read correct on P1 — every other framing (none, E, G) hit the pervasive `getexif()`-only-reads-IFD0 trap and silently renamed by mtime. Forcing an explicit reasoning pass improved correctness on the one genuinely tricky bit. But that gain arrived bundled with the heaviest over-engineering, so H is not shippable as-is.

## Verdict

**Ship E** (the fixed "…doing it 'right.'" → "Getting a *working* version running now…" variant). It is the leanest by a wide margin (193 total lines vs 1621/1563 for the one-shot framings) and was feature-complete everywhere, including the higher-ceiling P4. The one-shot-completeness idea delivers completeness but pays for it in exactly the over-engineering we set out to kill, and E already reaches completeness without that cost.

**Open thread (optional round 3):** H's "briefly state key assumptions, then build" clause was the only thing that fixed the EXIF correctness trap. A hybrid — E's scope discipline **plus** a lightweight "think through the key decisions first" nudge, *without* G/H's "finished production project / as many files as needed" language — might capture that correctness win without the bloat. Worth a small test if correctness-on-tricky-logic matters more than raw leanness.

## Caveat

All responders were Opus 4.8 at high effort. The launcher targets other models where absolute sizes will differ, but the ranking (E leanest-and-complete; one-shot framings over-build) should hold.
