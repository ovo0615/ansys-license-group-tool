# -*- coding: utf-8 -*-
"""GUI 煙霧測試。

不驗證外觀，只確認視窗建得起來、各頁籤的控制項有接上核心邏輯，
並且改了規格表之後 GUI 不會壞掉。沒有顯示裝置時整份跳過。
"""

import os
import sys

import pytest

tk = pytest.importorskip("tkinter")
pytest.importorskip("ttkbootstrap")


def _has_display() -> bool:
    """Windows 與 macOS 的視窗系統一定在，Linux 才需要看環境變數。

    只判斷 DISPLAY 會讓整份測試在 Windows 上靜默跳過——DISPLAY 是 X11 的東西，
    Windows 永遠沒有。而 allow_module_level 的跳過只會記成 1 筆，
    數字看起來完全正常，實際上這 12 項從來沒跑過。
    """
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


if not _has_display():
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


def _withdraw_instead_of_centering(self):
    """取代 App.center_window，把視窗收起來而不是置中。

    這些測試檢查的是控制項狀態與資料流，不是外觀，沒有必要真的顯示視窗。
    時機很講究：App.__init__ 最後呼叫的 center_window() 裡有 update_idletasks()，
    那正是視窗被映射到螢幕的那一刻。等 App() 回傳後才 withdraw() 已經太晚，
    畫面還是會閃一下。
    """
    self.withdraw()


@pytest.fixture(scope="module")
def _live_app():
    """整份測試共用同一個 App。

    ttkbootstrap 的 Style 是行程層級的單例，綁在第一個 root 上，
    它自己的 window.py 就寫明「一個行程只能有一個 root，請重複使用」。
    原本每個測試各建一次 App，撞到這條限制時的症狀不是穩定失敗而是偶發——
    有時候乾淨過關，有時候整批 RuntimeError，取決於前一個 root 有沒有被回收乾淨。

    建立失敗時要特別把半成品 root 清掉：App() 拋 TclError 時那個 root
    已經存在但沒有人持有它，直接 skip 會讓它一直活著，
    接下來每一個測試都會撞上單一 root 檢查，變成一路雪崩。
    """
    original_center = App.center_window
    App.center_window = _withdraw_instead_of_centering
    try:
        try:
            instance = App()
        except tk.TclError as exc:
            stranded = getattr(tk, "_default_root", None)
            if stranded is not None:
                try:
                    stranded.destroy()
                except tk.TclError:
                    pass
            pytest.skip(f"無法建立視窗：{exc}")
    finally:
        App.center_window = original_center

    instance.update_idletasks()
    assert not instance.winfo_viewable(), "視窗不該顯示在螢幕上"

    # 每個測試開始前要還原成這組初始值
    defaults = {
        name: obj.get()
        for name, obj in vars(instance).items()
        if isinstance(obj, tk.Variable)
    }

    yield instance, defaults
    instance.destroy()


@pytest.fixture
def app(_live_app):
    """共用的 App，但每個測試拿到的都是重設過的乾淨狀態。"""
    instance, defaults = _live_app

    instance.features.clear()
    instance.groups.clear()
    instance.rules.clear()
    instance.global_opts.clear()
    instance.server_info.clear()
    instance._feat_choices.clear()
    instance.license_file = ""
    instance._issues = []

    for name, value in defaults.items():
        getattr(instance, name).set(value)

    instance._refresh_feature_tree()
    instance._refresh_feature_choices()
    instance._refresh_group_listbox()
    instance._refresh_rule_tree()
    instance._refresh_global_tree()
    instance._on_keyword_change()
    instance._on_target_type_change()
    instance.update_idletasks()

    return instance


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


# ── :VERSION= 修飾詞 ──

TWO_POOL_LICENSE = """\
SERVER lichost1 001122334455 1055
VENDOR ansyslmd
INCREMENT electronics_desktop ansyslmd 2022.0202 permanent 1 SIGN=0000
INCREMENT electronics_desktop ansyslmd 2024.0113 permanent 2 SIGN=0000
INCREMENT elec_solve_hfss ansyslmd 2024.0113 permanent 1 SIGN=0000
"""


def _load_two_pool_license(app, tmp_path):
    path = tmp_path / "two_pool.txt"
    path.write_text(TWO_POOL_LICENSE, encoding="utf-8")
    app.lic_path_var.set(str(path))
    app._parse_license()
    app.update_idletasks()


def test_multi_pool_feature_is_listed_once_per_version(app, tmp_path):
    _load_two_pool_license(app, tmp_path)
    desktop = [f for f in app.features if f.name == "electronics_desktop"]
    assert len(desktop) == 2
    # 下拉選單要分得出這兩筆，否則使用者只會看到兩個一模一樣的選項
    labels = [l for l in app.feat_cb["values"] if "electronics_desktop" in l]
    assert len(labels) == 2 and len(set(labels)) == 2


def test_selecting_a_multi_pool_feature_fills_in_the_version(app, tmp_path):
    _load_two_pool_license(app, tmp_path)
    label = next(l for l in app.feat_cb["values"]
                 if "electronics_desktop" in l and "2024.0113" in l)
    app.feat_var.set(label)
    app._on_feature_change()
    assert app.version_var.get() == "2024.0113"

    # 只有一個池的 Feature 不該帶入版本
    label = next(l for l in app.feat_cb["values"] if "elec_solve_hfss" in l)
    app.feat_var.set(label)
    app._on_feature_change()
    assert app.version_var.get() == ""


def test_version_field_reaches_the_generated_rule(app, tmp_path):
    _load_two_pool_license(app, tmp_path)
    app.groups.append(Group("HOST_GROUP", "MAXWELL_ONLY", ["dsgnhost45"]))
    app.kw_var.set("EXCLUDE")
    app._on_keyword_change()
    app.feat_var.set(next(l for l in app.feat_cb["values"]
                          if "electronics_desktop" in l and "2024.0113" in l))
    app._on_feature_change()
    app.target_type_var.set("HOST_GROUP")
    app.target_name_var.set("MAXWELL_ONLY")
    app._add_rule()

    assert app.rules[-1].version == "2024.0113"
    app._refresh_preview()
    assert ("EXCLUDE electronics_desktop:VERSION=2024.0113 "
            "HOST_GROUP MAXWELL_ONLY") in app.preview_text.get("1.0", "end")


def test_version_typed_into_the_feature_box_is_split_out(app, tmp_path):
    """使用者直接把 feature:VERSION=x 打進 Feature 欄也要能正確拆開。"""
    _load_two_pool_license(app, tmp_path)
    app.groups.append(Group("HOST_GROUP", "G1", ["host1"]))
    app.kw_var.set("EXCLUDE")
    app._on_keyword_change()
    app.feat_var.set("rdacis:VERSION=2024.0113")
    app.version_var.set("")
    app.target_type_var.set("HOST_GROUP")
    app.target_name_var.set("G1")
    app._add_rule()

    assert app.rules[-1].feature == "rdacis"
    assert app.rules[-1].version == "2024.0113"
