"""
Disease Area Dashboard — live demo
Run: python3 demo/run_demo.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from src.main import DiseaseAreaDashboard

DATA = os.path.join(os.path.dirname(__file__), "../sample_data/pharma_sales.csv")

print("=" * 62)
print("  Disease Area Dashboard — Demo (Cardiovascular Therapy Area)")
print("=" * 62)

dash = DiseaseAreaDashboard(config={"therapy_area": "Cardiovascular", "rolling_months": 3})
df = dash.load_data(DATA)
print(f"\n✓ Loaded {len(df)} prescription records")
print(f"  Brands: {sorted(df['brand'].unique())}")
print(f"  Periods: {df['period'].nunique()} months | Channels: {df['channel'].nunique()}")

# Market share analysis
share = dash.market_share_analysis(df, metric="trx")
latest = share[share["period"] == share["period"].max()]
print(f"\n✓ Market Share Analysis (TRx) — {share['period'].max()}:")
print(f"  {'Brand':<18} {'TRx':>8}  {'Share %':>9}  {'Rank':>5}")
print(f"  {'-'*45}")
for _, row in latest.iterrows():
    print(f"  {row['brand']:<18} {row['trx_value']:>8,.0f}  {row['market_share_pct']:>8.1f}%  #{row['rank']}")

# MAT trend
mat = dash.mat_trend(df, metric="trx")
print(f"\n✓ MAT Trend (Moving Annual Total — last period):")
latest_mat = mat[mat["period"] == mat["period"].max()].sort_values("mat_value", ascending=False)
print(f"  {'Brand':<18} {'MAT TRx':>10}  {'MAT Growth %':>14}")
print(f"  {'-'*48}")
for _, row in latest_mat.iterrows():
    growth_str = f"{row['mat_growth_pct']:+.1f}%" if pd.notna(row['mat_growth_pct']) else "N/A"
    print(f"  {row['brand']:<18} {row['mat_value']:>10,.0f}  {growth_str:>14}")

# Brand segmentation
segments = dash.brand_segmentation(df, metric="trx")
print(f"\n✓ Brand Segmentation:")
print(f"  {'Brand':<18} {'Avg Share %':>12}  {'Trend Slope':>12}  {'Segment':>12}")
print(f"  {'-'*57}")
for _, row in segments.iterrows():
    print(f"  {row['brand']:<18} {row['avg_share_pct']:>11.1f}%  {row['share_trend_slope']:>12.4f}  {row['segment']:>12}")

# Share of Voice
sov_df = pd.DataFrame({
    "brand":            ["Cardivance", "HyperControl", "Norvalpha", "Vascuban"],
    "detailing_visits": [1250,          840,            620,          390],
})
sov = dash.calculate_therapy_area_share_of_voice(sov_df)
print(f"\n✓ Share of Voice (Detailing Visits):")
print(f"  {'Brand':<18} {'Visits':>8}  {'SoV %':>7}  {'Rank':>5}")
print(f"  {'-'*42}")
for _, row in sov.iterrows():
    print(f"  {row['brand']:<18} {row['total_visits']:>8,}  {row['share_of_voice_pct']:>6.1f}%  #{row['rank']}")

print("\n" + "=" * 62)
print("  ✅ Demo complete")
print("=" * 62)
