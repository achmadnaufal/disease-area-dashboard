"""
Treatment Switching Analyzer for pharmaceutical disease area BI.

Tracks patient therapy switching patterns across treatment lines to measure:
- Brand-to-generic and generic-to-brand switching rates
- Competitive wins and losses (patients switching from/to a target brand)
- Therapy line progression (Line 1 → Line 2 → Line 3)
- Formulary-driven switching signals (step edits, prior authorization changes)

Switching analysis is a core input to lifecycle management (LCM) strategy
and helps commercial teams understand erosion risk post-patent cliff and
response to competitor launches.

Methodology references:
- IQVIA Pharmacy Claims Analysis Framework (IQVIA Institute, 2023)
- Veeva CRM Activity-to-Rx correlation methodology
- ISPOR Good Practices for Observational Studies (2022)
- PhRMA Medication Switching and Adherence Research Best Practices

Author: github.com/achmadnaufal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SwitchEvent:
    """A single observed therapy switch event for one patient.

    Attributes:
        patient_id: De-identified patient identifier.
        switch_date: ISO date string (YYYY-MM-DD) of the switch event.
        from_drug: Drug/brand the patient switched FROM.
        to_drug: Drug/brand the patient switched TO.
        therapy_line: Therapy line at time of switch (1, 2, 3, etc.).
        reason_code: Optional reason code (e.g., 'ae', 'cost', 'formulary',
            'efficacy', 'physician', 'unknown').
        payer_type: Optional payer category ('commercial', 'medicare',
            'medicaid', 'cash').
    """

    patient_id: str
    switch_date: str
    from_drug: str
    to_drug: str
    therapy_line: int = 1
    reason_code: Optional[str] = None
    payer_type: Optional[str] = None


@dataclass
class SwitchFlowSummary:
    """Summary of switch flows for a target brand.

    Attributes:
        target_brand: The brand being analysed.
        total_switches: Total switch events in the dataset.
        switches_from_target: Events where patients left the target brand.
        switches_to_target: Events where patients arrived at the target brand.
        net_patient_flow: switches_to_target minus switches_from_target.
        top_destinations: Top drugs patients switched TO from target (with counts).
        top_origins: Top drugs patients switched FROM to reach target (with counts).
        switch_rate_pct: Switches from target as % of total target brand events.
        brand_to_generic_rate_pct: % of departures that went to a generic equivalent.
        competitive_loss_rate_pct: % of departures that went to a named competitor.
    """

    target_brand: str
    total_switches: int
    switches_from_target: int
    switches_to_target: int
    net_patient_flow: int
    top_destinations: List[Tuple[str, int]]
    top_origins: List[Tuple[str, int]]
    switch_rate_pct: float
    brand_to_generic_rate_pct: float
    competitive_loss_rate_pct: float


class TreatmentSwitchingAnalyzer:
    """Analyzes therapy switching patterns in pharmaceutical claims/prescription data.

    Ingests a list of SwitchEvent objects and provides slicing and aggregation
    methods for brand switching analysis, competitive intelligence, and
    formulary signal detection.

    Args:
        events: List of SwitchEvent objects (can be loaded from IQVIA, Veeva, or
            claims data extracts).
        generic_suffixes: Drug name substrings that identify generic formulations.
            Used for brand-to-generic rate calculation. Default includes common
            INN naming patterns.

    Example::

        events = [
            SwitchEvent("P001", "2025-01-15", "BrandA", "GenericA", therapy_line=1,
                        reason_code="cost", payer_type="commercial"),
            SwitchEvent("P002", "2025-02-03", "Competitor", "BrandA", therapy_line=2,
                        reason_code="efficacy"),
            SwitchEvent("P003", "2025-02-18", "BrandA", "Competitor", therapy_line=1,
                        reason_code="formulary"),
        ]
        analyzer = TreatmentSwitchingAnalyzer(events)
        summary = analyzer.brand_switch_summary("BrandA", competitors=["Competitor"])
        print(f"Net patient flow: {summary.net_patient_flow}")
    """

    def __init__(
        self,
        events: List[SwitchEvent],
        generic_suffixes: Optional[List[str]] = None,
    ) -> None:
        self._events = events
        self._generic_suffixes = generic_suffixes or [
            "generic", "hcl", "sodium", "(gx)", "[gx]", "gx", "gg",
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def brand_switch_summary(
        self,
        target_brand: str,
        competitors: Optional[List[str]] = None,
        therapy_line: Optional[int] = None,
        payer_type: Optional[str] = None,
        top_n: int = 5,
    ) -> SwitchFlowSummary:
        """Summarise switching patterns for a target brand.

        Args:
            target_brand: Brand name to analyse (case-insensitive match).
            competitors: Named competitor brands for competitive loss rate.
                If None, all non-generic destinations are treated as competitive.
            therapy_line: Filter to a specific therapy line. None = all lines.
            payer_type: Filter to a specific payer type. None = all payers.
            top_n: Number of top destinations/origins to return.

        Returns:
            SwitchFlowSummary with switch counts, rates, and top drug flows.
        """
        events = self._filter(therapy_line=therapy_line, payer_type=payer_type)

        target_upper = target_brand.upper()
        total = len(events)

        departures = [
            e for e in events if e.from_drug.upper() == target_upper
        ]
        arrivals = [
            e for e in events if e.to_drug.upper() == target_upper
        ]

        # Top destinations (where patients went after leaving target)
        dest_counts: Dict[str, int] = {}
        for e in departures:
            dest_counts[e.to_drug] = dest_counts.get(e.to_drug, 0) + 1
        top_dest = sorted(dest_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]

        # Top origins (where patients came from before joining target)
        origin_counts: Dict[str, int] = {}
        for e in arrivals:
            origin_counts[e.from_drug] = origin_counts.get(e.from_drug, 0) + 1
        top_origins = sorted(origin_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]

        # Rates
        switch_rate = (len(departures) / total * 100) if total > 0 else 0.0
        generic_count = sum(1 for e in departures if self._is_generic(e.to_drug))
        brand_to_generic_rate = (generic_count / len(departures) * 100) if departures else 0.0

        if competitors:
            comp_upper = {c.upper() for c in competitors}
            comp_count = sum(
                1 for e in departures if e.to_drug.upper() in comp_upper
            )
        else:
            # All non-generic destinations treated as competitive
            comp_count = len(departures) - generic_count
        comp_loss_rate = (comp_count / len(departures) * 100) if departures else 0.0

        return SwitchFlowSummary(
            target_brand=target_brand,
            total_switches=total,
            switches_from_target=len(departures),
            switches_to_target=len(arrivals),
            net_patient_flow=len(arrivals) - len(departures),
            top_destinations=top_dest,
            top_origins=top_origins,
            switch_rate_pct=round(switch_rate, 2),
            brand_to_generic_rate_pct=round(brand_to_generic_rate, 2),
            competitive_loss_rate_pct=round(comp_loss_rate, 2),
        )

    def therapy_line_progression(
        self,
        patient_id: Optional[str] = None,
    ) -> Dict[int, int]:
        """Count switch events by therapy line.

        Args:
            patient_id: If provided, filter to a single patient's events.

        Returns:
            Dict mapping therapy line (int) to number of switch events at that line.
        """
        events = self._events
        if patient_id:
            events = [e for e in events if e.patient_id == patient_id]

        line_counts: Dict[int, int] = {}
        for e in events:
            line_counts[e.therapy_line] = line_counts.get(e.therapy_line, 0) + 1
        return dict(sorted(line_counts.items()))

    def formulary_signal_detector(
        self,
        target_brand: str,
        lookback_months: int = 3,
        min_events: int = 5,
    ) -> Dict:
        """Detect potential formulary-driven switching signals for the target brand.

        A formulary signal is defined as a spike in departures with
        ``reason_code == 'formulary'`` or ``reason_code == 'step_edit'``
        in the most recent period.

        Args:
            target_brand: Brand to monitor.
            lookback_months: Not used for filtering in this implementation
                (events are pre-filtered by caller). Included for API consistency
                with time-series implementations.
            min_events: Minimum departure events to compute signal
                (returns ``"insufficient_data"`` otherwise).

        Returns:
            Dict with:
                - ``formulary_switch_count``: departures with formulary reason.
                - ``formulary_switch_pct``: % of departures with formulary reason.
                - ``signal_strength``: 'strong' (>30%), 'moderate' (>15%), 'weak', or
                  'insufficient_data'.
                - ``affected_payer_types``: Payer types with formulary switches.
        """
        target_upper = target_brand.upper()
        departures = [e for e in self._events if e.from_drug.upper() == target_upper]

        if len(departures) < min_events:
            return {
                "formulary_switch_count": 0,
                "formulary_switch_pct": 0.0,
                "signal_strength": "insufficient_data",
                "affected_payer_types": [],
            }

        formulary_codes = {"formulary", "step_edit", "prior_auth", "pa"}
        formulary_events = [
            e for e in departures
            if e.reason_code and e.reason_code.lower() in formulary_codes
        ]

        formulary_pct = len(formulary_events) / len(departures) * 100
        strength = (
            "strong" if formulary_pct > 30
            else "moderate" if formulary_pct > 15
            else "weak"
        )

        payer_types = list({e.payer_type for e in formulary_events if e.payer_type})

        return {
            "formulary_switch_count": len(formulary_events),
            "formulary_switch_pct": round(formulary_pct, 2),
            "signal_strength": strength,
            "affected_payer_types": sorted(payer_types),
        }

    def reason_code_distribution(
        self,
        from_drug: Optional[str] = None,
        to_drug: Optional[str] = None,
    ) -> Dict[str, int]:
        """Count switch events by reason code, optionally filtered by drug pair.

        Args:
            from_drug: Filter departures from this drug. None = all.
            to_drug: Filter arrivals to this drug. None = all.

        Returns:
            Dict mapping reason_code → count (including 'unknown' for None).
        """
        events = self._events
        if from_drug:
            events = [e for e in events if e.from_drug.upper() == from_drug.upper()]
        if to_drug:
            events = [e for e in events if e.to_drug.upper() == to_drug.upper()]

        dist: Dict[str, int] = {}
        for e in events:
            code = e.reason_code or "unknown"
            dist[code] = dist.get(code, 0) + 1
        return dist

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _filter(
        self,
        therapy_line: Optional[int] = None,
        payer_type: Optional[str] = None,
    ) -> List[SwitchEvent]:
        events = self._events
        if therapy_line is not None:
            events = [e for e in events if e.therapy_line == therapy_line]
        if payer_type:
            events = [e for e in events if e.payer_type == payer_type]
        return events

    def _is_generic(self, drug_name: str) -> bool:
        """Heuristic: check if a drug name looks like a generic formulation."""
        lower = drug_name.lower()
        return any(suffix in lower for suffix in self._generic_suffixes)
