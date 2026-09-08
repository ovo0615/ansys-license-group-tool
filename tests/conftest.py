# -*- coding: utf-8 -*-
"""共用測試資料。

授權檔與 opt 檔的副檔名都被 .gitignore 排除（裡面通常帶使用者與主機名稱），
所以測試資料一律寫在程式碼裡，不放實體樣本檔。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ansys_opt import LicenseParser  # noqa: E402

SAMPLE_LICENSE = """\
SERVER lichost1 001122334455 1055
VENDOR ansyslmd
INCREMENT anshpc ansyslmd 2026.0530 31-dec-2026 64 \\
    VENDOR_STRING=SAMPLE ISSUED=01-jan-2026 SIGN=0000
INCREMENT ansys ansyslmd 2026.0530 permanent 5 \\
    ISSUED=01-jan-2026 SIGN=0000
INCREMENT ansys ansyslmd 2026.0530 permanent 3 \\
    ISSUED=01-jan-2026 SIGN=0000
INCREMENT hfss ansyslmd 2026.0530 31-jan-2027 2 \\
    ISSUED=01-jan-2026 SIGN=0000
INCREMENT hfss ansyslmd 2026.0530 31-mar-2027 1 \\
    ISSUED=01-jan-2026 SIGN=0000
INCREMENT dysmp ansyslmd 2026.0530 31-dec-2026 8 \\
    ISSUED=01-jan-2026 SIGN=0000
"""


@pytest.fixture
def features():
    _, parsed = LicenseParser.parse_text(SAMPLE_LICENSE)
    return parsed
