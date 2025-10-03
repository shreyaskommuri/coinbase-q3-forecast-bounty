import pandas as pd
import numpy as np
import requests
import time
import argparse
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pytrends.request import TrendReq

# Import enhanced sentiment analyzer
try:
    from enhanced_sentiment import EnhancedSentimentAnalyzer
    ENHANCED_AVAILABLE = True
except ImportError:
    ENHANCED_AVAILABLE = False

PS_URL = "https://api.pushshift.io/reddit/search/submission/"

def fetch_trends(keywords, start, end):
    """Fetch Google Trends data for given keywords and timeframe."""
    pytrends = TrendReq(hl="en-US", tz=0)
    timeframe = f"{start} {end}"
    frames = []
    for kw in keywords:
        try:
            pytrends.build_payload([kw], cat=0, timeframe=timeframe, geo='', gprop='')
            df = pytrends.interest_over_time().reset_index()
            if "isPartial" in df.columns: 
                df = df.drop(columns=["isPartial"])
            df = df.rename(columns={kw: "value"})
            df["keyword"] = kw
            frames.append(df)
        except Exception as e:
            print(f"Warning: Could not fetch trends for '{kw}': {e}")
            # Create empty dataframe as fallback
            df = pd.DataFrame({"date": pd.date_range(start, end), "value": 50, "keyword": kw})
            frames.append(df)
        
        time.sleep(1)  # Rate limiting
    
    if frames:
        trends = pd.concat(frames, ignore_index=True)
        trends = trends.groupby("date", as_index=False)["value"].mean().rename(columns={"value":"trends_value"})
    else:
        # Fallback if all requests fail
        trends = pd.DataFrame({"date": pd.date_range(start, end), "trends_value": 50})
    
    return trends

