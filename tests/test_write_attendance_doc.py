import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.write_attendance_doc import (
    AttendanceSummary, OfficialOutDetail, _close_word, read_attendance_doc,
    read_official_out_details, write_attendance_doc,
)
from datetime import date


TEMPLATE = Path(r"E:\山西省地震局工作\大同台\考勤\2026年8月测试模板\202608DTZ考勤表.doc")


@unittest.skipUnless(TEMPLATE.is_file(), "本机缺少Word考勤模板")
class WriteAttendanceDocTests(unittest.TestCase):
    def test_quits_wps_while_anchor_document_is_still_open(self):
        events = []
        class Anchor:
            def Close(self, **_kwargs): events.append("anchor-close")
        class Word:
            def Quit(self, **_kwargs): events.append("word-quit")
        class PythonCom:
            def CoUninitialize(self): events.append("com-uninit")
        _close_word(PythonCom(), Word(), Anchor())
        self.assertEqual(events[0], "word-quit")

    def test_writes_existing_and_appends_new_person_without_touching_template(self):
        original_hash = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "202608DTZ考勤表.doc"
            summaries = {
                "薛志文": AttendanceSummary(
                    attendance=5, official_out=1, leave=0,
                    all_day_duty=2, day_duty=3, comp_leave=4,
                ),
                "李文超": AttendanceSummary(attendance=7),
            }
            details = [OfficialOutDetail(
                registrant="薛志文", category="因公外出办事",
                reason="水准测量", location="上皇庄",
                days=(date(2026, 8, 6),), approver="张主任",
                companions=("李文超",), remarks="携带仪器",
            )]
            write_attendance_doc(TEMPLATE, output, summaries, official_out_details=details)
            self.assertTrue(output.is_file())
            self.assertEqual(output.suffix.lower(), ".doc")
            rows = read_attendance_doc(output)
            self.assertEqual(rows["薛志文"]["出勤"], "5")
            self.assertEqual(rows["薛志文"]["因公外出"], "1")
            self.assertEqual(rows["薛志文"]["请假"], "")
            self.assertEqual(rows["薛志文"]["全日班"], "2")
            self.assertEqual(rows["薛志文"]["白班"], "3")
            self.assertEqual(rows["薛志文"]["补休"], "4")
            self.assertEqual(rows["李文超"]["出勤"], "7")
            self.assertEqual(rows["李文超"]["因公外出"], "")
            detail_rows = read_official_out_details(output)
            self.assertEqual(detail_rows, [{
                "登记时间": "8.6", "登记人": "薛志文", "类别": "因公外出办事",
                "事由及地点": "水准测量，上皇庄", "起止时间、天数": "8.6 1天",
                "批准人": "张主任", "备注": "同行 李文超；携带仪器",
            }])
        self.assertEqual(hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(), original_hash)


if __name__ == "__main__":
    unittest.main()
