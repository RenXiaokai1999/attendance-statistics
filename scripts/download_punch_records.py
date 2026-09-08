from __future__ import annotations

from pathlib import Path


class PunchDownloadError(RuntimeError):
    pass


def validate_download(path: Path, expected_name: str) -> Path:
    path = Path(path)
    if path.name != expected_name or path.suffix.lower() != ".xlsx":
        raise PunchDownloadError("下载的签卡记录文件名或格式不符合预期")
    if not path.is_file() or path.stat().st_size == 0:
        raise PunchDownloadError("下载的签卡记录不存在或为空")
    return path


def download_punch_records(*_args, **_kwargs) -> Path:
    raise PunchDownloadError(
        "考勤网站当前无法建立安全连接；恢复后需完成页面控件联调"
    )
