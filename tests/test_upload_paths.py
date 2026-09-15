import os
import sys
import unittest
import shutil
from datetime import datetime

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from routers.upload_router import prepare_upload_target, sanitize_segment
from config import settings

class TestUploadDirectoryAndDedup(unittest.TestCase):
    def setUp(self):
        self.test_user = "test_user_path"
        self.test_doc = "lab"
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.target_dir = os.path.join(settings.UPLOAD_DIR, self.test_user, self.test_doc, self.today)
        if os.path.exists(self.target_dir):
            shutil.rmtree(self.target_dir)

    def tearDown(self):
        if os.path.exists(self.target_dir):
            shutil.rmtree(self.target_dir)

    def test_sanitize_segment(self):
        self.assertEqual(sanitize_segment("bad/path"), "bad_path")
        self.assertEqual(sanitize_segment(""), "general")
        self.assertEqual(sanitize_segment("special:*?<>"), "special_")

    def test_prepare_upload_target_dedup(self):
        # First file
        p1, u1, f1 = prepare_upload_target(self.test_user, self.test_doc, "化验报告.png")
        self.assertEqual(f1, "化验报告.png")
        self.assertEqual(u1, f"/uploads/{self.test_user}/{self.test_doc}/{self.today}/化验报告.png")
        with open(p1, "wb") as f:
            f.write(b"data1")

        # Second duplicate file
        p2, u2, f2 = prepare_upload_target(self.test_user, self.test_doc, "化验报告.png")
        self.assertEqual(f2, "化验报告(1).png")
        self.assertEqual(u2, f"/uploads/{self.test_user}/{self.test_doc}/{self.today}/化验报告(1).png")
        with open(p2, "wb") as f:
            f.write(b"data2")

        # Third duplicate file
        p3, u3, f3 = prepare_upload_target(self.test_user, self.test_doc, "化验报告.png")
        self.assertEqual(f3, "化验报告(2).png")
        self.assertEqual(u3, f"/uploads/{self.test_user}/{self.test_doc}/{self.today}/化验报告(2).png")
        with open(p3, "wb") as f:
            f.write(b"data3")

        self.assertTrue(os.path.exists(p1))
        self.assertTrue(os.path.exists(p2))
        self.assertTrue(os.path.exists(p3))

if __name__ == "__main__":
    unittest.main()
