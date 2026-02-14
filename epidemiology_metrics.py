"""Epidemiology and disease impact metrics module."""
import pandas as pd
from typing import Dict
from enum import Enum


class DiseaseStatus(Enum):
    """Disease status classifications."""
    ENDEMIC = "endemic"
    EPIDEMIC = "epidemic"
    PANDEMIC = "pandemic"
    EMERGING = "emerging"


class EpidemiologyMetrics:
    """Calculate key epidemiology metrics from disease data."""
    
    def __init__(self, disease_name: str, cases: int, population: int, deaths: int = 0):
        if cases < 0 or population <= 0 or deaths < 0:
            raise ValueError("Invalid parameters")
        self.disease_name = disease_name
        self.cases = cases
        self.population = population
        self.deaths = deaths
    
    def calculate_incidence_rate(self, per: int = 100000) -> float:
        """Calculate incidence rate per specified population."""
        return (self.cases / self.population) * per if self.population > 0 else 0
    
    def calculate_mortality_rate(self) -> float:
        """Calculate case fatality rate."""
        return (self.deaths / self.cases) * 100 if self.cases > 0 else 0
    
    def calculate_metrics(self) -> Dict:
        """Generate comprehensive metrics."""
        return {
            "disease": self.disease_name,
            "cases": self.cases,
            "deaths": self.deaths,
            "incidence_per_100k": round(self.calculate_incidence_rate(), 2),
            "cfr_percent": round(self.calculate_mortality_rate(), 2),
        }
