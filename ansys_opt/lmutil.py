# -*- coding: utf-8 -*-
"""包裝 lmutil，讓套用設定不必停掉整個授權服務。

修改 options file 之後常見的做法是把 License Manager 停掉再啟動，
代價是所有正在跑的工作都會斷線。FlexNet 本身提供 lmreread，
可以只讓 vendor daemon 重讀授權檔與 options file，不中斷服務。
Windows 版的 lmutil.exe 隨 Ansys 一起安裝，只是很少被提到。
"""

import os
import subprocess

# Windows 上 lmutil.exe 的常見位置（依版次而異）
_WINDOWS_CANDIDATES = [
    r"C:\Program Files\ANSYS Inc\Shared Files\Licensing\winx64\lmutil.exe",
    r"C:\Program Files\ANSYS Inc\Shared Files\Licensing\win64\lmutil.exe",
]

# Linux 上的常見位置
_LINUX_CANDIDATES = [
    "/ansys_inc/shared_files/licensing/linx64/lmutil",
]

_DEFAULT_LIC_WINDOWS = (
    r"C:\Program Files\ANSYS Inc\Shared Files\Licensing"
    r"\license_files\ansyslmd.lic"
)
_DEFAULT_LIC_LINUX = "/ansys_inc/shared_files/licensing/license_files/ansyslmd.lic"


class LmUtil:
    """找出 lmutil 並組出指令。實際執行與否由呼叫端決定。"""

    @staticmethod
    def candidates() -> list[str]:
        paths = list(_WINDOWS_CANDIDATES) + list(_LINUX_CANDIDATES)
        env_dir = os.environ.get("ANSYSLIC_DIR")
        if env_dir:
            paths.insert(0, os.path.join(env_dir, "winx64", "lmutil.exe"))
            paths.insert(1, os.path.join(env_dir, "linx64", "lmutil"))
        return paths

    @staticmethod
    def find() -> str:
        """回傳找得到的 lmutil 路徑，找不到回傳空字串。"""
        for path in LmUtil.candidates():
            if os.path.isfile(path):
                return path
        return ""

    @staticmethod
    def default_license_path() -> str:
        return _DEFAULT_LIC_WINDOWS if os.name == "nt" else _DEFAULT_LIC_LINUX

    @staticmethod
    def reread_command(license_path: str = "", lmutil_path: str = "") -> list[str]:
        """讓 vendor daemon 重讀授權檔與 options file，不中斷服務。"""
        return [
            lmutil_path or LmUtil.find() or "lmutil",
            "lmreread",
            "-c", license_path or LmUtil.default_license_path(),
        ]

    @staticmethod
    def status_command(license_path: str = "", lmutil_path: str = "") -> list[str]:
        """列出目前的取用狀況，用來確認 RESERVE / MAX 是否生效。"""
        return [
            lmutil_path or LmUtil.find() or "lmutil",
            "lmstat", "-a",
            "-c", license_path or LmUtil.default_license_path(),
        ]

    @staticmethod
    def quote(command: list[str]) -> str:
        """組成可以直接貼到命令列的字串。"""
        parts = []
        for token in command:
            parts.append(f'"{token}"' if " " in token else token)
        return " ".join(parts)

    @staticmethod
    def run(command: list[str], timeout: int = 60) -> tuple[int, str]:
        """執行指令，回傳 (return code, 輸出)。找不到執行檔時回傳 (-1, 說明)。"""
        try:
            proc = subprocess.run(
                command, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
        except FileNotFoundError:
            return -1, (
                "找不到 lmutil。請確認 Ansys 授權管理元件已安裝，"
                "或手動指定 lmutil 的路徑。"
            )
        except subprocess.TimeoutExpired:
            return -1, f"指令執行超過 {timeout} 秒沒有回應。"
        except OSError as exc:
            return -1, f"執行失敗：{exc}"
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
