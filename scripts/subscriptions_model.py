import json
import argparse
from dataclasses import dataclass
from typing import Dict

@dataclass
class InterestInputs:
    fiat_balance: float
    fiat_rate: float
    fiat_share: float
    usdc_balance: float
    usdc_rate: float
    usdc_share: float

@dataclass
class StakingInputs:
    eth_staked_units: float
    eth_price: float
    reward_apr: float
    take_rate: float

@dataclass
class CustodyInputs:
    auc: float
    fee_bps: float

@dataclass
class QuarterConfig:
    quarter: str
    reference_total: float
    interest: InterestInputs
    staking: StakingInputs
    custody: CustodyInputs
    other: float

def load_config(path: str) -> QuarterConfig:
    with open(path, "r") as f:
        cfg = json.load(f)
    return QuarterConfig(
        quarter=cfg["quarter"],
        reference_total=float(cfg.get("reference_total", 0)),
        interest=InterestInputs(**cfg["interest"]),
        staking=StakingInputs(**cfg["staking"]),
        custody=CustodyInputs(**cfg["custody"]),
        other=float(cfg.get("other", 0))
    )

def calc_interest(iii: InterestInputs) -> float:
    # Interest = (FiatBal * FedRate * FiatShare) + (USDCBal * USDCYield * USDCShare)
    fiat = iii.fiat_balance * iii.fiat_rate * iii.fiat_share
    usdc = iii.usdc_balance * iii.usdc_rate * iii.usdc_share
    return fiat + usdc

def calc_staking(sss: StakingInputs) -> float:
    # Annual rewards on notional, then quarterly slice, times Coinbase take
    staked_notional = sss.eth_staked_units * sss.eth_price
    annual_rewards = staked_notional * sss.reward_apr
    quarterly_rewards = annual_rewards / 4.0
    return quarterly_rewards * sss.take_rate

def calc_custody(ccc: CustodyInputs) -> float:
    return ccc.auc * ccc.fee_bps

def run_model(cfg: QuarterConfig) -> Dict[str, float]:
    interest = calc_interest(cfg.interest)
    staking = calc_staking(cfg.staking)
    custody = calc_custody(cfg.custody)
    other = cfg.other
    total = interest + staking + custody + other
    err = total - cfg.reference_total if cfg.reference_total else None
    err_pct = (err / cfg.reference_total * 100.0) if cfg.reference_total else None
    return {
        "quarter": cfg.quarter,
        "interest": interest,
        "staking": staking,
        "custody": custody,
        "other": other,
        "total": total,
        "reference_total": cfg.reference_total,
        "error_abs": err if err is not None else float("nan"),
        "error_pct": err_pct if err_pct is not None else float("nan"),
    }

def main():
    ap = argparse.ArgumentParser(description="Subscriptions & Services component model")
    ap.add_argument("--config", required=True, help="Path to configs/qX_YYYY.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    res = run_model(cfg)

    print(f"== {res['quarter']} S&S Model ==")
    print(f"Interest: ${res['interest']:,.0f}")
    print(f"Staking : ${res['staking']:,.0f}")
    print(f"Custody : ${res['custody']:,.0f}")
    print(f"Other   : ${res['other']:,.0f}")
    print("-" * 36)
    print(f"Total   : ${res['total']:,.0f}")
    if res['reference_total'] > 0:
        print(f"Reference: ${res['reference_total']:,.0f}")
        print(f"Error: ${res['error_abs']:,.0f} ({res['error_pct']:.3f}%)")

if __name__ == "__main__":
    main()
