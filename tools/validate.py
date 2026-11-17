"""Validate the shipped main.py (imported, not copied) by leave-one-out scoring.

Each comparable launch with a complete release-day curve is a target: its
hour-1 print goes in as `known`, its hours 2..24 are the answer. The
forecaster is run through main.forecast_case with a case whose comparables
are all the others (mimics the real case file). Flat persistence baseline
scored the same way. Run: python3 tools/validate.py
"""
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path

ENTRY = Path(__file__).resolve().parent.parent
KIT = Path("/home/hatch/workspace/makefun/gta6-kit/gta6-twitch-ccu-forecast-01-kit")

spec = importlib.util.spec_from_file_location("entry_main", ENTRY / "main.py")
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]


def pinball(y, q, tau):
    d = math.log(max(y, 1)) - math.log(max(q, 1e-9))
    return 2 * max(tau * d, (tau - 1) * d)


def score(actual, rows):
    tot, n = 0.0, 0
    for h in range(1, 24):
        for tau, q in zip(LEVELS, rows[h - 1]["q"]):
            tot += pinball(actual[h], q, tau)
            n += 1
    return tot / n


def flat_rows(p1):
    return [{"hour": h, "q": [max(1, p1) * math.exp(z * 0.15 * math.sqrt(h - 1)) for z in Z]}
            for h in range(2, 25)]


def make_case(p1, comparables):
    return {
        "levels": LEVELS,
        "known": [{"hour": 1, "viewers": p1}],
        "forecast": [{"hour": h} for h in range(2, 25)],
        "comparables": comparables,
    }


def main_eval():
    case0 = json.load(open(KIT / "input" / "p00.in"))
    comps = case0["comparables"]
    curves = {}
    for c in comps:
        cur = main.release_day_curve(c)
        if cur:
            curves[c["name"]] = (cur, c)
    names = sorted(curves)
    console_clean = [n for n in names
                     if main.is_console_only(curves[n][1]) and not main.is_contaminated(curves[n][1])]

    def loo(targets, label):
        mine, flat = [], []
        per = []
        for t in targets:
            cur, _ = curves[t]
            others = [curves[n][1] for n in names if n != t]
            fc = main.forecast_case(make_case(cur[0], others), t)
            mine.append(score(cur, fc["hours"]))
            flat.append(score(cur, flat_rows(cur[0])))
            per.append((t, cur[0], mine[-1], flat[-1]))
        print(f"{label}: n={len(targets)}")
        print(f"  shipped model : mean={statistics.mean(mine):.4f} median={statistics.median(mine):.4f}")
        print(f"  flat baseline : mean={statistics.mean(flat):.4f} median={statistics.median(flat):.4f}")
        print(f"  improvement   : {(1 - statistics.mean(mine) / statistics.mean(flat)) * 100:.1f}% mean, "
              f"{(1 - statistics.median(mine) / statistics.median(flat)) * 100:.1f}% median")
        return per

    print("=== LOO, console-only clean targets (GTA VI's stratum) ===")
    per = loo(console_clean, "console-clean")
    for t, p1, m, f in per:
        print(f"  {t:45s} p1={p1:>8,}  model={m:.4f}  flat={f:.4f}")

    print("\n=== LOO, all 37 comparable targets (context: includes PC-unlock curves) ===")
    loo(names, "all")

    print("\n=== practice-case forecasts (cannot score: answers are server-side) ===")
    for cid in ["p00", "p01", "p02", "p03"]:
        case = json.load(open(KIT / "input" / f"{cid}.in"))
        fc = main.forecast_case(case, cid)
        p1 = case["known"][0]["viewers"]
        meds = {r["hour"]: r["q"][2] for r in fc["hours"]}
        print(f"  {cid} {case['game']['name']}: p1={p1:,}  "
              f"median h2={meds[2]:,.0f} h6={meds[6]:,.0f} h12={meds[12]:,.0f} "
              f"h19={meds[19]:,.0f} h24={meds[24]:,.0f}")


if __name__ == "__main__":
    main_eval()
