# -*- coding: utf-8 -*-
"""GUI 煙霧測試。

不驗證外觀，只確認視窗建得起來、各頁籤的控制項有接上核心邏輯，
並且改了規格表之後 GUI 不會壞掉。沒有顯示裝置時整份跳過。
"""

import os

import pytest

tk = pytest.importorskip("tkinter")
pytest.importorskip("ttkbootstrap")

if not os.environ.get("DISPLAY"):
    pytest.skip("沒有顯示裝置，跳過 GUI 測試", allow_module_level=True)

from ansys_license_group_tool import App  # noqa: E402
from ansys_opt import (  # noqa: E402
    GLOBAL_SPECS,
    KEYWORD_SPECS,
    TARGET_TYPES,
    AccessRule,
    Group,
)

from conftest import SAMPLE_LICENSE  # noqa: E402


@pytest.fixture
def app():
    try:
        instance = App()
    except tk.TclError as exc:
        pytest.skip(f"無法建立視窗：{exc}")
    instance.update_idletasks()
    yield instance
    instance.destroy()


def _load_sample_license(app, tmp_path):
    path = tmp_path / "sample_license.txt"
    path.write_text(SAMPLE_LICENSE, encoding="utf-8")
    app.lic_path_var.set(str(path))
    app._parse_license()
    app.update_idletasks()


def test_window_builds_with_all_tabs(app):
    assert len(app.nb.tabs()) == 4


def test_every_keyword_and_target_type_is_offered(app):
    """新增關鍵字只需要改規格表，GUI 會自己跟上。"""
    assert set(app.kw_cb["values"]) == set(KEYWORD_SPECS)
    assert set(app.target_type_cb["values"]) == set(TARGET_TYPES)
    assert set(app.gopt_cb["values"]) == set(GLOBAL_SPECS)


def test_keyword_hint_is_shown_for_every_keyword(app):
    for keyword in KEYWORD_SPECS:
        app.kw_var.set(keyword)
        app._on_keyword_change()
        assert app.kw_hint_var.get().strip(), keyword


def test_parsing_populates_feature_tree_with_product_names(app, tmp_path):
    _load_sample_license(app, tmp_path)
    rows = [app.feat_tree.item(i, "values") for i in app.feat_tree.get_children()]
    assert rows
    by_code = {row[0]: row[1] for row in rows}
    assert "HPC" in by_code["anshpc"]
    assert by_code["ansys"] != "（未收錄）"


def test_selecting_a_feature_with_two_expiry_dates_fills_expdate(app, tmp_path):
    _load_sample_license(app, tmp_path)
    label = next(l for l in app.feat_cb["values"] if l.startswith("hfss"))
    app.feat_var.set(label)
    app._on_feature_change()
    assert app.expdate_var.get() in ("31-jan-2027", "31-mar-2027")


def test_switching_keyword_toggles_the_right_inputs(app):
    app.kw_var.set("INCLUDEALL")
    app._on_keyword_change()
    assert str(app.feat_cb["state"]) == "disabled"
    assert str(app.count_entry["state"]) == "disabled"
    assert str(app.target_type_cb["state"]) == "readonly"

    app.kw_var.set("TIMEOUT")
    app._on_keyword_change()
    assert str(app.feat_cb["state"]) == "normal"
    assert str(app.count_entry["state"]) == "normal"
    assert str(app.target_type_cb["state"]) == "disabled"
    assert app.count_label_var.get() == "秒數："

    app.kw_var.set("RESERVE")
    app._on_keyword_change()
    assert app.count_label_var.get() == "數量："


def test_target_name_choices_follow_the_target_type(app):
    app.groups.append(Group("GROUP", "TeamA", ["user1"]))
    app.groups.append(Group("HOST_GROUP", "LabHosts", ["n1"]))
    app.target_type_var.set("GROUP")
    app._on_target_type_change()
    assert list(app.target_name_cb["values"]) == ["TeamA"]

    app.target_type_var.set("HOST_GROUP")
    app._on_target_type_change()
    assert list(app.target_name_cb["values"]) == ["LabHosts"]

    app.target_type_var.set("INTERNET")
    app._on_target_type_change()
    assert list(app.target_name_cb["values"]) == []


def test_quick_case_insensitive_button(app):
    app._quick_case_insensitive()
    assert [(o.keyword, o.value) for o in app.global_opts] == \
           [("GROUPCASEINSENSITIVE", "ON")]
    assert len(app.gopt_tree.get_children()) == 1


def test_preview_and_validation_run_together(app, tmp_path):
    _load_sample_license(app, tmp_path)
    app.groups.append(Group("GROUP", "TeamA", ["user1"]))
    app.rules.append(AccessRule("RESERVE", "hfss", "31-jan-2027", "99",
                                "GROUP", "TeamA"))
    app._refresh_preview()

    preview = app.preview_text.get("1.0", "end")
    assert "GROUP TeamA user1" in preview
    assert "RESERVE 99 hfss:EXPDATE=31-jan-2027 GROUP TeamA" in preview
    assert any(i.code == "COUNT_EXCEEDS" for i in app._issues)
    assert len(app.issue_tree.get_children()) == len(app._issues)


def test_keep_comments_checkbox_changes_the_output(app):
    app.groups.append(Group("GROUP", "TeamA", ["user1"], comment="說明"))

    app.keep_comments_var.set(True)
    app._refresh_preview()
    assert "#" in app.preview_text.get("1.0", "end")

    app.keep_comments_var.set(False)
    app._refresh_preview()
    assert "#" not in app.preview_text.get("1.0", "end")


def test_loading_an_existing_opt_file_repopulates_the_ui(app, tmp_path, monkeypatch):
    from tkinter import filedialog, messagebox

    source = tmp_path / "existing_options.txt"
    source.write_text(
        "GROUPCASEINSENSITIVE ON\n"
        "GROUP TeamA user1 user2\n"
        "# 保留給電磁組\n"
        "RESERVE 1 hfss GROUP TeamA\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(source))
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **kw: "ok")

    app._load_existing_opt()

    assert [g.name for g in app.groups] == ["TeamA"]
    assert app.rules[0].comment == "保留給電磁組"
    assert [(o.keyword, o.value) for o in app.global_opts] == \
           [("GROUPCASEINSENSITIVE", "ON")]
    assert len(app.rule_tree.get_children()) == 1
    assert app.grp_listbox.size() == 1


def test_reread_command_is_shown(app):
    app.lic_for_reread_var.set("/tmp/sample.lic")
    app.update_idletasks()
    assert "lmreread" in app.reread_cmd_var.get()
    assert "/tmp/sample.lic" in app.reread_cmd_var.get()
