"""
Comorbidity Network Analyzer
================================
Identifies and quantifies disease co-occurrence patterns in real-world
patient populations using network-based analysis methods. Computes
pairwise comorbidity indices (Jaccard, phi coefficient, relative risk)
and detects high-comorbidity disease clusters relevant to therapeutic
area targeting.

Applications:
    - Identifying high-comorbidity patient segments for polychronic care programmes
    - Estimating shared prescribing opportunity (SFE: share-of-wallet analysis)
    - Supporting HEOR and burden-of-illness argumentation
    - Informing therapy area benchmarking and clinical trial eligibility design

References:
    - Barnett K et al. (2012). Epidemiology of multimorbidity and implications
      for health care, research, and medical education. Lancet, 380(9836), 37–43.
    - Elixhauser A et al. (1998). Comorbidity measures for use with administrative
      data. Medical Care, 36(1), 8–27.
    - Hidalgo CA et al. (2009). A dynamic network approach for the study of
      human phenomes. PLoS Computational Biology, 5(4), e1000353.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


class ComorbidityMetric(str, Enum):
    JACCARD = "jaccard"              # intersection / union
    PHI_COEFFICIENT = "phi"          # tetrachoric correlation
    RELATIVE_RISK = "relative_risk"  # RR of co-occurrence
    PREVALENCE_RATIO = "prevalence_ratio"  # PR of co-occurrence


@dataclass
class PatientRecord:
    """A single patient's diagnosis profile."""

    patient_id: str
    diagnoses: Set[str]               # ICD-10 codes or disease names
    age: Optional[float] = None
    sex: Optional[str] = None         # "M" or "F"

    def __post_init__(self) -> None:
        if not self.diagnoses:
            raise ValueError("Patient must have at least one diagnosis")
        if self.age is not None and (self.age < 0 or self.age > 130):
            raise ValueError("age must be 0–130")


@dataclass
class ComorbidityEdge:
    """Quantified relationship between two diseases."""

    disease_a: str
    disease_b: str
    co_occurrence_count: int        # patients with both
    prevalence_a: float             # P(A) — proportion of patients with A
    prevalence_b: float             # P(B)
    jaccard: float                  # Jaccard similarity coefficient
    phi: float                      # phi coefficient (tetrachoric correlation)
    relative_risk: float            # RR of co-occurrence
    prevalence_ratio: float         # prevalence ratio
    is_significant: bool            # based on phi > threshold


@dataclass
class DiseaseCluster:
    """A group of highly co-occurring diseases."""

    cluster_id: str
    diseases: List[str]
    internal_cohesion: float        # mean pairwise Jaccard within cluster
    prevalence_pct: float           # % of total patients with ≥2 cluster diseases
    lead_disease: str               # highest-prevalence disease in cluster


@dataclass
class ComorbidityNetworkReport:
    """Full comorbidity network analysis output."""

    n_patients: int
    n_unique_diseases: int
    disease_prevalences: Dict[str, float]   # disease → % of patients
    top_comorbidities: List[ComorbidityEdge]
    disease_clusters: List[DiseaseCluster]
    multimorbidity_stats: Dict               # % with 2+, 3+, 5+ conditions
    hub_diseases: List[str]                  # diseases with most comorbidity connections
    recommendations: List[str]


