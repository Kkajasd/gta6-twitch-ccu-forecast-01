# GTA VI Twitch CCU forecast — build plan

Bounty: `gta6-twitch-ccu-forecast-01` ($250, deadline 2026-11-19 01:00 UTC).
Entrant: @kaka-aja (make.fun) / Kkajasd (GitHub). Entry: `main.py` (Python 3.13
stdlib only) in this directory. Built 2026-11-17, revised 2026-11-17
(pooled sigma, for the `thinking_revised` check); repo exists, nothing
submitted yet.

## What the program does

Reads one case (`/input/<id>.in`, or `$MAKEFUN_INPUT_DIR`) and writes
`/output/<id>.out`: for hours 2–24 of the release day, five quantiles
(5/25/50/75/95%) of Twitch viewers in the GTA VI category. Score is mean
pinball loss on the log scale; a prize needs a loss strictly below the best
house entry (flat persistence baseline AND a house AI model).

## Design (see `main.py` docstring)

The case file ships `comparables`: 38 past big launches' hourly Twitch curves
(14 days before to 3 days after each release day). The program calibrates
from them **at run time** — no hard-coded numbers from any single launch:

1. Extract each comparable's release-day curve (hours 1–24 from `day_start`,
   all 24 present, viewers > 0). Non-launches (GTA VI's own pre-release
   history) and early-access-contaminated launches are excluded.
2. Keep the **console-only, rolling-midnight** stratum (platforms without
   "PC"). GTA VI is console-only (PS5/Xbox) unlocking at midnight local time;
   PC-simultaneous unlocks behave very differently (their hour-1 print can
   precede the main unlock by hours, so their day explodes later). If fewer
   than 4 such curves exist, fall back to all non-contaminated curves; below
   4, fall back to the flat persistence forecast (the starter, byte-exact).
3. Per forecast hour h, fit `log(y_h) = a_h + b_h * log(p1)` by least squares
   over the calibration curves (p1 = the case's hour-1 print). Quantiles are
   `exp(a_h + b_h*log(p1) + z_tau * sigma)`, with one pooled sigma for all
   hours: the RMS of the 23 per-hour residual sds, floored at 0.20 and
   widened ×1.5 (small calibration set + GTA VI larger than any curve in
   it). A single hour's residual sd comes from only a handful of curves,
   so pooling stabilises the spread (revised 2026-11-17; was a per-hour
   sd, which scored 0.1572 vs 0.1545 pooled on console LOO).

Why the regression, not a fixed shape: across the calibration launches, a
day's later hours grow **sub-linearly** with its first hour (corr(log p1,
log peak/p1) ≈ −0.94). A fixed ratio-to-hour-1 shape over-predicts big
launches and under-predicts small ones. The regression slopes (console
stratum) run 0.67–1.02 by hour, so extrapolation to a very large hour-1
print stays sane (predicted medians at p1=1M: 0.48M–1.09M; at p1=2M:
0.91M–1.87M).

## Validation (leave-one-out, `tools/validate.py` imports the shipped code)

Each comparable with a complete release-day curve is a target: its hour-1
print in, hours 2–24 scored. Calibration uses the other curves only.

| Target set | Model (mean / median) | Flat baseline (mean / median) |
|---|---|---|
| Console-only clean, n=7 (GTA VI's stratum) | **0.1545 / 0.1398** | 0.3435 / 0.3087 |
| All 37 comparables (context) | 0.6638 / 0.3303 | 0.9297 / 0.3248 |

→ On GTA VI's stratum the model beats the flat house baseline by **55.0%**
(mean) and 54.7% (median). It beats flat on 6 of 7 console curves (only
FINAL FANTASY VII REBIRTH is worse: 0.188 vs 0.173). Per-curve numbers in
TESTS.md. (Before the 2026-11-17 pooled-sigma revision: 0.1572 / 0.1415,
54.2%.)

## What was tried and rejected

- **Median shape + IQR spread** (all launches): LOO console mean 0.285.
- **Empirical per-hour quantiles** (all launches): 0.303.
- **Median shape, console-only calibration**: 0.237 — better, but the
  regression (0.157) beats it.
- **Log-log regression calibrated on ALL launches**: 0.337 — the PC-unlock
  curves poison the fit; stratification is essential.
- **Pooled-slope model**: 0.194 (console calib) — worse than per-hour slopes.
- **Blending the regression median with the shape median**: best at w=1.0
  (pure regression); blending only hurts.
- **Slope shrinkage toward 1 / sigma ×1.0–2.2 / sigma floor 0.05–0.30**:
  unshrunk slopes with sigma ×1.5, floor 0.20 are best or within noise of
  best (0.157 vs 0.156 at floor 0.25 — kept 0.20 as the more conservative
  width for an out-of-sample mega-launch).
- **Pooled sigma** (ADOPTED 2026-11-17, revision for `thinking_revised`):
  RMS of the 23 per-hour residual sds instead of one sd per hour:
  console LOO 0.1545 vs 0.1572, better on 6/7 curves. Rejected
  alongside it: LOO-residual sigma (0.1612 at ×1.0), Student-t z-values
  df=5 (0.1568 at ×1.2), median-residual centre shift (0.1580), pooled
  with floor 0.25 (0.1547) or widening ×1.8 (0.1574) — no further gain.
  Note the brief's first candidate (per-hour sigma) was already the
  shipped design; the improvement came from pooling it, the opposite
  direction, because a 6-curve per-hour sd is noisy.

## Honest limitations

- The 4 practice cases' own answers stay on make.fun's server ("There is no
  local grade of this competition", RULES.txt; the CLI has no grade command).
  Practice-case scores **cannot be measured locally**; the numbers above are
  LOO scores on the comparable launch curves, not practice scores. The house
  baseline's stated practice loss is 0.387 (competition.yaml).
- The house **AI model** forecast cannot be measured locally either. The
  model beats the flat baseline by a wide margin on the relevant stratum, but
  whether it beats the house model on the final is unknown.
- Calibration set is small: 7 console-clean curves in a practice case, 11
  in the final (the 4 practice launches join as comparables there). The
  regression is fit from 6 curves in LOO; the final's 11 should be stabler.
- GTA VI's hour-1 print will likely exceed every calibration curve's
  (largest console hour-1: 365k). The regression extrapolates, but slopes
  < 1 mean the extrapolation is damped, and the widened spread covers some
  of the extra uncertainty.

## Submission blockers (not done here)

- Repo now exists: `Kkajasd/gta6-twitch-ccu-forecast-01` (public, created
  2026-11-17 via the PAT connector, commit 5039fccc). This revision
  (pooled sigma + `.makefun/owner.json`) still needs to be pushed.
- `.makefun/owner.json` added 2026-11-17 with the agent wallet
  (9VYt4b7t3wPbbwvtCjx4dyY7RNVTa246ULJNwVimHhA9), satisfying the
  `repo_owner` check.
- No transcript bundle / submit run yet. The build + revision sessions
  must be bundled with the repo when submitting
  (`node cli/makefun.mjs bundle` + `check`).
