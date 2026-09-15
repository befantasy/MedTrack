import sys
import os
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from database import SessionLocal, engine
import models
from routers.chart_router import get_chart_overview, get_available_metrics, determine_item_status

models.Base.metadata.create_all(bind=engine)

class TestChartOverview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.user = cls.db.query(models.User).filter_by(username="test_overview_user").first()
        if not cls.user:
            cls.user = models.User(username="test_overview_user", password_hash="test")
            cls.db.add(cls.user)
            cls.db.commit()
            cls.db.refresh(cls.user)

    @classmethod
    def tearDownClass(cls):
        cls.db.query(models.LabItem).filter_by(user_id=cls.user.id).delete()
        cls.db.query(models.LabReport).filter_by(user_id=cls.user.id).delete()
        cls.db.query(models.User).filter_by(id=cls.user.id).delete()
        cls.db.commit()
        cls.db.close()

    def setUp(self):
        self.db.query(models.LabItem).filter_by(user_id=self.user.id).delete()
        self.db.query(models.LabReport).filter_by(user_id=self.user.id).delete()
        self.db.commit()

    def test_empty_overview(self):
        res = get_chart_overview(target_user_id=self.user.id, current_user=self.user, db=self.db)
        self.assertFalse(res["has_data"])
        self.assertEqual(res["latest_stats"]["total_items"], 0)
        self.assertEqual(len(res["kpi_cards"]), 0)

    def test_overview_with_abnormal_and_normal(self):
        # Add 2 reports on 2 dates
        rep1 = models.LabReport(user_id=self.user.id, report_date="2026-01-01", hospital="H1")
        rep2 = models.LabReport(user_id=self.user.id, report_date="2026-02-01", hospital="H2")
        self.db.add_all([rep1, rep2])
        self.db.commit()

        # Date 1: CEA = 2.5 (normal, ref 0-5), WBC = 6.0 (normal, ref 4-10)
        item1 = models.LabItem(
            report_id=rep1.id, user_id=self.user.id, item_name="癌胚抗原", item_code="CEA",
            value=2.5, unit="ng/mL", ref_min=0, ref_max=5.0, test_date="2026-01-01", status="NORMAL"
        )
        item2 = models.LabItem(
            report_id=rep1.id, user_id=self.user.id, item_name="白细胞计数", item_code="WBC",
            value=6.0, unit="10^9/L", ref_min=4.0, ref_max=10.0, test_date="2026-01-01", status="NORMAL"
        )
        # Date 2: CEA = 6.8 (HIGH), WBC = 3.2 (LOW), CA199 = 45.0 (HIGH)
        item3 = models.LabItem(
            report_id=rep2.id, user_id=self.user.id, item_name="癌胚抗原", item_code="CEA",
            value=6.8, unit="ng/mL", ref_min=0, ref_max=5.0, test_date="2026-02-01", status="HIGH"
        )
        item4 = models.LabItem(
            report_id=rep2.id, user_id=self.user.id, item_name="白细胞计数", item_code="WBC",
            value=3.2, unit="10^9/L", ref_min=4.0, ref_max=10.0, test_date="2026-02-01", status="LOW"
        )
        item5 = models.LabItem(
            report_id=rep2.id, user_id=self.user.id, item_name="糖类抗原19-9", item_code="CA199",
            value=45.0, unit="U/mL", ref_min=0, ref_max=37.0, test_date="2026-02-01", status="HIGH"
        )
        self.db.add_all([item1, item2, item3, item4, item5])
        self.db.commit()

        # Check overview
        res = get_chart_overview(target_user_id=self.user.id, current_user=self.user, db=self.db)
        self.assertTrue(res["has_data"])
        self.assertEqual(res["latest_date"], "2026-02-01")
        self.assertEqual(res["latest_stats"]["total_items"], 3)
        self.assertEqual(res["latest_stats"]["abnormal_count"], 3)
        self.assertEqual(res["latest_stats"]["normal_count"], 0)

        # Check KPI cards: top cards should prioritize abnormal items (CEA, CA199, WBC)
        cards = res["kpi_cards"]
        self.assertGreaterEqual(len(cards), 3)
        codes = [c["code"] for c in cards]
        self.assertIn("CEA", codes)
        self.assertIn("WBC", codes)
        self.assertIn("CA199", codes)

        cea_card = next(c for c in cards if c["code"] == "CEA")
        self.assertEqual(cea_card["latest_value"], 6.8)
        self.assertEqual(cea_card["prev_value"], 2.5)
        self.assertEqual(cea_card["delta"], 4.3)
        self.assertEqual(cea_card["trend"], "↑")
        self.assertEqual(cea_card["status"], "HIGH")
        self.assertEqual(cea_card["status_label"], "偏高")
        self.assertEqual(len(cea_card["sparkline"]), 2)

        wbc_card = next(c for c in cards if c["code"] == "WBC")
        self.assertEqual(wbc_card["latest_value"], 3.2)
        self.assertEqual(wbc_card["prev_value"], 6.0)
        self.assertEqual(wbc_card["delta"], -2.8)
        self.assertEqual(wbc_card["trend"], "↓")
        self.assertEqual(wbc_card["status"], "LOW")
        self.assertEqual(wbc_card["status_label"], "偏低")

        # Check available metrics
        avail = get_available_metrics(target_user_id=self.user.id, current_user=self.user, db=self.db)
        self.assertEqual(len(avail), 3)
        cea_avail = next(a for a in avail if a["code"] == "CEA")
        self.assertEqual(cea_avail["latest_value"], 6.8)
        self.assertEqual(cea_avail["status"], "HIGH")

if __name__ == '__main__':
    unittest.main()
