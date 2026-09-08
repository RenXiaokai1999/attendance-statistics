from __future__ import annotations

from getpass import getpass

from scripts.config import load_settings
from scripts.credentials import CredentialStore


def main() -> None:
    settings = load_settings()
    target = settings["credential_target"]
    account = input("考勤网站账户名：").strip()
    secret = getpass("考勤网站密码（不会显示）：")
    if not account or not secret:
        raise SystemExit("账户名和密码不能为空")
    CredentialStore().save(target, account, secret)
    print(f"已保存到 Windows 凭据管理器：{target}")


if __name__ == "__main__":
    main()
