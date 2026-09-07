# -*- coding: utf-8 -*-
"""解析 Ansys 授權檔（.lic / .txt），擷取 Feature 資訊。"""

import re

from .model import FeatureEntry

_SERVER_RE = re.compile(r"^SERVER\s+(\S+)", re.MULTILINE)
_VENDOR_RE = re.compile(r"^VENDOR\s+(\S+)", re.MULTILINE)
_INCREMENT_RE = re.compile(
    r"^(?:INCREMENT|FEATURE)\s+(\S+)\s+\S+\s+(\S+)\s+(\S+)\s+(\d+)",
    re.MULTILINE,
)
_ISSUED_RE = re.compile(r"ISSUED=(\S+)")


class LicenseParser:
    """從授權檔擷取 (server_info, features)。"""

    @staticmethod
    def parse_text(content: str) -> tuple[dict, list[FeatureEntry]]:
        server_info: dict = {}

        match = _SERVER_RE.search(content)
        if match:
            server_info["server"] = match.group(1)
        match = _VENDOR_RE.search(content)
        if match:
            server_info["vendor"] = match.group(1)

        # 行末的反斜線代表續行，先合併成單行再解析
        joined = re.sub(r"\\\s*\n\s*", " ", content)

        # 同一個 (name, expiry) 可能有多行 INCREMENT，數量要加總
        totals: dict[tuple[str, str], FeatureEntry] = {}
        for match in _INCREMENT_RE.finditer(joined):
            name, version, expiry, count = (
                match.group(1), match.group(2), match.group(3), int(match.group(4))
            )
            if expiry.lower() == "permanent":
                expiry = "permanent"

            # 只在這一行的範圍內找 ISSUED=，不要吃到下一行
            line_end = joined.find("\n", match.start())
            line = joined[match.start():line_end if line_end != -1 else len(joined)]
            issued_match = _ISSUED_RE.search(line)
            issued = issued_match.group(1) if issued_match else ""

            key = (name, expiry)
            if key in totals:
                totals[key].count += count
            else:
                totals[key] = FeatureEntry(
                    name=name, version=version, expiry=expiry,
                    count=count, issued=issued,
                )

        features = sorted(totals.values(), key=lambda f: (f.name, f.expiry))
        return server_info, features

    @staticmethod
    def parse(filepath: str) -> tuple[dict, list[FeatureEntry]]:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except OSError as exc:
            raise IOError(f"無法讀取檔案：{exc}") from exc
        return LicenseParser.parse_text(content)
