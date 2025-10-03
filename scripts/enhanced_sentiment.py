"""
Enhanced sentiment analysis module using multiple data sources:
- Google Trends (via pytrends)
- Reddit data (via Pushshift API)
- Gemini AI for enhanced sentiment analysis
- Fallback to mock data when APIs are unavailable
"""

import pandas as pd
import numpy as np
import requests
import time
import json
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Optional imports - will be available if packages are installed
try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

class EnhancedSentimentAnalyzer:
    def __init__(self, config_path="configs/sentiment_config.json"):
        """Initialize the sentiment analyzer with configuration."""
        self.config = self._load_config(config_path)
        self.vader_analyzer = SentimentIntensityAnalyzer()
        
        # Initialize Gemini if available and enabled
        if GEMINI_AVAILABLE and self.config.get("apis", {}).get("gemini", {}).get("enabled", False):
            try:
                api_key = self.config["apis"]["gemini"]["api_key"]
                if api_key != "your_gemini_api_key_here":
                    genai.configure(api_key=api_key)
                    self.gemini_model = genai.GenerativeModel('gemini-pro')
                    self.gemini_enabled = True
                else:
                    self.gemini_enabled = False
            except:
                self.gemini_enabled = False
        else:
            self.gemini_enabled = False
    
    def _load_config(self, path):
        """Load configuration from JSON file."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            return {
                "use_real_data": True,
                "fallback_to_mock": True,
                "apis": {
                    "gemini": {"enabled": False},
                    "pytrends": {"enabled": True},
                    "reddit": {"enabled": True}
                }
            }
    
    def fetch_google_trends(self, keywords, start_date, end_date):
        """Fetch Google Trends data."""
        if not PYTRENDS_AVAILABLE:
            print("Warning: pytrends not available, skipping Google Trends")
            return None
            
        try:
            pytrends = TrendReq(hl="en-US", tz=0)
            timeframe = f"{start_date} {end_date}"
            frames = []
            
            for kw in keywords:
                try:
                    pytrends.build_payload([kw], cat=0, timeout=timeframe, geo='', gprop='')
                    df = pytrends.interest_over_time().reset_index()
                    if "isPartial" in df.columns:
                        df = df.drop(columns=["isPartial"])
                    df = df.rename(columns={kw: "value"})
                    df["keyword"] = kw
                    frames.append(df)
                except Exception as e:
                    print(f"Failed to fetch trends for '{kw}': {e}")
                    continue
                
                time.sleep(1)  # Rate limiting
            
            if frames:
                trends = pd.concat(frames, ignore_index=True)
                return trends.groupby("date", as_index=False)["value"].mean().rename(columns={"value": "trends_value"})
            else:
                return None
                
        except Exception as e:
            print(f"Google Trends fetch failed: {e}")
            return None
    
    def fetch_reddit_data(self, query, start_date, end_date):
        """Fetch Reddit submission data."""
        PS_URL = "https://api.pushshift.io/reddit/search/submission/"
        days = pd.date_range(start_date, end_date, freq="D")
        records = []
        
        for day in days:
            t0 = int(pd.Timestamp(day).timestamp())
            t1 = int((pd.Timestamp(day) + pd.Timedelta(days=1)).timestamp())
            params = {
                "q": query,
                "after": t0,
                "before": t1,
                "size": 250,
                "fields": ["title", "selftext"],
                "sort": "desc"
            }
            
            all_scores, count = [], 0
            try:
                resp = requests.get(PS_URL, params=params, timeout=20)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for post in data[:50]:  # Limit for Gemini efficiency
                        text = (post.get("title", "") + " " + post.get("selftext", "")).strip()
                        if text:
                            vs = self.vader_analyzer.polarity_scores(text)["compound"]
                            all_scores.append(vs)
                            count += 1
            except:
                pass
            
            avg_sentiment = np.mean(all_scores) if all_scores else 0.0
            records.append({
                "date": day,
                "reddit_volume": count,
                "reddit_sentiment_raw": avg_sentiment,
                "reddit_posts": all_scores[:10]  # Keep sample for Gemini
            })
            time.sleep(0.3)  # Rate limiting
        
        return pd.DataFrame(records)
    
    def analyze_with_gemini(self, reddit_posts, trends_data=None):
        """Enhanced sentiment analysis using Gemini AI."""
        if not self.gemini_enabled:
            return None
        
        # Prepare context for Gemini
        sample_posts = []
        for day_data in reddit_posts:
            sample_posts.extend([score for score in day_data["reddit_posts"][:2]])
        
        context = {
            "reddit_sentiment_samples": sample_posts[:5],
            "coinbase_trends_avg": np.mean(trends_data) if trends_data is not None else "N/A"
        }
        
        prompt = f"""
        Analyze sentiment for Coinbase cryptocurrency exchange based on this data:
        Reddit sentiment samples (VADER compound scores): {sample_posts[:5]}
        Trending indicator: {'Strong' if (trends_data is not None and np.mean(trends_data) > 60) else 'Moderate' if trends_data is not None else 'Unknown'}
        
        Consider market sentiment, regulatory environment, and crypto adoption trends.
        
        Return a comprehensive sentiment score from 0-10 where:
        - 0-3: Very negative sentiment
        - 4-6: Neutral sentiment  
        - 7-10: Positive sentiment
        
        Also provide a brief reason for the score.
        Format your response as: "SCORE: X.XXX | REASON: Your analysis here"
        """
        
        try:
            response = self.gemini_model.generate_content(prompt)
            result = response.text.strip()
            # Extract score
            if "SCORE:" in result:
                score_part = result.split("SCORE:")[1].split("|")[0].strip()
                return float(score_part)
            return None
        except Exception as e:
            print(f"Gemini analysis failed: {e}")
            return None
    
    def build_composite_factor(self, trends_df, reddit_df):
        """Build composite sentiment factor."""
        # Merge dataframes
        df = pd.merge(trends_df, reddit_df, on="date", how="outer").sort_values("date").set_index("date").asfreq("D")
        
        # Calculate features
        if len(df) > 28:
            baseline = df["trends_value"].iloc[:28].mean()
        else:
            baseline = df["trends_value"].mean()
        
        df["trends_level"] = df["trends_value"] / (baseline if baseline else 1.0)
        df["ma_28"] = df["trends_value"].rolling(28, min_periods=7).mean()
        df["trends_momentum"] = (df["trends_value"] / df["ma_28"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
        df["vol_ma14"] = df["reddit_volume"].rolling(14, min_periods=7).mean()
        df["reddit_volume_mom"] = (df["reddit_volume"] / df["vol_ma14"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
        df["reddit_sentiment"] = 1 + (df["reddit_sentiment_raw"] * 0.25)
        
        # Gemini-enhanced analysis
        gemini_score = self.analyze_with_gemini(reddit_df)
        if gemini_score is not None:
            # Convert Gemini score (0-10) to sentiment factor (0.9-1.1)
            gemini_factor = 0.9 + (gemini_score / 10) * 0.2
            print(f"Gemini enhanced score: {gemini_score:.2f} -> Factor: {gemini_factor:.4f}")
        else:
            gemini_factor = 1.0
        
        # Weighted composite z-scores
        weights = {
            "trends_level": 0.25,
            "trends_momentum": 0.15,
            "reddit_volume_mom": 0.20,
            "reddit_sentiment": 0.15,
            "gemini_boost": 0.25
        }
        
        def zscore(s):
            mu, sd = s.mean(), s.std(ddof=0)
            if sd == 0 or np.isnan(sd):
                return pd.Series(0.0, index=s.index)
            return (s - mu) / sd
        
        # Calculate weighted composite
        composite = (
            weights["trends_level"] * zscore(df["trends_level"]) +
            weights["trends_momentum"] * zscore(df["trends_momentum"]) +
            weights["reddit_volume_mom"] * zscore(df["reddit_volume_mom"]) +
            weights["reddit_sentiment"] * zscore(df["reddit_sentiment"]) +
            weights["gemini_boost"] * zscore(pd.Series([gemini_factor] * len(df)))
        )
        
        # Apply scaling and clipping
        factor = 1.0 + (composite * 0.015) * gemini_factor
        factor = np.clip(factor, 0.95, 1.05)
        
        return pd.DataFrame({
            "date": df.index,
            "sentiment_factor": factor.round(4),
            "trends_level": df["trends_level"].round(3),
            "trends_momentum": df["trends_momentum"].round(3),
            "reddit_volume_mom": df["reddit_volume_mom"].round(3),
            "reddit_sentiment": df["reddit_sentiment"].round(3),
            "gemini_enhanced": gemini_score
        })
    
    def generate_forecast(self, start_date, end_date, keywords=["coinbase", "coinbase app", "coinbase login"], reddit_query="coinbase"):
        """Generate sentiment forecast with real data when possible."""
        print(f"Building enhanced sentiment factor from {start_date} to {end_date}")
        
        # Try to fetch real data
        trends_df = self.fetch_google_trends(keywords, start_date, end_date)
        reddit_df = self.fetch_reddit_data(reddit_query, start_date, end_date)
        
        # Use real data if available
        if trends_df is not None and not reddit_df.empty and self.config.get("use_real_data", True):
            print("Successfully fetched real data, building enhanced factor...")
            return self.build_composite_factor(trends_df, reddit_df)
        
        # Fallback to mock data
        print("Using mock data for demonstration...")
        return self._generate_mock_data(start_date, end_date)
    
    def _generate_mock_data(self, start_date, end_date):
        """Generate realistic mock sentiment data."""
        dates = pd.date_range(start_date, end_date, freq="D")
        
        # Create trend that improves over the quarter
        base_trend = np.linspace(0.97, 1.03, len(dates))
        noise = np.random.normal(0, 0.015, len(dates))
        sentiment_factor = np.clip(base_trend + noise, 0.95, 1.05)
        
        return pd.DataFrame({
            "date": dates,
            "sentiment_factor": sentiment_factor.round(4),
            "trends_level": np.random.uniform(0.8, 1.3, len(dates)).round(3),
            "trends_momentum": np.random.uniform(0.7, 1.4, len(dates)).round(3),
            "reddit_volume_mom": np.random.uniform(0.6, 1.6, len(dates)).round(3),
            "reddit_sentiment": np.random.uniform(0.9, 1.1, len(dates)).round(3),
            "gemini_enhanced": None
        })

if __name__ == "__main__":
    analyzer = EnhancedSentimentAnalyzer()
    result = analyzer.generate_forecast("2025-07-01", "2025-09-30")
    print("\nGenerated sentiment data:")
    print(result.head())
    
    # Save results
    result.to_csv("data/coinbase_sentiment_daily.csv", index=False)
    
    # Create monthly aggregates
    result["month"] = pd.to_datetime(result["date"]).dt.to_period("M").astype(str)
    monthly = result.groupby("month", as_index=False)["sentiment_factor"].mean()
    monthly.to_csv("data/coinbase_sentiment_monthly.csv", index=False)
    print("Saved daily and monthly sentiment data!")
