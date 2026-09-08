from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


class CandidateKind(str, Enum):
    COMP_LEAVE = "comp_leave"
    LEAVE = "leave"
    OFFICIAL_OUT = "official_out"
    IRRELEVANT = "irrelevant"


@dataclass(frozen=True)
class TextClassification:
    kind: CandidateKind
    approved: bool
    partial_day: bool
    cancelled: bool
    matched_kinds: tuple[CandidateKind, ...]
    is_vehicle_application: bool


@dataclass(frozen=True)
class ImageCandidate:
    path: str
    sha256: str
    perceptual_hash: str
    ocr_text: str
    kind: CandidateKind
    approved: bool
    partial_day: bool
    cancelled: bool
    matched_kinds: tuple[CandidateKind, ...]
    modified_time: float
    is_vehicle_application: bool


LEAVE_WORDS = ("请休假审批单", "请假", "年假", "育儿假", "探亲假", "婚假", "病假", "事假")
APPROVAL_WORDS = ("同意", "批准", "收到")
CANCEL_WORDS = ("撤回", "撤销", "取消", "作废")
PARTIAL_WORDS = ("半天", "小时", "半日")
OFFICIAL_ERRAND_WORDS = ("因公外出办事", "外出办事", "因公外出申请")
TRAINING_WORDS = ("参加培训", "参加学习", "学习培训", "培训申请")
LEVELING_WORDS = ("水准测量", "水准观测", "水准作业", "水准观测记录手簿")
VEHICLE_WORDS = ("用车", "派车", "车辆")
RENTAL_CAR_WORDS = ("租车", "车辆租赁", "汽车租赁")
TAXI_WORDS = ("出租车", "打车", "网约车")
FORMAL_VEHICLE_APPLICATION_WORDS = ("用车申请", "用车审批单", "派车申请")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def classify_ocr_text(text: str) -> TextClassification:
    compact = "".join((text or "").split())
    matched: list[CandidateKind] = []
    if "调休" in compact:
        matched.append(CandidateKind.COMP_LEAVE)
    if any(word in compact for word in LEAVE_WORDS) and "调休" not in compact:
        matched.append(CandidateKind.LEAVE)
    is_vehicle_record = any(word in compact for word in VEHICLE_WORDS)
    is_trip_or_leveling = "出差" in compact or any(
        word in compact for word in LEVELING_WORDS
    )
    is_errand_or_training = any(
        word in compact for word in OFFICIAL_ERRAND_WORDS + TRAINING_WORDS
    )
    is_taxi_record = any(word in compact for word in TAXI_WORDS)
    is_rental_car_record = any(word in compact for word in RENTAL_CAR_WORDS)
    is_vehicle_application = any(
        word in compact for word in FORMAL_VEHICLE_APPLICATION_WORDS
    )
    if (
        is_vehicle_application
        or (
            not is_taxi_record
            and (
                is_rental_car_record
                or is_trip_or_leveling
                or (is_errand_or_training and not is_vehicle_record)
            )
        )
    ):
        matched.append(CandidateKind.OFFICIAL_OUT)
    kind = matched[0] if matched else CandidateKind.IRRELEVANT
    approved = any(word in compact for word in APPROVAL_WORDS) and not any(
        f"未{word}" in compact for word in APPROVAL_WORDS
    )
    return TextClassification(
        kind=kind,
        approved=approved,
        partial_day=any(word in compact for word in PARTIAL_WORDS),
        cancelled=any(word in compact for word in CANCEL_WORDS),
        matched_kinds=tuple(matched),
        is_vehicle_application=is_vehicle_application,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _difference_hash(image: Image.Image) -> str:
    pixels = list(ImageOps.grayscale(image).resize((9, 8)).getdata())
    bits = 0
    for row in range(8):
        for column in range(8):
            bits = (bits << 1) | int(
                pixels[row * 9 + column] > pixels[row * 9 + column + 1]
            )
    return f"{bits:016x}"


def _ocr(path: Path, tesseract_path: Path) -> tuple[str, str]:
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)
    with Image.open(path) as source:
        perceptual_hash = _difference_hash(source)
        image = ImageOps.exif_transpose(source).convert("L")
        if image.width > 1800:
            height = max(1, round(image.height * 1800 / image.width))
            image = image.resize((1800, height))
        texts = [
            pytesseract.image_to_string(image, lang="chi_sim+eng", config=f"--psm {mode}")
            for mode in (6, 11)
        ]
        initial_text = "\n".join(dict.fromkeys(texts))
        if (
            image.width > image.height
            and classify_ocr_text(initial_text).kind is CandidateKind.IRRELEVANT
        ):
            texts.extend(
                pytesseract.image_to_string(
                    image.rotate(angle, expand=True),
                    lang="chi_sim+eng",
                    config="--psm 11",
                )
                for angle in (90, 270)
            )
    return "\n".join(dict.fromkeys(texts)), perceptual_hash


def scan_image_directories(
    directories: Iterable[Path],
    tesseract_path: Path,
    *,
    workers: int = 6,
    progress=None,
) -> list[ImageCandidate]:
    candidates: list[ImageCandidate] = []
    seen_sha256: set[str] = set()
    files: list[tuple[Path, str]] = []
    for directory in directories:
        directory = Path(directory)
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            digest = _sha256(path)
            if digest in seen_sha256:
                continue
            seen_sha256.add(digest)
            files.append((path, digest))

    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(_ocr, path, Path(tesseract_path)): (path, digest)
            for path, digest in files
        }
        for future in as_completed(futures):
            path, digest = futures[future]
            completed += 1
            if progress is not None:
                progress(completed, len(files))
            try:
                text, perceptual_hash = future.result()
            except Exception:
                continue
            classification = classify_ocr_text(text)
            if classification.kind is not CandidateKind.IRRELEVANT:
                candidates.append(
                    ImageCandidate(
                        path=str(path),
                        sha256=digest,
                        perceptual_hash=perceptual_hash,
                        ocr_text=text,
                        kind=classification.kind,
                        approved=classification.approved,
                        partial_day=classification.partial_day,
                        cancelled=classification.cancelled,
                        matched_kinds=classification.matched_kinds,
                        modified_time=path.stat().st_mtime,
                        is_vehicle_application=classification.is_vehicle_application,
                    )
                )
    return sorted(candidates, key=lambda candidate: candidate.path)


def candidate_to_dict(candidate: ImageCandidate) -> dict:
    data = asdict(candidate)
    data["kind"] = candidate.kind.value
    data["matched_kinds"] = [kind.value for kind in candidate.matched_kinds]
    return data
