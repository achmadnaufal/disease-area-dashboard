# Disease Area Dashboard

Pharmaceutical market intelligence: brand market share, MAT trends, and competitive tracking.

## Domain Context

Pharma BI analysts use disease area dashboards to track brand performance within a therapy area
(e.g. Cardiovascular, Oncology, Diabetes). Key metrics: TRx (total prescriptions), NRx (new Rx),
MAT (Moving Annual Total — 12-month rolling sum to eliminate seasonality), and market share %.

## Features
- **Market share analysis**: brand TRx/NRx/sales share per period with rank
- **MAT trend**: 12-month rolling total with YoY growth % per brand
- **IQVIA/Veeva-compatible**: works with standard pharma data formats
- **Sample data**: cardiovascular therapy area with 4 competing brands

## Quick Start

```python
from src.main import DiseaseAreaDashboard

dash = DiseaseAreaDashboard(config={"therapy_area": "Cardiovascular"})
df = dash.load_data("sample_data/pharma_sales.csv")
dash.validate(df)

# Market share by TRx
share = dash.market_share_analysis(df, metric="trx")
print(share.pivot(index="brand", columns="period", values="market_share_pct"))

# MAT trend
mat = dash.mat_trend(df, metric="trx")
print(mat[mat["brand"] == "Cardivance"])
```

## Running Tests
```bash
pytest tests/ -v
```
