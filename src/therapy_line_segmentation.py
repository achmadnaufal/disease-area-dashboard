"""
Therapy Line Segmentation for Pharmaceutical Disease Area Analytics.

Segments patient cohorts by therapy line (1L, 2L, 3L+) to quantify
treatment progression, identify switching patterns, and calculate
market share by line of therapy for a given disease area.

Therapy line definitions follow clinical convention:
    - 1L (First Line): Initial treatment after diagnosis
    - 2L (Second Line): Treatment after 1L failure/switch
    - 3L+ (Third Line and beyond): Subsequent therapies

Author: github.com/achmadnaufal
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PatientRecord:
    """
    Represents a single patient's therapy history entry.

    Attributes:
        patient_id: Anonymised patient identifier.
        therapy_line: Treatment line (``1L``, ``2L``, ``3L+``).
        drug_name: Generic or brand drug name.
        start_date: Treatment start date (``YYYY-MM`` format).
        end_date: Treatment end date or ``None`` if ongoing.
        discontinuation_reason: Reason for stopping (e.g., ``Progression``,
            ``Toxicity``, ``Remission``, ``Ongoing``).
        channel: Dispensing channel (``Hospital``, ``Retail``, ``Specialty``).
        region: Geographic region or territory code.
    """

    patient_id: str
    therapy_line: str
    drug_name: str
    start_date: str
    end_date: Optional[str] = None
    discontinuation_reason: str = "Ongoing"
    channel: str = "Hospital"
    region: str = "National"

    VALID_LINES = {"1L", "2L", "3L+"}
    VALID_CHANNELS = {"Hospital", "Retail", "Specialty", "Pharmacy"}

    def __post_init__(self) -> None:
        if self.therapy_line not in self.VALID_LINES:
            raise ValueError(
                f"therapy_line '{self.therapy_line}' invalid. Use: {self.VALID_LINES}"
            )
        if not self.patient_id.strip():
            raise ValueError("patient_id cannot be empty.")
        if not self.drug_name.strip():
            raise ValueError("drug_name cannot be empty.")


class TherapyLineSegmentation:
    """
    Segments patient cohorts by therapy line and computes market share metrics.

    Key metrics produced:
    - Patient volume by therapy line
    - Drug market share within each therapy line
    - Therapy progression rate (% reaching 2L, 3L+)
    - Discontinuation reason breakdown
    - Regional and channel splits

    Attributes:
        disease_area (str): Name of the disease area being analysed.
        records (list[PatientRecord]): Registered patient records.

    Example::

        seg = TherapyLineSegmentation(disease_area="NSCLC")
        seg.add_record(PatientRecord(
            patient_id="PT-001",
            therapy_line="1L",
            drug_name="Osimertinib",
            start_date="2025-01",
            channel="Hospital",
        ))
        print(seg.market_share_by_line())
        print(seg.progression_rates())
    """

    THERAPY_LINE_ORDER = {"1L": 1, "2L": 2, "3L+": 3}

    def __init__(self, disease_area: str = "Disease Area") -> None:
        """
        Initialize the segmentation engine.

        Args:
            disease_area: Name of the disease area (e.g., ``NSCLC``, ``T2DM``).
        """
        self.disease_area = disease_area
        self.records: List[PatientRecord] = []

    # ------------------------------------------------------------------
    # Data management
    # ------------------------------------------------------------------

    def add_record(self, record: PatientRecord) -> None:
        """
        Add a patient therapy record.

        Args:
            record: A :class:`PatientRecord` instance.
        """
        self.records.append(record)

    def add_records_bulk(self, records: List[PatientRecord]) -> int:
        """
        Bulk-add multiple patient records.

        Args:
            records: List of :class:`PatientRecord` instances.

        Returns:
            Number of records added.
        """
        for r in records:
            self.records.append(r)
        return len(records)

    def filter_by_line(self, therapy_line: str) -> List[PatientRecord]:
        """
        Return all records for a specific therapy line.

        Args:
            therapy_line: One of ``1L``, ``2L``, ``3L+``.

        Raises:
            ValueError: If therapy_line is not valid.
        """
        if therapy_line not in PatientRecord.VALID_LINES:
            raise ValueError(f"Invalid therapy_line: {therapy_line}")
        return [r for r in self.records if r.therapy_line == therapy_line]

    # ------------------------------------------------------------------
    # Market share analytics
    # ------------------------------------------------------------------

    def volume_by_line(self) -> Dict[str, int]:
        """
        Count unique patient records by therapy line.

        Returns:
            dict mapping therapy line to patient count.
        """
        counts: Dict[str, int] = defaultdict(int)
        for r in self.records:
            counts[r.therapy_line] += 1
        return dict(counts)

    def market_share_by_line(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate drug market share (%) within each therapy line.

        Market share is calculated as patient volume per drug divided by
        total patient volume in that therapy line.

        Returns:
            Nested dict: ``{therapy_line: {drug_name: share_pct, ...}, ...}``
        """
        line_drug: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        line_total: Dict[str, int] = defaultdict(int)

        for r in self.records:
            line_drug[r.therapy_line][r.drug_name] += 1
            line_total[r.therapy_line] += 1

        result: Dict[str, Dict[str, float]] = {}
        for line, drugs in line_drug.items():
            total = line_total[line]
            result[line] = {
                drug: round(count / total * 100, 1)
                for drug, count in sorted(drugs.items(), key=lambda x: -x[1])
            }
        return result

    def top_drug_per_line(self) -> Dict[str, Tuple[str, float]]:
        """
        Return the top drug (by patient share) in each therapy line.

        Returns:
            dict: ``{therapy_line: (drug_name, share_pct)}``
        """
        shares = self.market_share_by_line()
        result = {}
        for line, drugs in shares.items():
            if drugs:
                top_drug = max(drugs, key=lambda d: drugs[d])
                result[line] = (top_drug, drugs[top_drug])
        return result

    # ------------------------------------------------------------------
    # Progression analysis
    # ------------------------------------------------------------------

    def progression_rates(self) -> Dict[str, float]:
        """
        Estimate therapy line progression rates.

        Calculated as:
        - 2L progression rate = patients in 2L / patients in 1L * 100
        - 3L+ progression rate = patients in 3L+ / patients in 1L * 100

        Returns:
            dict with keys ``to_2L_pct`` and ``to_3L_plus_pct``.
            Returns 0.0 if no 1L patients.
        """
        vol = self.volume_by_line()
        n_1l = vol.get("1L", 0)
        if n_1l == 0:
            return {"to_2L_pct": 0.0, "to_3L_plus_pct": 0.0}
        return {
            "to_2L_pct": round(vol.get("2L", 0) / n_1l * 100, 1),
            "to_3L_plus_pct": round(vol.get("3L+", 0) / n_1l * 100, 1),
        }

    def discontinuation_breakdown(self, therapy_line: Optional[str] = None) -> Dict[str, float]:
        """
        Return discontinuation reason distribution as percentages.

        Args:
            therapy_line: Optional filter to a single line (``1L``, ``2L``, ``3L+``).
                If ``None``, computes across all lines.

        Returns:
            dict: ``{reason: percentage, ...}``
        """
        records = (
            self.filter_by_line(therapy_line)
            if therapy_line
            else self.records
        )
        if not records:
            return {}
        reason_counts: Dict[str, int] = defaultdict(int)
        for r in records:
            reason_counts[r.discontinuation_reason] += 1
        total = len(records)
        return {
            reason: round(count / total * 100, 1)
            for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1])
        }

    def channel_split(self, therapy_line: Optional[str] = None) -> Dict[str, float]:
        """
        Return dispensing channel distribution as percentages.

        Args:
            therapy_line: Optional therapy line filter.

        Returns:
            dict: ``{channel: percentage, ...}``
        """
        records = (
            self.filter_by_line(therapy_line)
            if therapy_line
            else self.records
        )
        if not records:
            return {}
        ch_counts: Dict[str, int] = defaultdict(int)
        for r in records:
            ch_counts[r.channel] += 1
        total = len(records)
        return {
            ch: round(count / total * 100, 1)
            for ch, count in sorted(ch_counts.items(), key=lambda x: -x[1])
        }

    def region_volume(self) -> Dict[str, int]:
        """
        Return patient volume by region.

        Returns:
            dict: ``{region: count, ...}``
        """
        counts: Dict[str, int] = defaultdict(int)
        for r in self.records:
            counts[r.region] += 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def full_summary(self) -> Dict:
        """
        Generate a comprehensive segmentation summary.

        Returns:
            dict containing all key segmentation metrics.
        """
        return {
            "disease_area": self.disease_area,
            "total_records": len(self.records),
            "volume_by_line": self.volume_by_line(),
            "market_share_by_line": self.market_share_by_line(),
            "top_drug_per_line": {
                line: {"drug": name, "share_pct": share}
                for line, (name, share) in self.top_drug_per_line().items()
            },
            "progression_rates": self.progression_rates(),
            "discontinuation_breakdown": self.discontinuation_breakdown(),
            "channel_split": self.channel_split(),
            "region_volume": self.region_volume(),
        }

    def __len__(self) -> int:
        return len(self.records)

    def __repr__(self) -> str:
        return (
            f"TherapyLineSegmentation(disease_area={self.disease_area!r}, "
            f"records={len(self.records)})"
        )