class ComorbidityNetworkAnalyzer:
    """
    Identifies and quantifies pairwise disease co-occurrence patterns in
    a patient population.

    Parameters
    ----------
    patients : list of PatientRecord
        Patient diagnosis profiles.
    min_co_occurrence : int, optional
        Minimum co-occurrence count to include an edge (default 2).
    phi_significance_threshold : float, optional
        Minimum |phi| to flag as significant (default 0.10).
    top_n_comorbidities : int, optional
        Number of top edges to return (default 20).

    Examples
    --------
    >>> from src.comorbidity_network_analyzer import (
    ...     ComorbidityNetworkAnalyzer, PatientRecord
    ... )
    >>> patients = [
    ...     PatientRecord("P001", {"T2DM", "Hypertension", "CKD"}),
    ...     PatientRecord("P002", {"T2DM", "Dyslipidaemia", "NAFLD"}),
    ...     PatientRecord("P003", {"Hypertension", "HF", "CKD"}),
    ...     PatientRecord("P004", {"T2DM", "Hypertension", "HF"}),
    ...     PatientRecord("P005", {"T2DM", "CKD", "Anaemia"}),
    ... ]
    >>> analyzer = ComorbidityNetworkAnalyzer(patients, min_co_occurrence=2)
    >>> report = analyzer.analyse()
    >>> print(f"Hub disease: {report.hub_diseases[0]}")
    Hub disease: T2DM
    """

    def __init__(
        self,
        patients: List[PatientRecord],
        min_co_occurrence: int = 2,
        phi_significance_threshold: float = 0.10,
        top_n_comorbidities: int = 20,
    ) -> None:
        if not patients:
            raise ValueError("At least one patient record is required")
        if min_co_occurrence < 1:
            raise ValueError("min_co_occurrence must be >= 1")
        if not (0 < phi_significance_threshold < 1):
            raise ValueError("phi_significance_threshold must be (0, 1)")
        self.patients = patients
        self.min_co = min_co_occurrence
        self.phi_thresh = phi_significance_threshold
        self.top_n = top_n_comorbidities
        self.n = len(patients)

    # ------------------------------------------------------------------
    # Build disease presence matrix (sparse)
    # ------------------------------------------------------------------

    def _disease_sets(self) -> Tuple[Dict[str, Set[str]], Set[str]]:
        """
        Returns:
            patient_diseases: patient_id → set of diseases
            all_diseases: union of all disease codes
        """
        all_diseases: Set[str] = set()
        patient_diseases = {}
        for p in self.patients:
            all_diseases |= p.diagnoses
            patient_diseases[p.patient_id] = p.diagnoses
        return patient_diseases, all_diseases

    def _disease_prevalences(self) -> Dict[str, float]:
        """Proportion of patients with each disease."""
        counts: Dict[str, int] = {}
        for p in self.patients:
            for d in p.diagnoses:
                counts[d] = counts.get(d, 0) + 1
        return {d: round(c / self.n, 6) for d, c in counts.items()}

    def _co_occurrence_count(
        self, disease_a: str, disease_b: str, patient_diseases: Dict[str, Set[str]]
    ) -> int:
        """Count patients with both diseases."""
        return sum(
            1
            for diags in patient_diseases.values()
            if disease_a in diags and disease_b in diags
        )

    # ------------------------------------------------------------------
    # Edge metrics
    # ------------------------------------------------------------------

    def _jaccard(self, n_a: int, n_b: int, n_ab: int) -> float:
        """Jaccard similarity = |A ∩ B| / |A ∪ B|."""
        union = n_a + n_b - n_ab
        return n_ab / union if union > 0 else 0.0

    def _phi(self, n_ab: int, n_a: int, n_b: int, n: int) -> float:
        """
        Phi coefficient (point-biserial) for binary disease presence/absence.
        phi = (n_ab × n_not_a_not_b − n_a_not_b × n_not_a_b) /
              sqrt(n_a × n_not_a × n_b × n_not_b)
        """
        n_a_only = n_a - n_ab
        n_b_only = n_b - n_ab
        n_neither = n - n_a - n_b + n_ab

        num = n_ab * n_neither - n_a_only * n_b_only
        denom = math.sqrt(n_a * (n - n_a) * n_b * (n - n_b))
        return round(num / denom, 6) if denom > 0 else 0.0

    def _relative_risk(self, n_ab: int, n_a: int, n_b: int, n: int) -> float:
        """
        Relative risk of B given A vs B in general population.
        RR = P(B|A) / P(B) = (n_ab/n_a) / (n_b/n)
        """
        p_b_given_a = n_ab / n_a if n_a > 0 else 0
        p_b = n_b / n
        return round(p_b_given_a / p_b, 4) if p_b > 0 else 0.0

    def _prevalence_ratio(self, n_ab: int, n_a: int, n_b: int, n: int) -> float:
        """
        Prevalence ratio = (n_ab/n) / (n_a/n × n_b/n × n) — observed/expected.
        """
        observed = n_ab / n if n > 0 else 0
        expected = (n_a / n) * (n_b / n) if n > 0 else 0
        return round(observed / expected, 4) if expected > 0 else 0.0

    # ------------------------------------------------------------------
    # Build all edges
    # ------------------------------------------------------------------

    def _build_edges(
        self,
        patient_diseases: Dict[str, Set[str]],
        all_diseases: Set[str],
        prevalences: Dict[str, float],
    ) -> List[ComorbidityEdge]:
        """Generate all qualifying comorbidity pairs."""
        disease_list = sorted(all_diseases)
        counts = {d: round(prevalences[d] * self.n) for d in disease_list}

        edges = []
        seen: Set[FrozenSet[str]] = set()
        for i, da in enumerate(disease_list):
            for db in disease_list[i + 1:]:
                pair = frozenset({da, db})
                if pair in seen:
                    continue
                seen.add(pair)

                n_ab = self._co_occurrence_count(da, db, patient_diseases)
                if n_ab < self.min_co:
                    continue

                n_a = counts[da]
                n_b = counts[db]
                if n_a == 0 or n_b == 0:
                    continue

                j = self._jaccard(n_a, n_b, n_ab)
                phi = self._phi(n_ab, n_a, n_b, self.n)
                rr = self._relative_risk(n_ab, n_a, n_b, self.n)
                pr = self._prevalence_ratio(n_ab, n_a, n_b, self.n)

                edges.append(
                    ComorbidityEdge(
                        disease_a=da,
                        disease_b=db,
                        co_occurrence_count=n_ab,
                        prevalence_a=prevalences[da],
                        prevalence_b=prevalences[db],
                        jaccard=round(j, 6),
                        phi=round(phi, 6),
                        relative_risk=rr,
                        prevalence_ratio=pr,
                        is_significant=abs(phi) >= self.phi_thresh,
                    )
                )
        return sorted(edges, key=lambda e: e.co_occurrence_count, reverse=True)

    # ------------------------------------------------------------------
    # Disease clusters (greedy modularity — simplified)
    # ------------------------------------------------------------------

    def _detect_clusters(
        self, edges: List[ComorbidityEdge], prevalences: Dict[str, float]
    ) -> List[DiseaseCluster]:
        """
        Simple greedy clustering: seed high-Jaccard edges into clusters.
        """
        # Rank edges by Jaccard
        sig_edges = sorted(
            [e for e in edges if e.is_significant],
            key=lambda e: e.jaccard,
            reverse=True,
        )
        if not sig_edges:
            return []

        # Greedy: assign each disease to the first cluster it fits, or start new one
        disease_cluster: Dict[str, int] = {}
        cluster_members: Dict[int, Set[str]] = {}
        cluster_id = 0

        for edge in sig_edges:
            c_a = disease_cluster.get(edge.disease_a)
            c_b = disease_cluster.get(edge.disease_b)

            if c_a is None and c_b is None:
                # New cluster
                cluster_members[cluster_id] = {edge.disease_a, edge.disease_b}
                disease_cluster[edge.disease_a] = cluster_id
                disease_cluster[edge.disease_b] = cluster_id
                cluster_id += 1
            elif c_a is not None and c_b is None:
                cluster_members[c_a].add(edge.disease_b)
                disease_cluster[edge.disease_b] = c_a
            elif c_b is not None and c_a is None:
                cluster_members[c_b].add(edge.disease_a)
                disease_cluster[edge.disease_a] = c_b
            # If both already in different clusters, skip (avoid merging)

        results = []
        for cid, members in cluster_members.items():
            members_list = list(members)
            # Internal cohesion: mean pairwise Jaccard
            pair_jaccards = [
                e.jaccard
                for e in edges
                if e.disease_a in members and e.disease_b in members
            ]
            cohesion = sum(pair_jaccards) / len(pair_jaccards) if pair_jaccards else 0

            # Prevalence of cluster: patients with ≥2 cluster diseases
            cluster_patients = sum(
                1
                for p in self.patients
                if len(p.diagnoses & set(members_list)) >= 2
            )
            cluster_prev = cluster_patients / self.n * 100 if self.n > 0 else 0

            lead = max(members_list, key=lambda d: prevalences.get(d, 0))

            results.append(
                DiseaseCluster(
                    cluster_id=f"C{cid + 1:02d}",
                    diseases=sorted(members_list),
                    internal_cohesion=round(cohesion, 4),
                    prevalence_pct=round(cluster_prev, 2),
                    lead_disease=lead,
                )
            )

        return sorted(results, key=lambda c: c.prevalence_pct, reverse=True)

    # ------------------------------------------------------------------
    # Multimorbidity stats
    # ------------------------------------------------------------------

    def _multimorbidity_stats(self) -> Dict:
        counts = [len(p.diagnoses) for p in self.patients]
        return {
            "mean_conditions": round(sum(counts) / len(counts), 2) if counts else 0,
            "pct_with_2_or_more": round(sum(1 for c in counts if c >= 2) / len(counts) * 100, 1),
            "pct_with_3_or_more": round(sum(1 for c in counts if c >= 3) / len(counts) * 100, 1),
            "pct_with_5_or_more": round(sum(1 for c in counts if c >= 5) / len(counts) * 100, 1),
        }

    # ------------------------------------------------------------------
    # Hub diseases (most connections)
    # ------------------------------------------------------------------

    def _hub_diseases(
        self, edges: List[ComorbidityEdge], top_k: int = 5
    ) -> List[str]:
        degree: Dict[str, int] = {}
        for e in edges:
            degree[e.disease_a] = degree.get(e.disease_a, 0) + 1
            degree[e.disease_b] = degree.get(e.disease_b, 0) + 1
        return sorted(degree, key=lambda d: degree[d], reverse=True)[:top_k]

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    @staticmethod
    def _recommendations(
        multimorbidity: Dict,
        clusters: List[DiseaseCluster],
        hub_diseases: List[str],
    ) -> List[str]:
        recs = []
        mm2 = multimorbidity.get("pct_with_2_or_more", 0)
        if mm2 > 50:
            recs.append(
                f"{mm2:.1f}% of patients have 2+ conditions. "
                "Implement a polychronic care programme with integrated care pathway."
            )
        if hub_diseases:
            recs.append(
                f"Hub disease: {hub_diseases[0]} has the most comorbidity connections. "
                "Prioritise SFE messaging around co-management opportunities."
            )
        if clusters:
            top_cluster = clusters[0]
            recs.append(
                f"Largest cluster ({top_cluster.cluster_id}) includes "
                f"{', '.join(top_cluster.diseases)} — {top_cluster.prevalence_pct:.1f}% prevalence. "
                "Evaluate shared disease management protocols."
            )
        recs.append(
            "Validate comorbidity findings against ICD-10 coded claims data "
            "(e.g., IQVIA APLD) for statistical robustness before operationalising."
        )
        return recs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse(self) -> ComorbidityNetworkReport:
        """
        Run the full comorbidity network analysis.

        Returns
        -------
        ComorbidityNetworkReport
            Pairwise edges, clusters, multimorbidity stats, hub diseases,
            and recommendations.
        """
        patient_diseases, all_diseases = self._disease_sets()
        prevalences = self._disease_prevalences()
        edges = self._build_edges(patient_diseases, all_diseases, prevalences)
        top_edges = edges[: self.top_n]
        clusters = self._detect_clusters(edges, prevalences)
        mm_stats = self._multimorbidity_stats()
        hubs = self._hub_diseases(edges)
        recs = self._recommendations(mm_stats, clusters, hubs)

        return ComorbidityNetworkReport(
            n_patients=self.n,
            n_unique_diseases=len(all_diseases),
            disease_prevalences={
                k: round(v * 100, 2) for k, v in prevalences.items()
            },
            top_comorbidities=top_edges,
            disease_clusters=clusters,
            multimorbidity_stats=mm_stats,
            hub_diseases=hubs,
            recommendations=recs,
        )

    def top_comorbidities_for(
        self, disease: str, metric: ComorbidityMetric = ComorbidityMetric.RELATIVE_RISK
    ) -> List[ComorbidityEdge]:
        """
        Return edges involving a specific disease, sorted by the chosen metric.

        Parameters
        ----------
        disease : str
            Disease code or name to query.
        metric : ComorbidityMetric
            Sorting metric (default: relative_risk).

        Returns
        -------
        list of ComorbidityEdge
        """
        patient_diseases, all_diseases = self._disease_sets()
        prevalences = self._disease_prevalences()
        if disease not in all_diseases:
            raise ValueError(f"Disease '{disease}' not found in patient data")
        edges = self._build_edges(patient_diseases, all_diseases, prevalences)
        relevant = [
            e for e in edges if e.disease_a == disease or e.disease_b == disease
        ]
        attr_map = {
            ComorbidityMetric.JACCARD: "jaccard",
            ComorbidityMetric.PHI_COEFFICIENT: "phi",
            ComorbidityMetric.RELATIVE_RISK: "relative_risk",
            ComorbidityMetric.PREVALENCE_RATIO: "prevalence_ratio",
        }
        attr = attr_map.get(metric, "relative_risk")
        return sorted(relevant, key=lambda e: getattr(e, attr), reverse=True)
