# -*- coding: utf-8 -*-
from ansys_opt import LicenseParser

from conftest import SAMPLE_LICENSE


def test_server_and_vendor():
    info, _ = LicenseParser.parse_text(SAMPLE_LICENSE)
    assert info["server"] == "lichost1"
    assert info["vendor"] == "ansyslmd"


def test_same_feature_same_expiry_counts_are_summed(features):
    ansys = [f for f in features if f.name == "ansys"]
    assert len(ansys) == 1
    assert ansys[0].count == 8          # 5 + 3
    assert ansys[0].expiry == "permanent"


def test_same_feature_different_expiry_stays_separate(features):
    hfss = sorted(f.expiry for f in features if f.name == "hfss")
    assert hfss == ["31-jan-2027", "31-mar-2027"]


def test_continuation_lines_do_not_leak_between_entries(features):
    anshpc = next(f for f in features if f.name == "anshpc")
    assert anshpc.count == 64
    assert anshpc.issued == "01-jan-2026"


def test_empty_input_is_not_an_error():
    info, parsed = LicenseParser.parse_text("")
    assert info == {}
    assert parsed == []
