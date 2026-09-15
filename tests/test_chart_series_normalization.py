import sys
import os

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from database import SessionLocal, engine
import models
from routers.chart_router import get_chart_series

models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

# 1. Create or get test user
user = db.query(models.User).filter_by(username="unit_test_user").first()
if not user:
    user = models.User(username="unit_test_user", password_hash="test")
    db.add(user)
    db.commit()
    db.refresh(user)

# Clean up any existing items for this test user
db.query(models.LabItem).filter(models.LabItem.user_id == user.id).delete()
db.query(models.LabReport).filter(models.LabReport.user_id == user.id).delete()
db.commit()

# 2. Add two lab reports on different dates with different units for GLU and CR
# Hospital A on 2026-01-01: GLU in mmol/L (5.6), CR in umol/L (88.4)
rep1 = models.LabReport(user_id=user.id, report_date="2026-01-01", hospital="医院A")
db.add(rep1)
db.commit()
db.refresh(rep1)

item_glu1 = models.LabItem(
    report_id=rep1.id, user_id=user.id, item_name="空腹血糖", item_code="GLU",
    value=5.6, value_text="5.6", unit="mmol/L", ref_min=3.9, ref_max=6.1,
    test_date="2026-01-01"
)
item_cr1 = models.LabItem(
    report_id=rep1.id, user_id=user.id, item_name="血肌酐", item_code="CR",
    value=88.4, value_text="88.4", unit="umol/L", ref_min=44.0, ref_max=133.0,
    test_date="2026-01-01"
)
db.add_all([item_glu1, item_cr1])
db.commit()

# Hospital B on 2026-02-01: GLU in mg/dL (108.0), CR in mg/dL (1.0)
rep2 = models.LabReport(user_id=user.id, report_date="2026-02-01", hospital="医院B")
db.add(rep2)
db.commit()
db.refresh(rep2)

item_glu2 = models.LabItem(
    report_id=rep2.id, user_id=user.id, item_name="血糖", item_code="GLU",
    value=108.0, value_text="108", unit="mg/dL", ref_min=70.0, ref_max=110.0,
    test_date="2026-02-01"
)
item_cr2 = models.LabItem(
    report_id=rep2.id, user_id=user.id, item_name="肌酐", item_code="CR",
    value=1.0, value_text="1.0", unit="mg/dL", ref_min=0.5, ref_max=1.5,
    test_date="2026-02-01"
)
db.add_all([item_glu2, item_cr2])
db.commit()

# 3. Call get_chart_series
res = get_chart_series(codes="GLU,CR", target_user_id=user.id, current_user=user, db=db)

assert res["dates"] == ["2026-01-01", "2026-02-01"]
assert len(res["series"]) == 2

glu_series = next(s for s in res["series"] if s["code"] == "GLU")
cr_series = next(s for s in res["series"] if s["code"] == "CR")

# Verify GLU series:
assert glu_series["unit"] == "mmol/L"
# 108 mg/dL / 18.0182 = 5.99 -> 6.0
assert glu_series["data"][0] == 5.6
assert round(glu_series["data"][1], 1) == 6.0
assert glu_series["converted_flags"] == [False, True]
assert glu_series["raw_units"] == ["mmol/L", "mg/dL"]
assert glu_series["raw_values"] == [5.6, 108.0]
print("GLU chart series normalized perfectly:", glu_series["data"])

# Verify CR series:
assert cr_series["unit"] == "umol/L"
# 1.0 mg/dL * 88.4 = 88.4
assert cr_series["data"][0] == 88.4
assert cr_series["data"][1] == 88.4
assert cr_series["converted_flags"] == [False, True]
assert cr_series["raw_units"] == ["umol/L", "mg/dL"]
assert cr_series["raw_values"] == [88.4, 1.0]
print("CR chart series normalized perfectly:", cr_series["data"])

# Clean up
db.query(models.LabItem).filter(models.LabItem.user_id == user.id).delete()
db.query(models.LabReport).filter(models.LabReport.user_id == user.id).delete()
db.query(models.User).filter(models.User.id == user.id).delete()
db.commit()
db.close()

print("\nCHART SERIES INTEGRATION TEST PASSED SUCCESSFULLY!")
