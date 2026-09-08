# -*- coding: utf-8 -*-
"""同名 Feature 分屬多個授權池時，:VERSION= 是唯一分得開它們的方法。

情境（實際會遇到的樣子）：先買了一份含 electronics_desktop 的小包，
後來又買了一份含同一個 Feature 的大包。兩份都是 permanent，
所以 EXPDATE 一樣、分不開；只有 INCREMENT 行上的版本不同。
"""

import pytest

from ansys_opt import (
    AccessRule,
    Group,
    LicenseParser,
    OptGenerator,
    OptParser,
    render_rule,
    split_feature_token,
    validate,
)

# 兩個授權池，同名 Feature，兩份都是 permanent
TWO_POOL_LICENSE = """\
SERVER lichost1 001122334455 1055
VENDOR ansyslmd
INCREMENT electronics_desktop ansyslmd 2022.0202 permanent 1 \
    ISSUED=01-jan-2023 SIGN=0000
INCREMENT electronics_desktop ansyslmd 2024.0113 permanent 2 \
    ISSUED=01-jan-2023 SIGN=0000
INCREMENT elec_solve_maxwell ansyslmd 2022.0202 permanent 1 \
    ISSUED=01-jan-2023 SIGN=0000
INCREMENT elec_solve_maxwell ansyslmd 2024.0113 permanent 1 \
    ISSUED=01-jan-2023 SIGN=0000
INCREMENT elec_solve_hfss ansyslmd 2024.0113 permanent 1 \
    ISSUED=01-jan-2023 SIGN=0000
"""


@pytest.fixture
def two_pool_features():
    _, parsed = LicenseParser.parse_text(TWO_POOL_LICENSE)
    return parsed


# ── 解析：兩個池必須分開列 ──

def test_pools_with_same_expiry_are_not_merged(two_pool_features):
    desktop = [f for f in two_pool_features if f.name == "electronics_desktop"]
    assert len(desktop) == 2, "同名不同版本的授權池被併成一筆了"
    assert {f.version for f in desktop} == {"2022.0202", "2024.0113"}
    assert {(f.version, f.count) for f in desktop} == {
        ("2022.0202", 1), ("2024.0113", 2),
    }


def test_same_version_rows_still_sum(two_pool_features):
    """同一個池裡的多行 INCREMENT 仍然要加總。"""
    _, parsed = LicenseParser.parse_text(
        TWO_POOL_LICENSE
        + "INCREMENT elec_solve_hfss ansyslmd 2024.0113 permanent 3 SIGN=0000\n"
    )
    hfss = [f for f in parsed if f.name == "elec_solve_hfss"]
    assert len(hfss) == 1
    assert hfss[0].count == 4


# ── token 拆解 ──

@pytest.mark.parametrize("token,expected", [
    ("plain", ("plain", "", "")),
    ("hfss:EXPDATE=31-dec-2026", ("hfss", "", "31-dec-2026")),
    ("rdacis:VERSION=2024.0113", ("rdacis", "2024.0113", "")),
    ("x:VERSION=1.0:EXPDATE=1-jan-2027", ("x", "1.0", "1-jan-2027")),
    ("y:version=2.0", ("y", "2.0", "")),          # 關鍵字不分大小寫
])
def test_split_feature_token(token, expected):
    assert split_feature_token(token) == expected


# ── 產生與回讀 ──

def test_render_includes_version():
    rule = AccessRule("EXCLUDE", "electronics_desktop", "", "",
                      "HOST_GROUP", "MAXWELL_ONLY", version="2024.0113")
    assert render_rule(rule) == (
        "EXCLUDE electronics_desktop:VERSION=2024.0113 "
        "HOST_GROUP MAXWELL_ONLY"
    )


def test_version_survives_roundtrip():
    groups = [Group("HOST_GROUP", "MAXWELL_ONLY", ["dsgnhost45"])]
    rules = [
        AccessRule("EXCLUDE", "electronics_desktop", "", "",
                   "HOST_GROUP", "MAXWELL_ONLY", version="2024.0113"),
        AccessRule("EXCLUDE", "elec_solve_hfss", "", "",
                   "HOST_GROUP", "MAXWELL_ONLY"),
        AccessRule("RESERVE", "elec_solve_maxwell", "", "1",
                   "HOST_GROUP", "MAXWELL_ONLY", version="2022.0202"),
    ]
    text = OptGenerator.generate(groups, rules, [], keep_comments=False)
    doc = OptParser.parse_text(text)

    assert not doc.unknown_lines
    assert [(r.feature, r.version) for r in doc.rules] == [
        ("electronics_desktop", "2024.0113"),
        ("elec_solve_hfss", ""),
        ("elec_solve_maxwell", "2022.0202"),
    ]
    # 再產生一次要逐字相同
    assert OptGenerator.generate(doc.groups, doc.rules, doc.globals,
                                 keep_comments=False) == text


# ── 檢查 ──

def test_valid_version_is_not_flagged(two_pool_features):
    """指定了存在的版本，不該再說「不在授權檔中」。"""
    rules = [AccessRule("EXCLUDE", "electronics_desktop", "", "",
                        "HOST_GROUP", "G1", version="2024.0113")]
    groups = [Group("HOST_GROUP", "G1", ["host1"])]
    issues = validate(groups, rules, [], two_pool_features)
    assert not [i for i in issues if i.code in ("FEATURE_UNKNOWN",
                                                "VERSION_UNKNOWN")]


def test_unknown_version_is_flagged(two_pool_features):
    rules = [AccessRule("EXCLUDE", "electronics_desktop", "", "",
                        "HOST_GROUP", "G1", version="2099.0101")]
    groups = [Group("HOST_GROUP", "G1", ["host1"])]
    issues = validate(groups, rules, [], two_pool_features)
    assert [i for i in issues if i.code == "VERSION_UNKNOWN"]


def test_missing_version_on_multi_pool_feature_is_noted(two_pool_features):
    """沒指定版本會擋掉全部的池，這件事要講出來。"""
    rules = [AccessRule("EXCLUDE", "electronics_desktop", "", "",
                        "HOST_GROUP", "G1")]
    groups = [Group("HOST_GROUP", "G1", ["host1"])]
    issues = validate(groups, rules, [], two_pool_features)
    noted = [i for i in issues if i.code == "VERSION_NOT_SPECIFIED"]
    assert len(noted) == 1
    assert "2022.0202" in noted[0].hint and "2024.0113" in noted[0].hint


def test_single_pool_feature_is_not_noted(two_pool_features):
    rules = [AccessRule("EXCLUDE", "elec_solve_hfss", "", "",
                        "HOST_GROUP", "G1")]
    groups = [Group("HOST_GROUP", "G1", ["host1"])]
    issues = validate(groups, rules, [], two_pool_features)
    assert not [i for i in issues if i.code == "VERSION_NOT_SPECIFIED"]


def test_count_check_is_scoped_to_the_pool(two_pool_features):
    """RESERVE 2 對 2024 那個池合法，對 2022 那個只有 1 份的池就超量。"""
    groups = [Group("HOST_GROUP", "G1", ["host1"])]
    ok = validate(groups, [AccessRule("RESERVE", "electronics_desktop", "", "2",
                                      "HOST_GROUP", "G1", version="2024.0113")],
                  [], two_pool_features)
    assert not [i for i in ok if i.code == "COUNT_EXCEEDS"]

    bad = validate(groups, [AccessRule("RESERVE", "electronics_desktop", "", "2",
                                       "HOST_GROUP", "G1", version="2022.0202")],
                   [], two_pool_features)
    assert [i for i in bad if i.code == "COUNT_EXCEEDS"]
