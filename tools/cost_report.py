"""
cost_report.py — summarise REAL fal.ai spend from logs/generation_metadata.jsonl.

The pipeline logs one entry per comic (panel costs aggregated) with the actual
endpoint/model and an estimated_request_cost. This reads that ledger and prints
total spend, per-comic average, success/fail counts, a model breakdown, and the
free-tier runway implied by the current fal.ai balance.

Usage:
    python tools/cost_report.py
    python tools/cost_report.py --balance 6.80      # show runway vs a known balance
    python tools/cost_report.py --recent 10         # also list the last N comics
"""
import os
import sys
import json
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--balance", type=float, default=None, help="current fal.ai balance ($) for runway estimate")
    ap.add_argument("--recent", type=int, default=0, help="list the last N comics")
    args = ap.parse_args()

    logs_dir = getattr(settings, "LOGS_DIR", os.path.join(settings.BASE_DIR, "logs"))
    log_file = os.path.join(logs_dir, "generation_metadata.jsonl")
    if not os.path.exists(log_file):
        print(f"No cost log yet at {log_file} (run a comic first).")
        return 0

    entries = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        print("Cost log is empty.")
        return 0

    total = sum(float(e.get("estimated_request_cost", 0.0) or 0.0) for e in entries)
    n = len(entries)
    success = sum(1 for e in entries if e.get("status") == "success")
    failed = n - success
    by_model = defaultdict(lambda: [0, 0.0])  # model -> [count, cost]
    for e in entries:
        m = e.get("actual_model") or e.get("model") or "unknown"
        by_model[m][0] += 1
        by_model[m][1] += float(e.get("estimated_request_cost", 0.0) or 0.0)

    avg = total / n if n else 0.0
    print("=" * 56)
    print("Inkraft — fal.ai spend report")
    print("=" * 56)
    print(f"Comics logged:        {n}  ({success} success, {failed} failed)")
    print(f"Total estimated spend: ${total:.3f}")
    print(f"Avg per comic:         ${avg:.3f}")
    print("\nBy model/endpoint:")
    for m, (cnt, cost) in sorted(by_model.items(), key=lambda kv: -kv[1][1]):
        print(f"  {m:<36} {cnt:>4} comics  ${cost:.3f}")

    # Per-user spend (user_id logged since 2026-06-28) — see which testers cost most.
    by_user = defaultdict(lambda: [0, 0.0])
    for e in entries:
        uid = e.get("user_id") or "(unknown)"
        by_user[uid][0] += 1
        by_user[uid][1] += float(e.get("estimated_request_cost", 0.0) or 0.0)
    if len(by_user) > 1 or "(unknown)" not in by_user:
        print("\nBy user:")
        for uid, (cnt, cost) in sorted(by_user.items(), key=lambda kv: -kv[1][1])[:15]:
            print(f"  {str(uid)[:38]:<38} {cnt:>4} comics  ${cost:.3f}")

    # Tiered pricing: worst-case $/credit is the priciest tier (most panels per credit).
    free_credits = getattr(settings, "NEW_USER_CREDITS", 5)
    tiers = getattr(settings, "CREDIT_PANEL_TIERS", [(2, 1), (4, 2), (6, 3)])
    panel_cost = 0.039
    worst_cost_per_credit = max((mp * panel_cost) / c for mp, c in tiers) if tiers else panel_cost
    worst_user = free_credits * worst_cost_per_credit
    print(f"\nFree tier: {free_credits} credits/user. Tiered pricing caps worst-case spend at "
          f"~${worst_user:.2f}/user (${worst_cost_per_credit:.3f}/credit).")
    if args.balance is not None and worst_user > 0:
        print(f"Runway @ ${args.balance:.2f}: ~{int(args.balance / worst_user)} fresh free users (worst case); "
              f"~{int(args.balance / avg) if avg else 0} more comics at the observed avg.")

    if args.recent:
        print(f"\nLast {args.recent} comics:")
        for e in entries[-args.recent:]:
            print(f"  {e.get('timestamp','?')[:19]}  {e.get('style','?'):<10} "
                  f"{e.get('status','?'):<8} ${float(e.get('estimated_request_cost',0) or 0):.3f}  "
                  f"{e.get('actual_model','?')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
