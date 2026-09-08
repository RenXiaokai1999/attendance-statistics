from __future__ import annotations

import json
import argparse
from pathlib import Path

from scripts.config import MonthContext, load_settings
from scripts.scan_attendance_images import (
    ImageCandidate,
    candidate_to_dict,
    scan_image_directories,
)


def write_review_manifest(candidates: list[ImageCandidate], output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "needs_visual_review",
        "candidate_count": len(candidates),
        "candidates": [candidate_to_dict(candidate) for candidate in candidates],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="生成考勤图片复核清单")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = load_settings()
    context = MonthContext(args.year, args.month, settings)

    last_reported = 0
    def report(done: int, total: int) -> None:
        nonlocal last_reported
        if done == total or done - last_reported >= 50:
            print(f"OCR进度：{done}/{total}", flush=True)
            last_reported = done

    candidates = scan_image_directories(
        context.image_month_dirs,
        Path(settings["tesseract_path"]),
        progress=report,
    )
    write_review_manifest(candidates, args.output)
    print(f"候选图片：{len(candidates)}；清单：{args.output}")


if __name__ == "__main__":
    main()
