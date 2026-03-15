# disease-area-dashboard

**Domain:** Pharma BI

## Features
- Add epidemiological metrics (prevalence, incidence)
- Comprehensive documentation and examples

## Getting Started

### Installation
```bash
pip install -r requirements.txt
```

### Quick Example
```python
# See examples/ directory for complete examples
```

## Configuration
Detailed configuration options in `config/` directory.

## Testing
```bash
pytest tests/ -v
```

## Edge Cases Handled
- Null/empty input validation
- Boundary condition testing
- Type safety checks

## Contributing
See CONTRIBUTING.md for guidelines.

## License
MIT


## Usage Examples

### HCP Prescriber Segmentation

```python
from src.main import DiseaseAreaDashboard
import pandas as pd

dashboard = DiseaseAreaDashboard()

prescribers = pd.read_csv("data/hcp_transactions.csv")
segments = dashboard.segment_prescribers(
    prescribers,
    prescriber_col="hcp_id",
    volume_col="rx_units",
    brand_col="brand_name",
)
print(segments[["hcp_id", "total_units", "loyalty_score_pct", "hcp_segment"]])
# Output: ranked HCPs with segment labels for targeting prioritization
```

### Share of Voice Analysis

```python
detailing = pd.read_csv("data/field_force_activity.csv")
sov = dashboard.calculate_therapy_area_share_of_voice(
    detailing,
    brand_col="brand",
    detailing_visits_col="visits",
)
print(sov[["brand", "share_of_voice_pct", "rank"]])
```

Refer to the `tests/` directory for comprehensive example implementations.
