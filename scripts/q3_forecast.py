import pandas as pd
import json
import argparse
from subscriptions_model import load_config, run_model

def load_sentiment_factors():
    """Load the sentiment factors for Aug/Sep from the generated CSV."""
    try:
        df = pd.read_csv("data/coinbase_sentiment_monthly.csv")
        factors = {}
        for _, row in df.iterrows():
            month = row['month']
            if month == '2025-08':
                factors['aug'] = row['sentiment_factor']
            elif month == '2025-09':
                factors['sep'] = row['sentiment_factor']
        return factors['aug'], factors['sep']
    except:
        # Fallback if sentiment file doesn't exist
        print("Warning: Could not load sentiment factors. Using default values.")
        return 1.018, 1.015

def calculate_transaction_revenue(aug_notional_b=72, sep_notional_b=80, take_rate=0.0025):
    """
    Calculate quarterly transaction revenue for Q3 2025.
    
    Args:
        aug_notional_b: August Coinbase transaction notional in billions
        sep_notional_b: September Coinbase transaction notional in billions  
        take_rate: Blended take rate (e.g., 0.0025 = 25 bps)
    
    Returns:
        Dictionary with monthly and total transaction revenue
    """
    # Load sentiment factors for Aug/Sep
    aug_sentiment, sep_sentiment = load_sentiment_factors()
    
    # Management guidance: July transaction revenue (no sentiment)
    july_rev = 360_000_000
    
    # Aug/Sep: Apply sentiment factors (±5% bound)
    aug_rev = aug_notional_b * 1_000_000_000 * take_rate * aug_sentiment
    sep_rev = sep_notional_b * 1_000_000_000 * take_rate * sep_sentiment
    
    total_rev = july_rev + aug_rev + sep_rev
    
    return {
        "july": july_rev,
        "august": aug_rev,
        "september": sep_rev,
        "total": total_rev,
        "aug_sentiment": aug_sentiment,
        "sep_sentiment": sep_sentiment
    }

def forecast_q3():
    """Generate complete Q3 2025 revenue forecast."""
    
    print("="*70)
    print("Q3 2025 COINBASE REVENUE FORECAST")
    print("="*70)
    
    # 1. Load Q3 S&S configuration
    print("\n1. SUBSCRIPTIONS & SERVICES FORECAST")
    print("-" * 45)
    q3_config = load_config("configs/q3_2025.json")
    s_s_results = run_model(q3_config)
    
    print(f"Interest Revenue: ${s_s_results['interest']:,.0f}")
    print(f"Staking Revenue : ${s_s_results['staking']:,.0f}")
    print(f"Custody Revenue : ${s_s_results['custody']:,.0f}")
    print(f"Other Revenue   : ${s_s_results['other']:,.0f}")
    print("-" * 45)
    print(f"S&S Total       : ${s_s_results['total']:,.0f}")
    
    # 2. Calculate transaction revenue with sentiment factors
    print("\n2. TRANSACTION REVENUE FORECAST")
    print("-" * 45)
    trans_rev = calculate_transaction_revenue()
    
    print(f"July Revenue    : ${trans_rev['july']:,.0f} (management guide)")
    print(f"August Revenue : ${trans_rev['august']:,.0f} (sentiment: {trans_rev['aug_sentiment']:.3f})")
    print(f"September Rev.  : ${trans_rev['september']:,.0f} (sentiment: {trans_rev['sep_sentiment']:.3f})")
    print("-" * 45)
    print(f"Transaction Total: ${trans_rev['total']:,.0f}")
    
    # 3. Total revenue forecast
    total_revenue = trans_rev['total'] + s_s_results['total']
    
    print("\n3. TOTAL Q3 2025 REVENUE FORECAST")
    print("="*70)
    print(f"Transaction Revenue: ${trans_rev['total']:,.0f}")
    print(f"S&S Revenue       : ${s_s_results['total']:,.0f}")
    print("-" * 70)
    print(f"TOTAL Q3 REVENUE  : ${total_revenue:,.0f}")
    
    # 4. Scenario analysis
    print("\n4. SCENARIO ANALYSIS")
    print("-" * 45)
    
    # Base case (current assumptions)
    base_total = total_revenue
    
    # Bull case: +10% transaction volume, +2bps take rate
    bull_trans = calculate_transaction_revenue(sep_notional_b=88, take_rate=0.0027)
    bull_total = bull_trans['total'] + s_s_results['total']
    
    # Bear case: -10% transaction volume, -2bps take rate  
    bear_trans = calculate_transaction_revenue(aug_notional_b=65, sep_notional_b=72, take_rate=0.0023)
    bear_total = bear_trans['total'] + s_s_results['total']
    
    print(f"Base Case Revenue: ${base_total:,.0f}")
    print(f"Bull Case Revenue: ${bull_total:,.0f} (+${bull_total-base_total:,.0f})")
    print(f"Bear Case Revenue: ${bear_total:,.0f} (${bear_total-base_total:,.0f})")
    
    print("\n" + "="*70)
    print("FORECAST SUMMARY")
    print("="*70)
    print(f"• July transaction revenue anchored from management: ${trans_rev['july']:,.0f}")
    print(f"• Aug/Sep transaction revenue modulated by sentiment factors (±5% bound)")
    print(f"• Subscriptions & Services modeled from ex-ante drivers") 
    print(f"• Sentiment factors derived from Google Trends + Reddit")
    print(f"• Total Q3 2025 Revenue Forecast: ${total_revenue:,.0f}")
    
    return {
        "total_revenue": total_revenue,
        "transaction_revenue": trans_rev['total'],
        "s_s_revenue": s_s_results['total'],
        "scenarios": {
            "base": base_total,
            "bull": bull_total, 
            "bear": bear_total
        },
        "transactions": trans_rev,
        "s_s": s_s_results
    }

def main():
    parser = argparse.ArgumentParser(description="Generate Q3 2025 Coinbase revenue forecast")
    parser.add_argument("--aug-notional", "-a", type=float, default=72,
                       help="August transaction notional in billions (default: 72)")
    parser.add_argument("--sep-notional", "-s", type=float, default=80,
                       help="September transaction notional in billions (default: 80)")
    parser.add_argument("--take-rate", "-t", type=float, default=0.0025,
                       help="Blended take rate (default: 0.0025)")
    args = parser.parse_args()
    
    # Override defaults if provided
    if args.aug_notional != 72 or args.sep_notional != 80 or args.take_rate != 0.0025:
        print(f"Using custom parameters: Aug={args.aug_notional}B, Sep={args.sep_notional}B, Take={args.take_rate}")
        trans_rev = calculate_transaction_revenue(args.aug_notional, args.sep_notional, args.take_rate)
        q3_config = load_config("configs/q3_2025.json")
        s_s_results = run_model(q3_config)
        total_revenue = trans_rev['total'] + s_s_results['total']
        print(f"Custom Scenario Total Revenue: ${total_revenue:,.0f}")
    else:
        forecast_q3()

if __name__ == "__main__":
    main()
