import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.scan_attendance_images import (
    CandidateKind, _ocr, classify_ocr_text, scan_image_directories,
)


class ImageRuleTests(unittest.TestCase):
    def test_approved_comp_leave(self):
        result = classify_ocr_text("张子俊申请8月3日调休一天 领导：同意")
        self.assertEqual(result.kind, CandidateKind.COMP_LEAVE)
        self.assertTrue(result.approved)

    def test_request_without_approval_is_pending(self):
        result = classify_ocr_text("韩胜申请调休一天")
        self.assertEqual(result.kind, CandidateKind.COMP_LEAVE)
        self.assertFalse(result.approved)

    def test_leave_types_and_half_day(self):
        result = classify_ocr_text("山西省地震局 请休假审批单 育儿假 半天 已批准")
        self.assertEqual(result.kind, CandidateKind.LEAVE)
        self.assertTrue(result.approved)
        self.assertTrue(result.partial_day)

    def test_trip_and_leveling_vehicle_attachments_count(self):
        self.assertEqual(
            classify_ocr_text("出差用车申请 审批同意").kind,
            CandidateKind.OFFICIAL_OUT,
        )
        self.assertEqual(
            classify_ocr_text("水准测量用车附件 已批准").kind,
            CandidateKind.OFFICIAL_OUT,
        )

    def test_leveling_observation_and_fieldwork_terms_count(self):
        for text in ("水准观测记录手簿", "开展水准观测", "野外水准作业"):
            with self.subTest(text=text):
                self.assertEqual(
                    classify_ocr_text(text).kind,
                    CandidateKind.OFFICIAL_OUT,
                )

    def test_ocr_combines_two_page_segmentation_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            Image.new("RGB", (100, 50), "white").save(path)
            with patch("pytesseract.image_to_string", side_effect=["水准", "观测记录手簿"]) as mocked:
                text, _hash = _ocr(path, Path("tesseract.exe"))
            self.assertEqual(mocked.call_count, 2)
            self.assertIn("水准", text)
            self.assertIn("观测记录手簿", text)

    def test_ocr_retries_rotated_landscape_image_when_initial_text_is_irrelevant(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sideways.png"
            Image.new("RGB", (100, 50), "white").save(path)
            with patch(
                "pytesseract.image_to_string",
                side_effect=["", "", "水准测量", ""],
            ) as mocked:
                text, _hash = _ocr(path, Path("tesseract.exe"))
            self.assertEqual(mocked.call_count, 4)
            self.assertIn("水准测量", text)

    def test_scan_keeps_different_files_with_same_perceptual_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new("RGB", (20, 20), "white").save(root / "a.png")
            Image.new("RGB", (20, 20), "black").save(root / "b.png")
            with patch(
                "scripts.scan_attendance_images._ocr",
                side_effect=[("水准测量 已批准", "same"), ("水准观测 已批准", "same")],
            ):
                candidates = scan_image_directories([root], Path("tesseract.exe"), workers=1)
            self.assertEqual(len(candidates), 2)

    def test_official_errand_and_approved_training_count(self):
        self.assertEqual(
            classify_ocr_text("因公外出办事 领导同意").kind,
            CandidateKind.OFFICIAL_OUT,
        )
        self.assertEqual(
            classify_ocr_text("申请参加学习培训 经组织同意").kind,
            CandidateKind.OFFICIAL_OUT,
        )

    def test_errand_and_training_vehicle_attachments_stay_irrelevant(self):
        self.assertEqual(
            classify_ocr_text("外出办事用车附件 已批准").kind,
            CandidateKind.IRRELEVANT,
        )
        self.assertEqual(
            classify_ocr_text("参加培训用车附件 组织同意").kind,
            CandidateKind.IRRELEVANT,
        )

    def test_all_formal_vehicle_applications_count_as_official_out(self):
        for text in (
            "维修用车申请",
            "山西省地震局用车审批单",
            "派车申请 已撤回",
            "出租车用车申请 已作废",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    classify_ocr_text(text).kind,
                    CandidateKind.OFFICIAL_OUT,
                )

    def test_formal_vehicle_application_is_marked_for_review(self):
        result = classify_ocr_text("山西省地震局用车审批单 已撤回")
        self.assertTrue(getattr(result, "is_vehicle_application", False))

    def test_maintenance_vehicle_application_counts(self):
        result = classify_ocr_text("维修用车申请 已批准")
        self.assertEqual(result.kind, CandidateKind.OFFICIAL_OUT)

    def test_rental_car_evidence_counts_as_official_out(self):
        for text in ("租车合同", "车辆租赁发票", "汽车租赁明细"):
            with self.subTest(text=text):
                self.assertEqual(
                    classify_ocr_text(text).kind,
                    CandidateKind.OFFICIAL_OUT,
                )

    def test_taxi_and_ride_hailing_evidence_is_irrelevant(self):
        for text in ("出租车发票", "打车订单", "网约车行程单"):
            with self.subTest(text=text):
                self.assertEqual(
                    classify_ocr_text(text).kind,
                    CandidateKind.IRRELEVANT,
                )

    def test_cancelled_latest_record_is_detected(self):
        result = classify_ocr_text("此前调休申请现撤回")
        self.assertTrue(result.cancelled)


if __name__ == "__main__":
    unittest.main()
