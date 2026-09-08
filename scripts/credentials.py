from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CredentialError(RuntimeError):
    """凭据读取或保存失败，异常内容不得包含秘密。"""


@dataclass(frozen=True)
class Credentials:
    account: str
    secret: str


class CredentialStore:
    def __init__(self, backend: Any | None = None) -> None:
        if backend is None:
            import win32cred

            backend = win32cred
        self._backend = backend

    def save(self, target: str, account: str, secret: str) -> None:
        item = {
            "Type": self._backend.CRED_TYPE_GENERIC,
            "TargetName": target,
            "UserName": account,
            "CredentialBlob": secret,
            "Persist": self._backend.CRED_PERSIST_LOCAL_MACHINE,
        }
        try:
            self._backend.CredWrite(item, 0)
        except Exception as exc:
            raise CredentialError(f"无法保存 Windows 凭据：{target}") from exc

    def read(self, target: str) -> Credentials:
        try:
            item = self._backend.CredRead(
                target, self._backend.CRED_TYPE_GENERIC, 0
            )
            blob = item["CredentialBlob"]
            secret = (
                blob.decode("utf-16-le")
                if isinstance(blob, (bytes, bytearray))
                else str(blob)
            )
            return Credentials(account=str(item["UserName"]), secret=secret)
        except Exception as exc:
            raise CredentialError(f"无法读取 Windows 凭据：{target}") from exc
