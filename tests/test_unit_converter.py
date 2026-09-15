import sys
import os

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from services.unit_converter import normalize_lab_unit_and_value, clean_unit_str

def test_unit_cleaning():
    assert clean_unit_str(" μmol / L ") == "umol/L"
    assert clean_unit_str("10*9/L") == "10*9/L"
    assert clean_unit_str("×10^9/L") == "*10^9/L"
    print("Unit cleaning tests passed!")

def test_glucose_conversion():
    # 108 mg/dL -> ~6.0 mmol/L
    res = normalize_lab_unit_and_value("GLU", 108.0, "mg/dL", 70.0, 110.0, "70-110")
    assert res["is_converted"] is True
    assert res["unit"] == "mmol/L"
    assert round(res["value"], 1) == 6.0
    assert round(res["ref_min"], 1) == 3.9
    assert round(res["ref_max"], 1) == 6.1
    print("Glucose conversion tests passed!")

def test_creatinine_conversion():
    # 1.0 mg/dL -> 88.4 umol/L
    res = normalize_lab_unit_and_value("CR", 1.0, "mg/dL", 0.5, 1.5, "0.5-1.5")
    assert res["is_converted"] is True
    assert res["unit"] == "umol/L"
    assert res["value"] == 88.4
    assert res["ref_min"] == 44.2
    assert res["ref_max"] == 132.6
    print("Creatinine conversion tests passed!")

def test_wbc_conversion():
    # 5200 /uL -> 5.2 10^9/L
    res = normalize_lab_unit_and_value("WBC", 5200.0, "/uL", 4000.0, 10000.0, "4000-10000")
    assert res["is_converted"] is True
    assert res["unit"] == "10^9/L"
    assert res["value"] == 5.2
    assert res["ref_min"] == 4.0
    assert res["ref_max"] == 10.0

    # Normal 10^9/L -> no conversion needed
    res2 = normalize_lab_unit_and_value("WBC", 5.2, "10^9/L", 4.0, 10.0, "4.0-10.0")
    assert res2["is_converted"] is False
    assert res2["value"] == 5.2
    print("WBC conversion tests passed!")

def test_hemoglobin_conversion():
    # 13.5 g/dL -> 135.0 g/L
    res = normalize_lab_unit_and_value("HGB", 13.5, "g/dL", 12.0, 16.0, "12-16")
    assert res["is_converted"] is True
    assert res["unit"] == "g/L"
    assert res["value"] == 135.0
    assert res["ref_min"] == 120.0
    assert res["ref_max"] == 160.0
    print("Hemoglobin conversion tests passed!")

def test_tumor_marker_conversion():
    # 6800 pg/mL -> 6.8 ng/mL
    res = normalize_lab_unit_and_value("CEA", 6800.0, "pg/mL", 0.0, 5000.0, "0-5000")
    assert res["is_converted"] is True
    assert res["unit"] == "ng/mL"
    assert res["value"] == 6.8

    # 42000 U/L CA19-9 -> 42.0 U/mL
    res2 = normalize_lab_unit_and_value("CA19-9", 42000.0, "U/L", 0.0, 37000.0, "0-37000")
    assert res2["is_converted"] is True
    assert res2["unit"] == "U/mL"
    assert res2["value"] == 42.0
    print("Tumor marker conversion tests passed!")

def test_uric_acid_conversion():
    # 6.0 mg/dL -> ~356.9 umol/L
    res = normalize_lab_unit_and_value("UA", 6.0, "mg/dL", 3.5, 7.0, "3.5-7.0")
    assert res["is_converted"] is True
    assert res["unit"] == "umol/L"
    assert round(res["value"], 1) == 356.9
    print("Uric acid conversion tests passed!")

if __name__ == "__main__":
    test_unit_cleaning()
    test_glucose_conversion()
    test_creatinine_conversion()
    test_wbc_conversion()
    test_hemoglobin_conversion()
    test_tumor_marker_conversion()
    test_uric_acid_conversion()
    print("\nALL UNIT CONVERTER TESTS PASSED SUCCESSFULLY!")
