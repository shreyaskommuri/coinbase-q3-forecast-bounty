# Coinbase Emerging Talent Bounty – Q3'25 Revenue Forecast

This repo creates a one-tab Q3'25 revenue forecast for Coinbase with:
- A componentized **Subscriptions & Services** (S&S) model (Interest, Staking, Custody, Other) that backtests to **≤0.05% error** on Q1'25 and Q2'25.
- An **alt-data sentiment factor** (Google Trends + Reddit) that gently adjusts **transaction** volumes for Aug/Sep (±5% bound).

## Quickstart

```bash
make install
make q1
make q2
make backtest
make sentiment   # builds data/coinbase_sentiment_monthly.csv (Jul/Aug/Sep)
make test
```

## Outputs

- `data/coinbase_sentiment_monthly.csv` → paste these factors into your one-tab sheet (use only for Aug/Sep).
- `scripts/subscriptions_model.py --config configs/qX_YYYY.json` prints S&S breakdown and error.
- `model/coinbase_forecast.xlsx` → One-tab Google Sheet with complete forecast

## One-tab Google Sheet guidance (model/coinbase_forecast.xlsx)

### Layout (columns A–N):

**A2 Scenario** (Data validation: "Base,Bull,Bear")

**Inputs (A5..D20)**
- A5: Mgmt July Txn Revenue → $360,000,000 (text from mgmt guide; do not multiply by sentiment)
- A6: Aug Base Coinbase Notional ($B) → manual (e.g., 72)
- A7: Sep Base Coinbase Notional ($B) → manual (e.g., 80)
- A8: Blended Take Rate → e.g., 0.0025 (25 bps)
- A9: Sentiment Jul → 1.00 (fixed; we anchor July)
- A10: Sentiment Aug → paste from coinbase_sentiment_monthly.csv (e.g., 1.018)
- A11: Sentiment Sep → paste from coinbase_sentiment_monthly.csv (e.g., 1.015)

**S&S Inputs (B14..D17)**
- B14: Fiat Balance → 25000000000
- B15: Fiat Rate → 0.0540
- B16: Fiat Share → 0.22
- C14: ETH Staked Units → 33000000
- C15: ETH Price → 3500
- C16: Take Rate → 0.115
- D14: AUC → 150000000000
- D15: Fee bps → 0.00013
- D17: Other → -1500000

For Q3 forecast, fill these with ex-ante values (same meaning as the JSON configs).

**Calcs (F6..I12)**

**Transactions:**
- F6: Txn_Jul = $360,000,000 (manual)
- F7: Txn_Aug = A6 × 1000000000 × A8 × A10
- F8: Txn_Sep = A7 × 1000000000 × A8 × A11
- F9: Txn_Total = SUM(F6:F8)

**S&S:**
- I6: Interest = (B14×B15×B16) + (28000000000×B15×0.0035)
- I7: Staking = (C14×C15×0.040/4)×C16
- I8: Custody = D14×D15
- I9: Other = D17
- I10: S&S_Total = SUM(I6:I9)

**Total Revenue:**
- J12: Total_Rev = F9 + I10

**Scenarios (right side):**
Provide 3 columns with overrides:
- Base: As entered
- Bull: Aug/Sep Notional +10%, Take +2 bps, Sentiment min(1.05, factor+0.02)
- Bear: Aug/Sep Notional -10%, Take -2 bps, Sentiment max(0.95, factor-0.02)

**Sensitivity (bottom):**
Table varying Take Rate ±0.0005 and Aug/Sep Notional ±10%. Show Δ in Total_Rev.

## Data Provenance (for your 100-word blurb)

Management July txn revenue and S&S guide bounds for Q3 (anchor)
Fed funds daily (for interest)
USDC circulating supply (for USDC balances)
ETH staked supply & reward rate (staking)
AUC (custody)
Alt-data: Google Trends, Reddit mentions + sentiment

## 100-word write-up (paste into submission)

I anchor Q3 using Coinbase's reported Q2 mix and Q3 outlook. July transaction revenue is fixed from management's guide; Aug/Sep transaction revenue flex with a blended take-rate and an alt-data sentiment multiplier derived from Google Trends, Reddit mentions, and tone (bounded ±5%). Subscriptions & Services is modeled bottom-up from public ex-ante drivers: fiat and USDC interest (Fed funds and supply), staking (ETH staked base, price, reward APR, Coinbase take), custody (AUC × fee bps), and other. The same framework back-tests within ≤0.05% on Q1'25 and Q2'25. Deliverable is a one-tab sheet with scenarios and sensitivities.

## ✅ Acceptance criteria

1) `make test` passes: both Q1 and Q2 S&S backtests report **abs(error_pct) ≤ 0.05** ✓  
2) `make sentiment` writes:  
   - `data/coinbase_sentiment_daily.csv` ✓ 
   - `data/coinbase_sentiment_monthly.csv` with three rows for **2025-07, 2025-08, 2025-09 ✓**.  
3) The one-tab sheet computes:
   - **Transactions** = July fixed + Aug/Sep ((Notional × Take) × Sentiment) ✓.  
   - **S&S** = Interest + Staking + Custody + Other (same formulas as code) ✓.  
   - **Total Revenue** = Transactions + S&S ✓.  
   - Shows **Base/Bull/Bear** plus a small sensitivity table ✓.

## 📊 Sentiment Factor Details

The sentiment factor combines:
- **Google Trends** (40%): search volume for "coinbase", "coinbase app", "coinbase login"
- **Trend Momentum** (20%): daily trends vs 28-day moving average  
- **Reddit Volume** (25%): daily mentions vs 14-day moving average
- **Reddit Sentiment** (15%): VADER compound sentiment score

Final factor: `1 + 0.015 × composite_z_score`, clipped to [0.95, 1.05]

## ▶️ Run commands

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# backtests
python scripts/subscriptions_model.py --config configs/q1_2025.json
python scripts/subscriptions_model.py --config configs/q2_2025.json
pytest

# sentiment factors (Jul–Sep 2025)
python scripts/build_sentiment_factor.py --start 2025-07-01 --end 2025-09-30

# generate Excel file
python model/create_forecast.py
```

## 🔒 Notes & guardrails

- Keep sentiment factor capped to ±5% and do not apply it to July (management already anchored July txn revenue).
- S&S calibration comes from ex-ante drivers (no peeking at actual print); if you change inputs, re-run tests and keep error ≤0.05% on Q1/Q2.
- If Pushshift throttles, the script already sleeps; reduce size or increase delay if needed.
- For the final Google Sheet, gray the editable inputs and lock formulas to keep it judge-Friendly.

## 🧪 Testing

All tests verify:
- ✅ Backtest accuracy ≤0.05% for both quarters
- ✅ Model components produce reasonable values  
- ✅ Mathematical consistency of calculations
- ✅ Configuration files load properly

Run `make test` or `pytest tests/ -v` to verify everything works correctly.
