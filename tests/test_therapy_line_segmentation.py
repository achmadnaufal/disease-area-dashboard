"""Unit tests for TherapyLineSegmentation."""
import pytest
from src.therapy_line_segmentation import TherapyLineSegmentation, PatientRecord


@pytest.fixture
def seg():
    s = TherapyLineSegmentation(disease_area="NSCLC")
    # 1L: 4 patients
    s.add_record(PatientRecord("PT-001", "1L", "Osimertinib", "2025-01", channel="Hospital", region="Java"))
    s.add_record(PatientRecord("PT-002", "1L", "Osimertinib", "2025-02", channel="Hospital", region="Java"))
    s.add_record(PatientRecord("PT-003", "1L", "Gefitinib", "2025-01", discontinuation_reason="Progression", channel="Retail", region="Sumatra"))
    s.add_record(PatientRecord("PT-004", "1L", "Gefitinib", "2025-03", channel="Hospital", region="Java"))
    # 2L: 2 patients
    s.add_record(PatientRecord("PT-003", "2L", "Osimertinib", "2025-07", discontinuation_reason="Ongoing", channel="Hospital", region="Sumatra"))
    s.add_record(PatientRecord("PT-004", "2L", "Docetaxel", "2025-08", channel="Specialty", region="Java"))
    # 3L+: 1 patient
    s.add_record(PatientRecord("PT-003", "3L+", "Pembrolizumab", "2025-12", channel="Hospital", region="Sumatra"))
    return s


# --- PatientRecord validation ---

def test_invalid_therapy_line():
    with pytest.raises(ValueError, match="therapy_line"):
        PatientRecord("PT-001", "4L", "DrugX", "2025-01")

def test_empty_patient_id():
    with pytest.raises(ValueError, match="patient_id"):
        PatientRecord("", "1L", "DrugX", "2025-01")

def test_empty_drug_name():
    with pytest.raises(ValueError, match="drug_name"):
        PatientRecord("PT-001", "1L", "", "2025-01")


# --- Volume ---

def test_volume_by_line(seg):
    vol = seg.volume_by_line()
    assert vol["1L"] == 4
    assert vol["2L"] == 2
    assert vol["3L+"] == 1

def test_len(seg):
    assert len(seg) == 7


# --- Market share ---

def test_market_share_keys(seg):
    shares = seg.market_share_by_line()
    assert "1L" in shares
    assert "2L" in shares

def test_market_share_sums_to_100(seg):
    shares = seg.market_share_by_line()
    for line, drugs in shares.items():
        total = sum(drugs.values())
        assert abs(total - 100.0) < 0.5, f"{line} shares don't sum to 100: {total}"

def test_top_drug_1l(seg):
    top = seg.top_drug_per_line()
    assert top["1L"][0] == "Osimertinib"  # 2 vs 2 — tied, first by name
    # Both have 50% share
    assert top["1L"][1] == 50.0


# --- Progression ---

def test_progression_rates(seg):
    rates = seg.progression_rates()
    assert rates["to_2L_pct"] == 50.0  # 2 out of 4
    assert rates["to_3L_plus_pct"] == 25.0  # 1 out of 4

def test_progression_no_1l():
    s = TherapyLineSegmentation()
    s.add_record(PatientRecord("PT-001", "2L", "DrugX", "2025-01"))
    rates = s.progression_rates()
    assert rates["to_2L_pct"] == 0.0
    assert rates["to_3L_plus_pct"] == 0.0


# --- Filter ---

def test_filter_by_line(seg):
    records = seg.filter_by_line("1L")
    assert len(records) == 4

def test_filter_invalid_line(seg):
    with pytest.raises(ValueError):
        seg.filter_by_line("5L")


# --- Discontinuation ---

def test_discontinuation_breakdown_has_ongoing(seg):
    breakdown = seg.discontinuation_breakdown()
    assert "Ongoing" in breakdown

def test_discontinuation_sums_to_100(seg):
    breakdown = seg.discontinuation_breakdown()
    total = sum(breakdown.values())
    assert abs(total - 100.0) < 0.5

def test_discontinuation_by_line(seg):
    breakdown = seg.discontinuation_breakdown("1L")
    assert "Progression" in breakdown


# --- Channel split ---

def test_channel_split_has_hospital(seg):
    ch = seg.channel_split()
    assert "Hospital" in ch

def test_channel_split_sums_to_100(seg):
    ch = seg.channel_split()
    assert abs(sum(ch.values()) - 100.0) < 0.5


# --- Region ---

def test_region_volume(seg):
    rv = seg.region_volume()
    assert rv["Java"] > rv["Sumatra"]


# --- Bulk add ---

def test_bulk_add():
    s = TherapyLineSegmentation()
    records = [
        PatientRecord(f"PT-{i:03d}", "1L", "DrugA", "2025-01")
        for i in range(5)
    ]
    n = s.add_records_bulk(records)
    assert n == 5
    assert len(s) == 5


# --- Full summary ---

def test_full_summary_keys(seg):
    summary = seg.full_summary()
    for key in ["disease_area", "volume_by_line", "market_share_by_line",
                "progression_rates", "discontinuation_breakdown"]:
        assert key in summary

def test_repr(seg):
    assert "NSCLC" in repr(seg)