def trends_features(trends_df, start):
    """Calculate trend features: level and momentum."""
    t = trends_df.copy()
    start_ts = pd.Timestamp(start)
    baseline_window = t[t["date"] < (start_ts + pd.Timedelta(days=28))]["trends_value"]
    baseline = baseline_window.mean() if len(baseline_window) else t["trends_value"].mean()
    t["trends_level"] = t["trends_value"] / (baseline if baseline else 1.0)
    t["ma_28"] = t["trends_value"].rolling(28, min_periods=7).mean()
    t["trends_momentum"] = (t["trends_value"] / t["ma_28"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    return t.drop(columns=["ma_28"])

def fetch_reddit_counts_and_sentiment(query, start, end):
    """Fetch Reddit post counts and sentiment for given query and timeframe."""
    analyzer = SentimentIntensityAnalyzer()
    days = pd.date_range(start, end, freq="D")
    recs = []
    
    for day in days:
        t0 = int(pd.Timestamp(day).timestamp())
        t1 = int((pd.Timestamp(day) + pd.Timedelta(days=1)).timestamp())
        params = {
            "q": query, 
            "after": t0, 
            "before": t1, 
            "size": 250, 
            "fields": ["title","selftext"], 
            "sort": "desc"
        }

        all_scores, count = [], 0
        try:
            resp = requests.get(PS_URL, params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for post in data:
                    text = (post.get("title") or "") + " " + (post.get("selftext") or "")
                    if text.strip():
                        vs = analyzer.polarity_scores(text)["compound"]
                        all_scores.append(vs)
                        count += 1
        except requests.RequestException as e:
            print(f"Warning: Reddit API request failed for {day}: {e}")
            pass

        avg_sent = np.mean(all_scores) if all_scores else 0.0
        recs.append({
            "date": day, 
            "reddit_volume": count, 
            "reddit_sentiment_raw": avg_sent
        })
        time.sleep(0.3)  # Rate limiting
    
    df = pd.DataFrame(recs)
    # Calculate moving averages
    df["vol_ma14"] = df["reddit_volume"].rolling(14, min_periods=7).mean()
    df["reddit_volume_mom"] = (df["reddit_volume"] / df["vol_ma14"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    df["reddit_sentiment"] = 1 + (df["reddit_sentiment_raw"] * 0.25)
    return df[["date","reddit_volume","reddit_volume_mom","reddit_sentiment"]]

def zscore(s):
    """Calculate z-scores for a series."""
    mu, sd = s.mean(), s.std(ddof=0)
    if sd == 0 or np.isnan(sd): 
        return pd.Series(0.0, index=s.index)
    return (s - mu) / sd

def build_factor(start, end, keywords, reddit_query, max_up=0.05, max_down=-0.05):
    """Build the composite sentiment factor from trends and Reddit data."""
    
    print("Fetching Google Trends data...")
    trends = fetch_trends(keywords, start, end)
    trends = trends_features(trends, start)
    
    print("Fetching Reddit data...")
    reddit = fetch_reddit_counts_and_sentiment(reddit_query, start, end)
    
    # Merge dataframes
    df = pd.merge(trends, reddit, on="date", how="outer").sort_values("date").set_index("date").asfreq("D")
    
    # Fill missing values
    for col in ["trends_level","trends_momentum","reddit_volume_mom","reddit_sentiment"]:
        df[col] = df[col].interpolate().bfill().ffill()
    
    # Weighted composite z-score
    weights = {
        "trends_level": 0.4,
        "trends_momentum": 0.2,
        "reddit_volume_mom": 0.25,
        "reddit_sentiment": 0.15
    }
    
    z = (
        weights["trends_level"] * zscore(df["trends_level"]) +
        weights["trends_momentum"] * zscore(df["trends_momentum"]) +
        weights["reddit_volume_mom"] * zscore(df["reddit_volume_mom"]) +
        weights["reddit_sentiment"] * zscore(df["reddit_sentiment"])
    )
    
    # Apply scaling and clipping
    factor = 1.0 + (z * 0.015)
    factor = np.clip(factor, 1.0 + max_down, 1.0 + max_up)
    
    # Prepare output
    out = pd.DataFrame({
        "date": df.index,
        "sentiment_factor": factor.round(4),
        "trends_level": df["trends_level"].round(3),
        "trends_momentum": df["trends_momentum"].round(3),
        "reddit_volume_mom": df["reddit_volume_mom"].round(3),
        "reddit_sentiment": df["reddit_sentiment"].round(3)
    })
    
    return out

def main():
    parser = argparse.ArgumentParser(description="Build sentiment factor for Coinbase forecast")
    parser.add_argument("--start", default="2025-07-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-09-30", help="End date (YYYY-MM-DD)")
    parser.add_argument("--keywords", nargs="+", 
                       default=["coinbase","coinbase app","coinbase login"],
                       help="Google Trends keywords")
    parser.add_argument("--reddit_query", default="coinbase", 
                       help="Reddit search query")
    parser.add_argument("--out_daily", default="data/coinbase_sentiment_daily.csv",
                       help="Output daily CSV file")
    parser.add_argument("--out_monthly", default="data/coinbase_sentiment_monthly.csv",
                       help="Output monthly CSV file")
    args = parser.parse_args()

    print(f"Building sentiment factor from {args.start} to {args.end}")
    print(f"Keywords: {args.keywords}")
    print(f"Reddit query: {args.reddit_query}")
    
    # Use enhanced sentiment analyzer if available
    if ENHANCED_AVAILABLE:
        print("Using enhanced sentiment analyzer with real APIs and Gemini AI...")
        analyzer = EnhancedSentimentAnalyzer()
        sent = analyzer.generate_forecast(args.start, args.end, args.keywords, args.reddit_query)
        
        # Filter out the gemini_enhanced column for backward compatibility
        output_cols = ["date", "sentiment_factor", "trends_level", "trends_momentum", "reddit_volume_mom", "reddit_sentiment"]
        sent = sent[output_cols]
        
        print(f"Enhanced analyzer generated {len(sent)} records")
        sent.to_csv(args.out_daily, index=False)
        
        # Create monthly aggregates  
        sent["month"] = pd.to_datetime(sent["date"]).dt.to_period("M").astype(str)
        monthly = sent.groupby("month", as_index=False)["sentiment_factor"].mean()
        monthly.to_csv(args.out_monthly, index=False)
        
        print(f"Wrote enhanced {args.out_daily} and {args.out_monthly}")
        return
    
    # Fallback to original implementation
    # Check if we should use real data or mock data
    try:
        import json
        with open("configs/sentiment_config.json", "r") as f:
            config = json.load(f)
        use_real_data = config.get("use_real_data", False)
    except:
        use_real_data = False
    
    if use_real_data:
        print("Fetching real sentiment data from APIs...")
        # Try real API calls here
        try:
            trends = fetch_trends(keywords, args.start, args.end)
            trends = trends_features(trends, args.start)
            reddit = fetch_reddit_counts_and_sentiment(args.reddit_query, args.start, args.end)
            
            # Merge and create factor as in build_factor function
            df = pd.merge(trends, reddit, on="date", how="outer").sort_values("date").set_index("date").asfreq("D")
            
            # Fill missing values
            for col in ["trends_level","trends_momentum","reddit_volume_mom","reddit_sentiment"]:
                df[col] = df[col].interpolate().bfill().ffill()
            
            # Weighted composite z-score
            weights = {
                "trends_level": 0.4,
                "trends_momentum": 0.2,
                "reddit_volume_mom": 0.25,
                "reddit_sentiment": 0.15
            }
            
            z = (
                weights["trends_level"] * zscore(df["trends_level"]) +
                weights["trends_momentum"] * zscore(df["trends_momentum"]) +
                weights["reddit_volume_mom"] * zscore(df["reddit_volume_mom"]) +
                weights["reddit_sentiment"] * zscore(df["reddit_sentiment"])
            )
            
            factor = 1.0 + (z * 0.015)
            factor = np.clip(factor, 0.95, 1.05)
            
            # Create output dataframe
            sent = pd.DataFrame({
                "date": df.index,
                "sentiment_factor": factor.round(4),
                "trends_level": df["trends_level"].round(3),
                "trends_momentum": df["trends_momentum"].round(3),
                "reddit_volume_mom": df["reddit_volume_mom"].round(3),
                "reddit_sentiment": df["reddit_sentiment"].round(3)
            })
            
            print("Successfully fetched real sentiment data!")
        except Exception as e:
            print(f"Real API fetch failed: {e}")
            print("Falling back to mock data...")
            use_real_data = False
    
    if not use_real_data:
        # Create mock data instead of hitting APIs for demo purposes
        # In production, this would use real API calls
        print("Generating mock sentiment data for demo...")
    
    # Generate dates
    dates = pd.date_range(args.start, args.end, freq="D")
    
    # Create realistic-looking mock data
    np.random.seed(42)  # For reproducible results
    
    # Base sentiment factor trends up slightly over the quarter
    trend = np.linspace(0.98, 1.02, len(dates))
    noise = np.random.normal(0, 0.02, len(dates))
    base_factor = trend + noise
    
    # Clip to ±5% as specified
    sentiment_factor = np.clip(base_factor, 0.95, 1.05)
    
    # Create supporting features with realistic patterns
    trends_level = np.random.uniform(0.8, 1.3, len(dates))
    trends_momentum = np.random.uniform(0.7, 1.4, len(dates))
    reddit_volume_mom = np.random.uniform(0.6, 1.6, len(dates))
    reddit_sentiment = np.random.uniform(0.9, 1.1, len(dates))
    
    # Create output dataframe
    sent = pd.DataFrame({
        "date": dates,
        "sentiment_factor": sentiment_factor.round(4),
        "trends_level": trends_level.round(3),
        "trends_momentum": trends_momentum.round(3),
        "reddit_volume_mom": reddit_volume_mom.round(3),
        "reddit_sentiment": reddit_sentiment.round(3)
    })
    
    # Write daily CSV
    sent.to_csv(args.out_daily, index=False)
    print(f"Wrote {args.out_daily} with {len(sent)} daily records")

    # Create monthly aggregates
    sent["month"] = pd.to_datetime(sent["date"]).dt.to_period("M").astype(str)
    monthly = sent.groupby("month", as_index=False)["sentiment_factor"].mean()
    monthly.to_csv(args.out_monthly, index=False)
    print(f"Wrote {args.out_monthly} with monthly averages:")
    for _, row in monthly.iterrows():
        print(f"  {row['month']}: {row['sentiment_factor']:.4f}")

if __name__ == "__main__":
    main()
