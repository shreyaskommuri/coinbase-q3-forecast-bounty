import argparse
import sys
import os

# Add the scripts directory to the path so we can import subscriptions_model
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from subscriptions_model import load_config, run_model

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q1", default="configs/q1_2025.json")
    ap.add_argument("--q2", default="configs/q2_2025.json")
    args = ap.parse_args()

    for path in [args.q1, args.q2]:
        cfg = load_config(path)
        res = run_model(cfg)
        print("="*64)
        print(f"{res['quarter']}:")
        print(f"Interest ${res['interest']:,.0f} | Staking ${res['staking']:,.0f} | Custody ${res['custody']:,.0f} | Other ${res['other']:,.0f}")
        print(f"Total   ${res['total']:,.0f}  vs  Reference ${res['reference_total']:,.0f}")
        print(f"Error   ${res['error_abs']:,.0f}  ({res['error_pct']:.3f}%)")

if __name__ == "__main__":
    main()
