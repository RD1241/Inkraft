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

    log_file = os.path.join(settings.BASE_DIR, "logs", "generation_metadata.jsonl")
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

    free_credits = 3  # current new-user grant (credits_service.starting_balance)
    print(f"\nFree-tier exposure: {free_credits} credits/user × ${avg:.3f} avg ≈ ${free_credits * avg:.2f}/user")
    if args.balance is not None and avg > 0:
        print(f"Runway @ ${args.balance:.2f} balance: ~{int(args.balance / avg)} more comics "
              f"(~{int(args.balance / (free_credits * avg))} fresh free users)")

    if args.recent:
        print(f"\nLast {args.recent} comics:")
        for e in entries[-args.recent:]:
            print(f"  {e.get('timestamp','?')[:19]}  {e.get('style','?'):<10} "
                  f"{e.get('status','?'):<8} ${float(e.get('estimated_request_cost',0) or 0):.3f}  "
                  f"{e.get('actual_model','?')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
