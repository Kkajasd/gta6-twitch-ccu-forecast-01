# GTA VI Twitch CCU forecast — tests

Run 2026-11-17 (UTC). Entry: `main.py`, Python 3.13 stdlib only.
All commands run from `~/workspace/makefun/gta6-twitch-ccu-forecast-01/`
unless stated. Local Python here is 3.12.3; the code uses no 3.13-only
features (no `typing` extras, no new syntax).

## 1. Practice-case run (format + runtime)

```
MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

- 4/4 cases produced (`p00.out`–`p03.out`, 1,450–1,546 bytes each).
- Total wall time 0.212 s for 4 cases (~53 ms/case; limit 8,000 ms/case).
- Single-case run (only `p02.in` in the dir, as the grader does):
  0.081 s, output written.

## 2. Output format validation

Checked programmatically for all 4 outputs: exactly one top-level key
`hours`; exactly 23 rows, hours 2–24 each once; each row exactly 5
quantiles, all finite, `0 < q <= 1e9`, non-decreasing; every file
≤ 65,536 bytes. All VALID.

## 3. Determinism

Two consecutive runs over the practice inputs: outputs byte-identical
(`diff -r` clean).

## 4. Fallback (no comparables)

A case with `comparables: []` forecasts exactly the house baseline:
hour 2 `[78133.6, 90384.26, 100000, 110638.73, 127985.91]` and hour 24
`[30624.45, 61578.43, 100000, 162394.53, 326536.46]` for p1 = 100,000 —
identical to the example in `competition.yaml`.

## 5. Leave-one-out validation (`tools/validate.py`, imports shipped `main.py`)

Pinball loss on log scale, mean over 23 hours × 5 levels. Each target
curve's hour-1 print is the input; its real hours 2–24 are the answer.

### Console-only clean targets (n=7) — GTA VI's stratum

| Launch | hour-1 print | Model | Flat baseline |
|---|---|---|---|
| FINAL FANTASY VII REBIRTH | 53,526 | 0.1911 | 0.1734 |
| Ghost of Tsushima | 131,910 | 0.0976 | 0.2283 |
| Ghost of Yōtei | 27,206 | 0.1389 | 0.4734 |
| Saros | 6,400 | 0.1378 | 0.6011 |
| Stellar Blade | 27,057 | 0.1415 | 0.3725 |
| The Last of Us Part II | 365,019 | 0.1887 | 0.2470 |
| Zelda: Tears of the Kingdom | 129,948 | 0.2048 | 0.3087 |
| **Mean** | | **0.1572** | **0.3435** |
| **Median** | | **0.1415** | **0.3087** |

Model beats flat by 54.2% (mean and median); beats flat on 6/7 curves.

### All 37 comparable targets (context — includes PC-unlock curves)

Model mean 0.6618 / median 0.3164 vs flat mean 0.9297 / median 0.3248
(+28.8% mean, +2.6% median). The model is tuned for the console stratum;
PC-simultaneous-unlock curves are out of stratum and drag the all-curve
mean (their hour-1 prints can precede the main unlock, so their days
explode 100–400× — the flat mean of 0.93 is dominated by those outliers;
its median is 0.32).

## 6. Practice-case forecast medians (unscored — answers are server-side)

| Case | hour-1 | h2 | h6 | h12 | h19 | h24 |
|---|---|---|---|---|---|---|
| p00 Wolverine | 23,357 | 19,468 | 21,766 | 30,431 | 79,519 | 57,200 |
| p01 Red Dead Redemption 2 | 116,550 | 94,740 | 109,950 | 109,640 | 233,386 | 201,596 |
| p02 God of War Ragnarök | 269,517 | 216,237 | 255,885 | 213,933 | 409,206 | 388,866 |
| p03 Spider-Man 2 | 119,087 | 96,770 | 112,362 | 111,539 | 236,777 | 205,027 |

Shape is sane: night dip (h2 ≈ 0.8× hour 1), midday ≈ hour 1, evening
peak at h19 (≈ 2–3.4× hour 1), easing into h24.

## 7. What was NOT tested

- Practice-case scores: the answers are not in the kit (server-side only).
- The house AI model forecast: not measurable locally.
- The final case h00 (does not exist yet; cut at the 2026-11-19 01:00 UTC
  deadline from the live recording).
