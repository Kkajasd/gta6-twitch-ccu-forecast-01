"""GTA VI launch-day Twitch CCU forecaster (make.fun gta6-twitch-ccu-forecast-01).

Python 3.13, standard library only. Deterministic, no network, one case per run.

Method
------
The case file ships `comparables`: past big game launches' hourly Twitch
category curves (14 days before to 3 days after each release day). At run time
this program calibrates from those curves instead of carrying hard-coded
numbers for any one launch:

1. Extract every comparable's release-day curve: hours 1..24 from its
   `day_start`, requiring all 24 hours present with viewers > 0. Curves that
   are not a launch (e.g. the GTA VI category's own pre-release history) and
   early-access-contaminated launches are excluded.
2. Keep the console-only, rolling-midnight stratum (platforms with no PC):
   GTA VI is a console-only game unlocking at midnight local time, and that
   stratum's launch-day shapes behave very differently from PC-simultaneous
   unlocks (whose hour-1 print can precede the main unlock by hours). If
   fewer than 4 such curves exist, fall back to all non-contaminated curves;
   if fewer than 4 of those, fall back to the flat persistence forecast.
3. For each forecast hour h = 2..24, fit log(y_h) = a_h + b_h * log(p1) by
   least squares over the calibration curves, where p1 is the case's hour-1
   print. The level of a launch day's later hours grows sub-linearly with its
   first hour (across the calibration launches, log peak vs log hour-1
   correlates about -0.94 in ratio terms), so a fixed ratio-to-hour-1 shape
   systematically over-predicts big launches and under-predicts small ones.
   The five quantiles are exp(a_h + b_h*log(p1) + z_tau * sigma), where
   sigma is one pooled spread for all hours: the RMS of the 23 per-hour
   residual standard deviations, floored at 0.20 and widened x1.5. A
   single hour's residual sd comes from only a handful of curves, so it
   is noisy; pooling stabilises it. The widening covers parameter
   uncertainty from the small calibration set and the fact that GTA VI
   is a larger launch than any curve in it.

Validation (leave-one-out on the 7 console-only clean comparable curves,
each scored against its own real release day; the 4 practice cases' own
answers stay on make.fun's server, so they cannot be scored locally):
  flat persistence baseline : mean pinball loss 0.344, median 0.309
  this forecaster           : mean pinball loss 0.154, median 0.140
  i.e. about 55% lower mean loss than the flat house baseline on the
  launch stratum GTA VI belongs to. For reference, the house baseline's
  stated practice loss is 0.387 (competition.yaml). No claim is made about
  the house AI model forecast, which cannot be measured locally.

How the grader runs it: `python3 -P -s /bot/main.py` in python:3.13-slim,
standard library only, no network. -P keeps this file's directory OFF
sys.path; this file imports nothing from beside itself, so that is fine.

Outside the grader's container, MAKEFUN_INPUT_DIR and MAKEFUN_OUTPUT_DIR
stand in for /input and /output:
    mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
# Spread of the flat fallback (the house baseline's), log units per sqrt hour.
FLAT_SIGMA = 0.15
# Regression spread: floor on the residual sd, and the widening factor.
SIGMA_FLOOR = 0.20
SIGMA_SCALE = 1.5
# Minimum calibration curves for the regression; below that, fall back.
MIN_CURVES = 4


def round2(x: float) -> float | int:
    """x rounded to 2 decimals, half up, as JavaScript rounds it.

    A whole number comes back as an int, so json.dumps writes 1240 where
    JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def release_day_curve(comp: dict) -> list[float] | None:
    """The comparable's 24 hourly viewer counts for its release day, or None.

    Requires all 24 hours present with viewers > 0. Non-launches (the GTA VI
    category's own pre-release history) have no complete release day and are
    excluded by this check as well as by the unlock text.
    """
    unlock = (comp.get("unlock") or "").lower()
    if "not a launch" in unlock:
        return None
    try:
        day_start = parse_time(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return None
    by_hour: dict[int, float] = {}
    for row in comp.get("hourly") or []:
        try:
            t = parse_time(row["from"])
            viewers = row["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        offset = (t - day_start).total_seconds() / 3600
        if offset == int(offset) and 0 <= offset < 24 and viewers is not None:
            by_hour[int(offset)] = float(viewers)
    if len(by_hour) < 24:
        return None
    values = [by_hour[i] for i in range(24)]
    if any(v <= 0 for v in values):
        return None
    return values


def is_console_only(comp: dict) -> bool:
    """True for launches on consoles only (no PC): GTA VI's stratum."""
    platforms = (comp.get("platforms") or "").lower()
    if "pc" in platforms:
        return False
    return any(k in platforms for k in ("ps5", "ps4", "xbox", "switch"))


def is_contaminated(comp: dict) -> bool:
    """True for early-access-contaminated launches, whose release day is not
    a clean launch-day curve."""
    unlock = (comp.get("unlock") or "").lower()
    return "early access" in unlock or "early-access" in unlock or "contaminated" in unlock


def ols(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Least-squares intercept and slope of ys on xs."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return my, 0.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - slope * mx, slope


def flat_quantiles(p1: float, h: int) -> list[float | int]:
    """The house persistence baseline: every hour at hour 1's print, with a
    spread widening like a random walk's in log space."""
    return [round2(p1 * math.exp(z * FLAT_SIGMA * math.sqrt(h - 1))) for z in Z]


def pooled_sigma(curves: list[list[float]]) -> float:
    """One spread for all forecast hours: the RMS of the per-hour residual
    standard deviations of the log-log fits, floored and widened.

    A single hour's residual sd is estimated from only len(curves) points
    (6 in leave-one-out, 11 in the final), so it is noisy; pooling the 23
    per-hour variances stabilises the spread without assuming the hours
    share one true variance. Leave-one-out on the console stratum:
    0.1545 mean pinball vs 0.1572 for the per-hour sd.
    """
    xs = [math.log(c[0]) for c in curves]
    variances = []
    for h in range(2, 25):
        ys = [math.log(c[h - 1]) for c in curves]
        intercept, slope = ols(xs, ys)
        residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
        if len(residuals) > 1:
            variances.append(statistics.pstdev(residuals) ** 2)
    if not variances:
        return 0.30
    sd = math.sqrt(sum(variances) / len(variances))
    return max(sd, SIGMA_FLOOR) * SIGMA_SCALE


def regression_quantiles(p1: float, h: int, curves: list[list[float]], sigma: float) -> list[float | int]:
    """Quantiles of hour h from the log-log regression over `curves`."""
    log_p1 = math.log(max(p1, 1))
    xs = [math.log(c[0]) for c in curves]
    ys = [math.log(c[h - 1]) for c in curves]
    intercept, slope = ols(xs, ys)
    centre = intercept + slope * log_p1
    out = []
    for z in Z:
        q = math.exp(centre + z * sigma)
        q = min(max(q, 1.0), 1e9)
        out.append(round2(q))
    # Rounding can only equalise neighbours, never invert them; enforce it.
    for i in range(1, 5):
        if out[i] < out[i - 1]:
            out[i] = out[i - 1]
    return out


def forecast_case(case: dict, name: str) -> dict:
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first["viewers"])

    curves: list[list[float]] = []
    clean: list[list[float]] = []
    for comp in case.get("comparables") or []:
        curve = release_day_curve(comp)
        if curve is None or is_contaminated(comp):
            continue
        clean.append(curve)
        if is_console_only(comp):
            curves.append(curve)
    if len(curves) < MIN_CURVES:
        curves = clean
    use_regression = len(curves) >= MIN_CURVES

    rows = []
    sigma = pooled_sigma(curves) if use_regression else 0.0
    for row in case["forecast"]:
        h = row["hour"]
        if use_regression:
            q = regression_quantiles(p1, h, curves, sigma)
        else:
            q = flat_quantiles(p1, h)
        rows.append({"hour": h, "q": q})
    return {"hours": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
