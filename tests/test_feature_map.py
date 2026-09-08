# -*- coding: utf-8 -*-
import json
import os

import pytest

from ansys_opt import FeatureMap
from ansys_opt.feature_map import _BUNDLED, user_map_path


def test_bundled_map_loads():
    fmap = FeatureMap.load(include_user_map=False)
    assert len(fmap) > 20
    assert fmap.product_of("anshpc").startswith("Ansys HPC")
    assert "Mechanical Enterprise" in fmap.product_of("ansys")


def test_lookup_is_case_insensitive():
    fmap = FeatureMap.load(include_user_map=False)
    assert fmap.product_of("ANSHPC") == fmap.product_of("anshpc")


def test_unknown_feature_returns_empty_rather_than_guessing():
    fmap = FeatureMap.load(include_user_map=False)
    assert fmap.product_of("no_such_feature") == ""
    assert fmap.get("no_such_feature") is None


def test_hpc_entries_carry_the_mixing_caution():
    fmap = FeatureMap.load(include_user_map=False)
    assert "anshpc_pack" in fmap.caution_of("anshpc")
    assert "anshpc" in fmap.caution_of("anshpc_pack")


def test_every_bundled_entry_declares_confidence():
    with open(_BUNDLED, encoding="utf-8") as fh:
        raw = json.load(fh)
    for name, info in raw["features"].items():
        assert info.get("confidence") in ("high", "medium"), name
        assert info.get("product"), name


def test_user_csv_overrides_bundled_entries(tmp_path):
    csv_path = tmp_path / "map.csv"
    csv_path.write_text(
        "feature,product,category\n"
        "ansys,自家命名的產品,結構\n"
        "custom_feat,自家的增量,其他\n",
        encoding="utf-8",
    )
    fmap = FeatureMap.load(include_user_map=False)
    assert fmap.load_csv(str(csv_path)) == 2

    assert fmap.product_of("ansys") == "自家命名的產品"
    assert fmap.product_of("custom_feat") == "自家的增量"
    assert fmap.user_entry_count == 2


def test_csv_without_usable_rows_raises(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("feature,product\n", encoding="utf-8")
    with pytest.raises(ValueError):
        FeatureMap.load(include_user_map=False).load_csv(str(csv_path))


def test_user_entries_can_be_saved_and_reloaded(tmp_path):
    source = tmp_path / "in.csv"
    source.write_text("mycode,我的產品,類別\n", encoding="utf-8")

    fmap = FeatureMap.load(include_user_map=False)
    fmap.load_csv(str(source))
    saved = fmap.save_user_csv(str(tmp_path / "saved.csv"))

    reloaded = FeatureMap.load(include_user_map=False)
    reloaded.load_csv(saved)
    assert reloaded.product_of("mycode") == "我的產品"
    # 只有使用者匯入的項目會被寫出，內建種子不會被複製一份
    assert reloaded.user_entry_count == 1


def test_annotate_fills_product_names(features):
    FeatureMap.load(include_user_map=False).annotate(features)
    by_name = {f.name: f for f in features}
    assert by_name["anshpc"].product
    assert by_name["dysmp"].product


def test_user_map_path_is_outside_the_repo():
    assert os.path.basename(user_map_path()) == "feature_map_user.csv"
    assert "AnsysLicenseGroupTool" in user_map_path()
