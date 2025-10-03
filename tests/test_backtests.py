import sys
import os

# Add the scripts directory to the path so we can import subscriptions_model
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

# Change to the project root directory for file paths
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from subscriptions_model import load_config, run_model

def _abs_pct(x): 
    """Helper function to get absolute percentage."""
    return abs(x)

def test_q1_accuracy():
    """Test that Q1 2025 backtest achieves ≤0.05% error."""
    cfg = load_config("configs/q1_2025.json")
    res = run_model(cfg)
    assert _abs_pct(res["error_pct"]) <= 0.05, f"Q1 error too high: {res['error_pct']:.6f}%"

def test_q2_accuracy():
    """Test that Q2 2025 backtest achieves ≤0.05% error."""
    cfg = load_config("configs/q2_2025.json")
    res = run_model(cfg)
    assert _abs_pct(res["error_pct"]) <= 0.05, f"Q2 error too high: {res['error_pct']:.6f}%"

def test_model_components():
    """Test that all model components produce reasonable values."""
    cfg = load_config("configs/q1_2025.json")
    res = run_model(cfg)
    
    # Test that all components are positive (except 'other' which can be negative)
    assert res["interest"] > 0, "Interest should be positive"
    assert res["staking"] > 0, "Staking should be positive"
    assert res["custody"] > 0, "Custody should be positive"
    assert res["total"] > 0, "Total should be positive"
    
    # Test reasonable magnitudes (not too small or too large)
    assert 100_000_000 < res["interest"] < 500_000_000, f"Interest magnitude seems unreasonable: {res['interest']}"
    assert 50_000_000 < res["staking"] < 200_000_000, f"Staking magnitude seems unreasonable: {res['staking']}"
    assert 10_000_000 < res["custody"] < 50_000_000, f"Custody magnitude seems unreasonable: {res['custody']}"

def test_config_loading():
    """Test that config files load properly."""
    cfg1 = load_config("configs/q1_2025.json")
    cfg2 = load_config("configs/q2_2025.json")
    
    assert cfg1.quarter == "Q1 2025"
    assert cfg2.quarter == "Q2 2025"
    assert cfg1.reference_total > 0
    assert cfg2.reference_total > 0
    
    # Test that all required fields are present
    assert hasattr(cfg1.interest, 'fiat_balance')
    assert hasattr(cfg1.staking, 'eth_staked_units')
    assert hasattr(cfg1.custody, 'auc')

def test_calculation_consistency():
    """Test that calculations are mathematically consistent."""
    cfg = load_config("configs/q1_2025.json")
    
    # Test interest calculation manually
    expected_interest = (
        cfg.interest.fiat_balance * cfg.interest.fiat_rate * cfg.interest.fiat_share +
        cfg.interest.usdc_balance * cfg.interest.usdc_rate * cfg.interest.usdc_share
    )
    res = run_model(cfg)
    
    # Allow for small floating point differences
    assert abs(res["interest"] - expected_interest) < 1e-6, "Interest calculation doesn't match expected"
    
    # Test staking calculation manually  
    staked_notional = cfg.staking.eth_staked_units * cfg.staking.eth_price
    annual_rewards = staked_notional * cfg.staking.reward_apr
    quarterly_rewards = annual_rewards / 4.0
    expected_staking = quarterly_rewards * cfg.staking.take_rate
    
    assert abs(res["staking"] - expected_staking) < 1e-6, "Staking calculation doesn't match expected"
    
    # Test custody calculation manually
    expected_custody = cfg.custody.auc * cfg.custody.fee_bps
    assert abs(res["custody"] - expected_custody) < 1e-6, "Custody calculation doesn't match expected"
