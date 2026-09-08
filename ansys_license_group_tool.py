# -*- coding: utf-8 -*-
"""Ansys License 分組設定 GUI 工具

依據：Ansys_License_分組設定_SOP.md
功能：協助使用者透過圖形介面完成 ansyslmd.opt 分組設定

解析、產生、驗證等邏輯都在 ansys_opt/ 套件裡，這個檔案只負責介面。
"""

import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import ttkbootstrap as tbs
from ttkbootstrap.constants import *

from ansys_opt import (
    ERROR,
    GLOBAL_SPECS,
    INFO,
    KEYWORD_SPECS,
    TARGET_TYPES,
    WARNING,
    AccessRule,
    FeatureEntry,
    FeatureMap,
    GlobalOption,
    Group,
    LicenseParser,
    LmUtil,
    OptGenerator,
    OptParser,
    needs_count,
    needs_feature,
    needs_target,
    render_rule,
    spec_for,
    split_feature_token,
    validate,
)

DEFAULT_OPT_PATH = (
    r"C:\Program Files\ANSYS Inc\Shared Files\Licensing"
    r"\license_files\ansyslmd.opt"
)


class App(tbs.Window):

    FONT_TITLE = ("微軟正黑體", 14, "bold")
    FONT_LABEL = ("微軟正黑體", 10)
    FONT_BOLD = ("微軟正黑體", 10, "bold")
    FONT_SMALL = ("微軟正黑體", 9)
    FONT_MONO = ("Calibri", 10)

    WIDTH, HEIGHT = 1150, 800

    def __init__(self):
        super().__init__(
            title="Ansys License 分組設定工具",
            themename="darkly",
            size=(self.WIDTH, self.HEIGHT),
        )
        self.resizable(True, True)
        self.minsize(1000, 700)

        # 資料狀態
        self.features: list[FeatureEntry] = []
        self.server_info: dict = {}
        self.groups: list[Group] = []
        self.rules: list[AccessRule] = []
        self.global_opts: list[GlobalOption] = []
        self.license_file: str = ""
        self.fmap = FeatureMap.load()

        # Feature 下拉的顯示字串 → FeatureEntry
        self._feat_choices: dict[str, FeatureEntry] = {}

        self._build_ui()
        self.center_window()

    def center_window(self):
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - self.WIDTH) // 2
        y = (screen_h - self.HEIGHT) // 2
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    # ── UI 建構 ─────────────────────────────────────────────

    def _build_ui(self):
        header = tbs.Frame(self, bootstyle="dark", padding=(16, 10))
        header.pack(fill=X)
        tbs.Label(
            header, text="Ansys License 分組設定工具",
            font=("微軟正黑體", 15, "bold"), bootstyle="light",
        ).pack(side=LEFT)

        self.nb = tbs.Notebook(self, bootstyle="dark")
        self.nb.pack(fill=BOTH, expand=True, padx=12, pady=8)

        self._build_tab1_load()
        self._build_tab2_groups()
        self._build_tab3_rules()
        self._build_tab4_export()

        self.status_var = tk.StringVar(value="就緒。請從「步驟 1」載入授權檔案。")
        tbs.Label(
            self, textvariable=self.status_var,
            font=self.FONT_SMALL, bootstyle="secondary",
            anchor=W, padding=(12, 4),
        ).pack(fill=X, side=BOTTOM)

        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

    # ── 頁籤 1：載入授權檔案 ────────────────────────────────

    def _build_tab1_load(self):
        tab = tbs.Frame(self.nb, padding=16)
        self.nb.add(tab, text="  步驟 1｜載入授權檔案  ")

        tbs.Label(tab, text="步驟 1：選擇 Ansys License 檔案",
                  font=self.FONT_TITLE, bootstyle="info").pack(anchor=W, pady=(0, 4))
        tbs.Label(
            tab,
            text="支援 .lic 與 .txt。解析後會列出所有 Feature 的產品名稱、到期日與授權數量。",
            font=self.FONT_SMALL, bootstyle="secondary",
        ).pack(anchor=W, pady=(0, 12))
        tbs.Separator(tab, bootstyle="secondary").pack(fill=X, pady=(0, 12))

        file_row = tbs.Frame(tab)
        file_row.pack(fill=X, pady=(0, 8))
        tbs.Label(file_row, text="授權檔案：", font=self.FONT_LABEL).pack(side=LEFT)
        self.lic_path_var = tk.StringVar()
        tbs.Entry(file_row, textvariable=self.lic_path_var,
                  font=self.FONT_MONO, width=60).pack(
            side=LEFT, padx=(4, 8), fill=X, expand=True)
        tbs.Button(file_row, text="瀏覽…", bootstyle="outline-info",
                   command=self._browse_license, width=8).pack(side=LEFT, padx=(0, 4))
        tbs.Button(file_row, text="解析", bootstyle="success",
                   command=self._parse_license, width=8).pack(side=LEFT)

        # 伺服器資訊
        info_frame = tbs.LabelFrame(tab, text=" 授權主機資訊 ", padding=10,
                                    bootstyle="info")
        info_frame.pack(fill=X, pady=(0, 10))
        self.server_var = tk.StringVar(value="（尚未載入）")
        self.vendor_var = tk.StringVar(value="（尚未載入）")
        tbs.Label(info_frame, text="Server：", font=self.FONT_BOLD).grid(
            row=0, column=0, sticky=W, padx=(0, 6))
        tbs.Label(info_frame, textvariable=self.server_var,
                  font=self.FONT_MONO, bootstyle="light").grid(
            row=0, column=1, sticky=W, padx=(0, 30))
        tbs.Label(info_frame, text="Vendor：", font=self.FONT_BOLD).grid(
            row=0, column=2, sticky=W, padx=(0, 6))
        tbs.Label(info_frame, textvariable=self.vendor_var,
                  font=self.FONT_MONO, bootstyle="light").grid(
            row=0, column=3, sticky=W)

        # Feature 列表
        feat_frame = tbs.LabelFrame(tab, text=" 解析出的 Feature 清單 ", padding=10,
                                    bootstyle="info")
        feat_frame.pack(fill=BOTH, expand=True)

        tree_holder = tbs.Frame(feat_frame)
        tree_holder.pack(fill=BOTH, expand=True)

        cols = ("feature", "product", "version", "expiry", "count")
        self.feat_tree = tbs.Treeview(
            tree_holder, columns=cols, show="headings", bootstyle="info", height=12)
        for col, hdr, width in [
            ("feature", "Feature 代碼", 170),
            ("product", "產品名稱", 300),
            ("version", "版本", 90),
            ("expiry", "到期日", 120),
            ("count", "授權數量", 80),
        ]:
            self.feat_tree.heading(col, text=hdr)
            self.feat_tree.column(col, width=width, anchor=W)

        feat_scroll = tbs.Scrollbar(tree_holder, orient=VERTICAL,
                                    command=self.feat_tree.yview,
                                    bootstyle="info-round")
        self.feat_tree.configure(yscrollcommand=feat_scroll.set)
        self.feat_tree.pack(side=LEFT, fill=BOTH, expand=True)
        feat_scroll.pack(side=RIGHT, fill=Y)

        map_row = tbs.Frame(feat_frame)
        map_row.pack(fill=X, pady=(8, 0))
        self.map_status_var = tk.StringVar()
        self._refresh_map_status()
        tbs.Label(map_row, textvariable=self.map_status_var,
                  font=self.FONT_SMALL, bootstyle="secondary").pack(side=LEFT)
        tbs.Button(map_row, text="匯入對照表 CSV…", bootstyle="outline-info",
                   command=self._import_feature_map).pack(side=RIGHT)

        # 讀回既有設定
        reload_row = tbs.Frame(tab)
        reload_row.pack(fill=X, pady=(10, 0))
        tbs.Label(
            reload_row,
            text="已經有一份 ansyslmd.opt？可以直接載入後修改，不必從頭建立。",
            font=self.FONT_SMALL, bootstyle="warning",
        ).pack(side=LEFT)
        tbs.Button(reload_row, text="載入現有 opt 檔…", bootstyle="outline-warning",
                   command=self._load_existing_opt).pack(side=RIGHT)

    # ── 頁籤 2：群組管理 ────────────────────────────────────

    def _build_tab2_groups(self):
        tab = tbs.Frame(self.nb, padding=16)
        self.nb.add(tab, text="  步驟 2｜群組管理  ")

        tbs.Label(tab, text="步驟 2：建立使用者群組 / 主機群組",
                  font=self.FONT_TITLE, bootstyle="warning").pack(anchor=W, pady=(0, 4))
        tbs.Label(
            tab,
            text="GROUP：依登入帳號分組 ｜ HOST_GROUP：依電腦名稱分組",
            font=self.FONT_SMALL, bootstyle="secondary",
        ).pack(anchor=W, pady=(0, 12))
        tbs.Separator(tab, bootstyle="secondary").pack(fill=X, pady=(0, 12))

        paned = tbs.Panedwindow(tab, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        left = tbs.Frame(paned, padding=(0, 0, 8, 0))
        paned.add(left, weight=1)
        tbs.Label(left, text="群組列表", font=self.FONT_BOLD,
                  bootstyle="warning").pack(anchor=W, pady=(0, 6))
        self.grp_listbox = tk.Listbox(
            left, font=self.FONT_MONO, height=16,
            bg="#2b2b2b", fg="#eeeeee", selectbackground="#F4A21A",
            selectforeground="#1a1a1a", activestyle="none",
            relief="flat", borderwidth=1,
        )
        self.grp_listbox.pack(fill=BOTH, expand=True)
        self.grp_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        btn_row = tbs.Frame(left)
        btn_row.pack(fill=X, pady=(6, 0))
        tbs.Button(btn_row, text="＋ 新增群組", bootstyle="warning-outline",
                   command=self._add_group, width=12).pack(side=LEFT, padx=(0, 4))
        tbs.Button(btn_row, text="✕ 刪除群組", bootstyle="danger-outline",
                   command=self._delete_group, width=12).pack(side=LEFT)

        right = tbs.Frame(paned, padding=(8, 0, 0, 0))
        paned.add(right, weight=2)
        self.grp_name_var = tk.StringVar(value="（請選取左側群組）")
        tbs.Label(right, textvariable=self.grp_name_var, font=self.FONT_BOLD,
                  bootstyle="warning").pack(anchor=W, pady=(0, 6))

        mem_frame = tbs.Frame(right)
        mem_frame.pack(fill=BOTH, expand=True)
        self.mem_tree = tbs.Treeview(mem_frame, columns=("member",), show="headings",
                                     bootstyle="warning", height=14)
        self.mem_tree.heading("member", text="成員名稱（使用者帳號 / 主機名稱）")
        self.mem_tree.column("member", width=300, anchor=W)
        mem_scroll = tbs.Scrollbar(mem_frame, orient=VERTICAL,
                                   command=self.mem_tree.yview,
                                   bootstyle="warning-round")
        self.mem_tree.configure(yscrollcommand=mem_scroll.set)
        self.mem_tree.pack(side=LEFT, fill=BOTH, expand=True)
        mem_scroll.pack(side=RIGHT, fill=Y)

        add_mem_frame = tbs.Frame(right)
        add_mem_frame.pack(fill=X, pady=(6, 0))
        tbs.Label(add_mem_frame, text="新成員名稱：",
                  font=self.FONT_LABEL).pack(side=LEFT)
        self.new_mem_var = tk.StringVar()
        mem_entry = tbs.Entry(add_mem_frame, textvariable=self.new_mem_var,
                              font=self.FONT_MONO, width=28)
        mem_entry.pack(side=LEFT, padx=(4, 8))
        mem_entry.bind("<Return>", lambda e: self._add_member())
        tbs.Button(add_mem_frame, text="加入", bootstyle="warning",
                   command=self._add_member, width=8).pack(side=LEFT, padx=(0, 4))
        tbs.Button(add_mem_frame, text="移除選取", bootstyle="danger-outline",
                   command=self._remove_member, width=10).pack(side=LEFT)

        batch_frame = tbs.LabelFrame(right, text=" 批次輸入成員（每行一個名稱）",
                                     padding=8, bootstyle="warning")
        batch_frame.pack(fill=X, pady=(8, 0))
        self.batch_text = tk.Text(batch_frame, height=4, font=self.FONT_MONO,
                                  bg="#2b2b2b", fg="#eeeeee",
                                  insertbackground="white", relief="flat")
        self.batch_text.pack(fill=X, pady=(0, 4))
        tbs.Button(batch_frame, text="批次加入", bootstyle="warning-outline",
                   command=self._batch_add_members).pack(anchor=E)

        tbs.Label(
            right,
            text="⚠ 同一個使用者只能屬於一個 GROUP，同一台主機只能屬於一個 HOST_GROUP。",
            font=self.FONT_SMALL, bootstyle="danger",
        ).pack(anchor=W, pady=(6, 0))

    # ── 頁籤 3：存取規則 + 全域設定 ─────────────────────────

    def _build_tab3_rules(self):
        tab = tbs.Frame(self.nb, padding=16)
        self.nb.add(tab, text="  步驟 3｜存取規則  ")

        tbs.Label(tab, text="步驟 3：設定存取規則",
                  font=self.FONT_TITLE, bootstyle="success").pack(anchor=W, pady=(0, 8))

        sub_nb = tbs.Notebook(tab, bootstyle="success")
        sub_nb.pack(fill=BOTH, expand=True)

        rules_tab = tbs.Frame(sub_nb, padding=12)
        sub_nb.add(rules_tab, text="  存取規則  ")
        self._build_rules_panel(rules_tab)

        global_tab = tbs.Frame(sub_nb, padding=12)
        sub_nb.add(global_tab, text="  全域設定  ")
        self._build_globals_panel(global_tab)

    def _build_rules_panel(self, parent):
        rule_panel = tbs.LabelFrame(parent, text=" 新增規則 ", padding=12,
                                    bootstyle="success")
        rule_panel.pack(fill=X, pady=(0, 10))

        row1 = tbs.Frame(rule_panel)
        row1.pack(fill=X, pady=(0, 6))
        tbs.Label(row1, text="規則關鍵字：", font=self.FONT_LABEL).pack(side=LEFT)
        self.kw_var = tk.StringVar(value="RESERVE")
        kw_cb = tbs.Combobox(row1, textvariable=self.kw_var, state="readonly",
                             values=list(KEYWORD_SPECS.keys()), width=16,
                             font=self.FONT_MONO, bootstyle="success")
        kw_cb.pack(side=LEFT, padx=(4, 16))
        kw_cb.bind("<<ComboboxSelected>>", self._on_keyword_change)
        self.kw_cb = kw_cb

        tbs.Label(row1, text="Feature：", font=self.FONT_LABEL).pack(side=LEFT)
        self.feat_var = tk.StringVar()
        self.feat_cb = tbs.Combobox(row1, textvariable=self.feat_var, values=[],
                                    width=44, font=self.FONT_MONO,
                                    bootstyle="success")
        self.feat_cb.pack(side=LEFT, padx=(4, 16))
        self.feat_cb.bind("<<ComboboxSelected>>", self._on_feature_change)

        # 關鍵字說明：直接把「這個關鍵字會做什麼」講清楚
        self.kw_hint_var = tk.StringVar()
        tbs.Label(rule_panel, textvariable=self.kw_hint_var, font=self.FONT_SMALL,
                  bootstyle="info", justify=LEFT, wraplength=1000).pack(
            anchor=W, pady=(0, 8))

        row2 = tbs.Frame(rule_panel)
        row2.pack(fill=X, pady=(0, 6))

        self.count_label_var = tk.StringVar(value="數量：")
        self.count_label = tbs.Label(row2, textvariable=self.count_label_var,
                                     font=self.FONT_LABEL)
        self.count_label.pack(side=LEFT)
        self.count_var = tk.StringVar(value="1")
        self.count_entry = tbs.Entry(row2, textvariable=self.count_var,
                                     font=self.FONT_MONO, width=8)
        self.count_entry.pack(side=LEFT, padx=(4, 16))

        tbs.Label(row2, text=":VERSION=", font=self.FONT_LABEL).pack(side=LEFT)
        self.version_var = tk.StringVar()
        self.version_entry = tbs.Entry(row2, textvariable=self.version_var,
                                       font=self.FONT_MONO, width=12)
        self.version_entry.pack(side=LEFT, padx=(2, 16))

        tbs.Label(row2, text=":EXPDATE=", font=self.FONT_LABEL).pack(side=LEFT)
        self.expdate_var = tk.StringVar()
        self.expdate_entry = tbs.Entry(row2, textvariable=self.expdate_var,
                                       font=self.FONT_MONO, width=14)
        self.expdate_entry.pack(side=LEFT, padx=(2, 16))

        tbs.Label(row2, text="對象類型：", font=self.FONT_LABEL).pack(side=LEFT)
        self.target_type_var = tk.StringVar(value="GROUP")
        self.target_type_cb = tbs.Combobox(
            row2, textvariable=self.target_type_var, state="readonly",
            values=list(TARGET_TYPES.keys()), width=13,
            font=self.FONT_MONO, bootstyle="success")
        self.target_type_cb.pack(side=LEFT, padx=(4, 16))
        self.target_type_cb.bind("<<ComboboxSelected>>", self._on_target_type_change)

        tbs.Label(row2, text="對象名稱：", font=self.FONT_LABEL).pack(side=LEFT)
        self.target_name_var = tk.StringVar()
        self.target_name_cb = tbs.Combobox(row2, textvariable=self.target_name_var,
                                           values=[], width=20,
                                           font=self.FONT_MONO, bootstyle="success")
        self.target_name_cb.pack(side=LEFT, padx=(4, 0))

        row3 = tbs.Frame(rule_panel)
        row3.pack(fill=X, pady=(6, 0))
        self.target_hint_var = tk.StringVar()
        tbs.Label(row3, textvariable=self.target_hint_var, font=self.FONT_SMALL,
                  bootstyle="secondary").pack(side=LEFT)

        row4 = tbs.Frame(rule_panel)
        row4.pack(fill=X, pady=(6, 0))
        tbs.Label(row4, text="說明／註解（會寫進 opt 檔）：",
                  font=self.FONT_LABEL).pack(side=LEFT)
        self.rule_comment_var = tk.StringVar()
        tbs.Entry(row4, textvariable=self.rule_comment_var,
                  font=self.FONT_MONO, width=48).pack(side=LEFT, padx=(4, 12))
        tbs.Button(row4, text="  ＋ 加入規則  ", bootstyle="success",
                   command=self._add_rule).pack(side=RIGHT)

        list_frame = tbs.LabelFrame(parent, text=" 目前規則清單 ", padding=10,
                                    bootstyle="success")
        list_frame.pack(fill=BOTH, expand=True, pady=(0, 8))
        rule_cols = ("line", "comment")
        self.rule_tree = tbs.Treeview(list_frame, columns=rule_cols,
                                      show="headings", bootstyle="success", height=10)
        self.rule_tree.heading("line", text="opt 語法")
        self.rule_tree.column("line", width=600, anchor=W)
        self.rule_tree.heading("comment", text="說明")
        self.rule_tree.column("comment", width=300, anchor=W)
        rule_scroll = tbs.Scrollbar(list_frame, orient=VERTICAL,
                                    command=self.rule_tree.yview,
                                    bootstyle="success-round")
        self.rule_tree.configure(yscrollcommand=rule_scroll.set)
        self.rule_tree.pack(side=LEFT, fill=BOTH, expand=True)
        rule_scroll.pack(side=RIGHT, fill=Y)

        btn_row = tbs.Frame(parent)
        btn_row.pack(fill=X)
        tbs.Button(btn_row, text="✕ 刪除選取規則", bootstyle="danger-outline",
                   command=self._delete_rule).pack(side=LEFT)
        tbs.Label(btn_row,
                  text="💡 INCLUDE 是白名單：一旦設定，名單外的人就不能用了。"
                       "與 EXCLUDE 衝突時 EXCLUDE 優先。",
                  font=self.FONT_SMALL, bootstyle="warning").pack(side=RIGHT)

        self._on_keyword_change()
        self._on_target_type_change()

    def _build_globals_panel(self, parent):
        tbs.Label(
            parent,
            text="整份 opt 檔的設定。這些不繫結特定群組，對所有取用者生效。",
            font=self.FONT_SMALL, bootstyle="secondary",
        ).pack(anchor=W, pady=(0, 10))

        add_panel = tbs.LabelFrame(parent, text=" 新增全域設定 ", padding=12,
                                   bootstyle="info")
        add_panel.pack(fill=X, pady=(0, 10))

        row = tbs.Frame(add_panel)
        row.pack(fill=X)
        tbs.Label(row, text="項目：", font=self.FONT_LABEL).pack(side=LEFT)
        self.gopt_var = tk.StringVar(value="GROUPCASEINSENSITIVE")
        gopt_cb = tbs.Combobox(row, textvariable=self.gopt_var, state="readonly",
                               values=list(GLOBAL_SPECS.keys()), width=24,
                               font=self.FONT_MONO, bootstyle="info")
        gopt_cb.pack(side=LEFT, padx=(4, 16))
        gopt_cb.bind("<<ComboboxSelected>>", self._on_global_change)
        self.gopt_cb = gopt_cb

        tbs.Label(row, text="值：", font=self.FONT_LABEL).pack(side=LEFT)
        self.gopt_value_var = tk.StringVar()
        self.gopt_value_cb = tbs.Combobox(row, textvariable=self.gopt_value_var,
                                          values=[], width=40,
                                          font=self.FONT_MONO, bootstyle="info")
        self.gopt_value_cb.pack(side=LEFT, padx=(4, 16))
        tbs.Button(row, text="＋ 加入", bootstyle="info",
                   command=self._add_global).pack(side=LEFT)

        self.gopt_hint_var = tk.StringVar()
        tbs.Label(add_panel, textvariable=self.gopt_hint_var, font=self.FONT_SMALL,
                  bootstyle="info", justify=LEFT, wraplength=1000).pack(
            anchor=W, pady=(8, 0))

        # 最常用的一鍵設定
        quick = tbs.Frame(add_panel)
        quick.pack(fill=X, pady=(10, 0))
        tbs.Button(
            quick, text="一鍵加入 GROUPCASEINSENSITIVE ON",
            bootstyle="outline-success", command=self._quick_case_insensitive,
        ).pack(side=LEFT)
        tbs.Label(
            quick,
            text="← 帳號大小寫對不上是分組不生效的頭號原因，建議直接開啟。",
            font=self.FONT_SMALL, bootstyle="secondary",
        ).pack(side=LEFT, padx=(8, 0))

        list_frame = tbs.LabelFrame(parent, text=" 目前的全域設定 ", padding=10,
                                    bootstyle="info")
        list_frame.pack(fill=BOTH, expand=True)
        self.gopt_tree = tbs.Treeview(list_frame, columns=("line", "comment"),
                                      show="headings", bootstyle="info", height=8)
        self.gopt_tree.heading("line", text="opt 語法")
        self.gopt_tree.column("line", width=500, anchor=W)
        self.gopt_tree.heading("comment", text="說明")
        self.gopt_tree.column("comment", width=400, anchor=W)
        self.gopt_tree.pack(fill=BOTH, expand=True)

        tbs.Button(parent, text="✕ 刪除選取設定", bootstyle="danger-outline",
                   command=self._delete_global).pack(anchor=W, pady=(8, 0))

        self._on_global_change()

    # ── 頁籤 4：檢查與匯出 ──────────────────────────────────

    def _build_tab4_export(self):
        tab = tbs.Frame(self.nb, padding=16)
        self.nb.add(tab, text="  步驟 4｜檢查與匯出  ")

        tbs.Label(tab, text="步驟 4：檢查設定並匯出 ansyslmd.opt",
                  font=self.FONT_TITLE, bootstyle="danger").pack(anchor=W, pady=(0, 8))

        cfg_frame = tbs.LabelFrame(tab, text=" 輸出設定 ", padding=12,
                                   bootstyle="danger")
        cfg_frame.pack(fill=X, pady=(0, 10))

        out_row = tbs.Frame(cfg_frame)
        out_row.pack(fill=X, pady=(0, 8))
        tbs.Label(out_row, text="輸出路徑：", font=self.FONT_LABEL).pack(side=LEFT)
        self.out_path_var = tk.StringVar(value=DEFAULT_OPT_PATH)
        tbs.Entry(out_row, textvariable=self.out_path_var,
                  font=self.FONT_MONO, width=60).pack(
            side=LEFT, padx=(4, 8), fill=X, expand=True)
        tbs.Button(out_row, text="瀏覽…", bootstyle="outline-danger",
                   command=self._browse_output, width=8).pack(side=LEFT)

        opt_row = tbs.Frame(cfg_frame)
        opt_row.pack(fill=X)
        self.backup_var = tk.BooleanVar(value=True)
        tbs.Checkbutton(opt_row, text="自動備份現有 opt 檔",
                        variable=self.backup_var,
                        bootstyle="danger").pack(side=LEFT, padx=(0, 20))
        self.keep_comments_var = tk.BooleanVar(value=True)
        tbs.Checkbutton(
            opt_row,
            text="保留註解（建議：半年後接手的人才知道每條規則為什麼存在）",
            variable=self.keep_comments_var, bootstyle="danger",
            command=self._refresh_preview,
        ).pack(side=LEFT)

        # 預覽 + 檢查結果並排
        paned = tbs.Panedwindow(tab, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, pady=(0, 10))

        preview_frame = tbs.LabelFrame(paned, text=" 預覽（opt 檔內容）",
                                       padding=10, bootstyle="danger")
        paned.add(preview_frame, weight=3)
        # 給定 height，否則 Text 會要求 24 行的高度，把下方面板擠出畫面
        self.preview_text = tk.Text(preview_frame, font=("Calibri", 10), height=12,
                                    bg="#1e1e1e", fg="#d4d4d4",
                                    insertbackground="white", relief="flat",
                                    state="disabled", wrap="none")
        prev_y = tbs.Scrollbar(preview_frame, orient=VERTICAL,
                               command=self.preview_text.yview,
                               bootstyle="danger-round")
        self.preview_text.configure(yscrollcommand=prev_y.set)
        prev_y.pack(side=RIGHT, fill=Y)
        self.preview_text.pack(fill=BOTH, expand=True)

        check_frame = tbs.LabelFrame(paned, text=" 檢查結果 ", padding=10,
                                     bootstyle="warning")
        paned.add(check_frame, weight=2)
        self.issue_tree = tbs.Treeview(check_frame, columns=("level", "message"),
                                       show="headings", bootstyle="warning",
                                       height=12)
        self.issue_tree.heading("level", text="等級")
        self.issue_tree.column("level", width=60, anchor=W)
        self.issue_tree.heading("message", text="項目（點選看處理建議）")
        self.issue_tree.column("message", width=330, anchor=W)
        issue_y = tbs.Scrollbar(check_frame, orient=VERTICAL,
                                command=self.issue_tree.yview,
                                bootstyle="warning-round")
        self.issue_tree.configure(yscrollcommand=issue_y.set)
        issue_y.pack(side=RIGHT, fill=Y)
        self.issue_tree.pack(fill=BOTH, expand=True)
        self.issue_tree.bind("<<TreeviewSelect>>", self._on_issue_select)
        self.issue_tree.tag_configure(ERROR, foreground="#ff6b6b")
        self.issue_tree.tag_configure(WARNING, foreground="#f4c542")
        self.issue_tree.tag_configure(INFO, foreground="#7ec8e3")
        self._issues = []

        btn_row = tbs.Frame(tab)
        btn_row.pack(fill=X, pady=(0, 10))
        tbs.Button(btn_row, text="🔄 重新整理並檢查", bootstyle="outline-danger",
                   command=self._refresh_preview, width=18).pack(side=LEFT, padx=(0, 8))
        tbs.Button(btn_row, text="📋 複製到剪貼簿", bootstyle="outline-info",
                   command=self._copy_preview, width=16).pack(side=LEFT)
        tbs.Button(btn_row, text="💾  匯出 Opt 檔", bootstyle="danger",
                   command=self._export_opt, width=16).pack(side=RIGHT)

        self._build_apply_panel(tab)

    def _build_apply_panel(self, parent):
        frame = tbs.LabelFrame(parent, text=" 套用設定（不必停掉整個服務） ",
                               padding=10, bootstyle="warning")
        frame.pack(fill=X)

        tbs.Label(
            frame,
            text="lmreread 只讓 vendor daemon 重讀設定，正在跑的工作不會斷線；"
                 "停止再啟動則會讓所有人斷線。",
            font=self.FONT_SMALL, bootstyle="secondary",
            justify=LEFT, wraplength=1060,
        ).pack(anchor=W, pady=(0, 6))

        row = tbs.Frame(frame)
        row.pack(fill=X)
        tbs.Label(row, text="授權檔：", font=self.FONT_LABEL).pack(side=LEFT)
        self.lic_for_reread_var = tk.StringVar(value=LmUtil.default_license_path())
        tbs.Entry(row, textvariable=self.lic_for_reread_var,
                  font=self.FONT_MONO).pack(side=LEFT, padx=(4, 12),
                                            fill=X, expand=True)
        self.reread_cmd_var = tk.StringVar()
        tbs.Button(row, text="複製指令", bootstyle="outline-warning",
                   command=self._copy_reread_cmd, width=10).pack(side=LEFT, padx=(0, 4))
        tbs.Button(row, text="執行 lmreread", bootstyle="warning",
                   command=self._run_reread, width=14).pack(side=LEFT)

        tbs.Label(frame, textvariable=self.reread_cmd_var, font=self.FONT_MONO,
                  bootstyle="secondary", justify=LEFT, wraplength=1060).pack(
            anchor=W, pady=(6, 0))

        self._refresh_reread_cmd()
        self.lic_for_reread_var.trace_add(
            "write", lambda *_: self._refresh_reread_cmd())

    # ─────────────────────────────────────────────────────────
    #  頁籤 1 事件
    # ─────────────────────────────────────────────────────────

    def _refresh_map_status(self):
        total = len(self.fmap)
        user = self.fmap.user_entry_count
        text = f"Feature 對照表：共 {total} 筆"
        if user:
            text += f"（其中 {user} 筆來自你匯入的 CSV）"
        else:
            text += "（內建種子檔；可匯入 CSV 補齊自家授權的代碼）"
        self.map_status_var.set(text)

    def _browse_license(self):
        path = filedialog.askopenfilename(
            title="選擇 Ansys License 檔案",
            filetypes=[("License 檔案", "*.lic *.txt"), ("所有檔案", "*.*")],
        )
        if path:
            self.lic_path_var.set(path)

    def _parse_license(self):
        path = self.lic_path_var.get().strip()
        if not path:
            messagebox.showwarning("提示", "請先選擇 License 檔案。", parent=self)
            return
        if not os.path.exists(path):
            messagebox.showerror("錯誤", f"找不到檔案：\n{path}", parent=self)
            return
        try:
            server_info, features = LicenseParser.parse(path)
        except Exception as exc:
            messagebox.showerror("解析失敗", str(exc), parent=self)
            return

        self.server_info = server_info
        self.features = self.fmap.annotate(features)
        self.license_file = path

        self.server_var.set(server_info.get("server", "（未偵測到）"))
        self.vendor_var.set(server_info.get("vendor", "（未偵測到）"))
        self._refresh_feature_tree()
        self._refresh_feature_choices()

        unmapped = sum(1 for f in self.features if not f.product)
        status = f"✔ 已解析 {os.path.basename(path)}：{len(self.features)} 個 Feature"
        if unmapped:
            status += f"；其中 {unmapped} 個找不到產品名稱（可匯入對照表 CSV 補上）"
        self.status_var.set(status)

    def _refresh_feature_tree(self):
        for row in self.feat_tree.get_children():
            self.feat_tree.delete(row)
        for entry in self.features:
            tag = "perm" if entry.expiry == "permanent" else "lease"
            self.feat_tree.insert(
                "", END,
                values=(entry.name, entry.product or "（未收錄）",
                        entry.version, entry.expiry, entry.count),
                tags=(tag,),
            )
        self.feat_tree.tag_configure("perm", foreground="#7ec8e3")
        self.feat_tree.tag_configure("lease", foreground="#f4c542")

    def _refresh_feature_choices(self):
        """建立 Feature 下拉選單，顯示產品名稱讓人看得懂在選什麼。"""
        self._feat_choices = {}
        labels = []
        for entry in self.features:
            label = entry.name
            if entry.product:
                label += f" — {entry.product}"
            label += f"  (v{entry.version}, {entry.expiry}, ×{entry.count})"
            self._feat_choices[label] = entry
            labels.append(label)
        self.feat_cb["values"] = labels
        if labels and not self.feat_var.get():
            self.feat_var.set(labels[0])
            self._on_feature_change()

    def _import_feature_map(self):
        path = filedialog.askopenfilename(
            title="選擇 Feature 對照表 CSV（欄位：feature,product[,category]）",
            filetypes=[("CSV 檔案", "*.csv"), ("所有檔案", "*.*")],
        )
        if not path:
            return
        try:
            added = self.fmap.load_csv(path)
            saved = self.fmap.save_user_csv()
        except (OSError, ValueError) as exc:
            messagebox.showerror("匯入失敗", str(exc), parent=self)
            return

        if self.features:
            self.fmap.annotate(self.features)
            self._refresh_feature_tree()
            self._refresh_feature_choices()
        self._refresh_map_status()
        messagebox.showinfo(
            "匯入完成",
            f"已匯入 {added} 筆對照資料。\n\n"
            f"已存到：\n{saved}\n（下次啟動會自動載入）",
            parent=self,
        )

    def _load_existing_opt(self):
        path = filedialog.askopenfilename(
            title="選擇既有的 ansyslmd.opt",
            filetypes=[("Options 檔案", "*.opt"), ("所有檔案", "*.*")],
        )
        if not path:
            return
        try:
            doc = OptParser.parse(path)
        except Exception as exc:
            messagebox.showerror("載入失敗", str(exc), parent=self)
            return

        if (self.groups or self.rules or self.global_opts) and not messagebox.askyesno(
            "確認載入",
            "載入會取代目前畫面上的群組與規則，未匯出的變更會遺失。要繼續嗎？",
            parent=self,
        ):
            return

        self.groups = doc.groups
        self.rules = doc.rules
        self.global_opts = doc.globals
        self.out_path_var.set(path)

        self._refresh_group_listbox()
        self._refresh_rule_tree()
        self._refresh_global_tree()
        self._update_rule_targets()

        message = (f"已載入 {len(doc.groups)} 個群組、{len(doc.rules)} 條規則、"
                   f"{len(doc.globals)} 項全域設定。")
        if doc.unknown_lines:
            preview = "\n".join(doc.unknown_lines[:8])
            message += (f"\n\n有 {len(doc.unknown_lines)} 行無法辨識，"
                        f"匯出時不會被保留：\n{preview}")
        messagebox.showinfo("載入完成", message, parent=self)
        self.status_var.set(f"✔ 已載入既有設定：{os.path.basename(path)}")

    # ─────────────────────────────────────────────────────────
    #  頁籤 2 事件
    # ─────────────────────────────────────────────────────────

    def _on_group_select(self, event=None):
        group = self._current_group()
        if not group:
            return
        self.grp_name_var.set(f"群組：{group.group_type}  {group.name}")
        self._refresh_members(group)

    def _refresh_members(self, group: Group):
        for row in self.mem_tree.get_children():
            self.mem_tree.delete(row)
        for member in group.members:
            self.mem_tree.insert("", END, values=(member,))

    def _add_group(self):
        dialog = _GroupDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        gtype, gname = dialog.result
        for group in self.groups:
            if group.group_type == gtype and group.name == gname:
                messagebox.showwarning("重複", f"群組「{gtype} {gname}」已存在。",
                                       parent=self)
                return
        self.groups.append(Group(group_type=gtype, name=gname))
        self._refresh_group_listbox()
        self._update_rule_targets()
        self.status_var.set(f"已新增群組：{gtype} {gname}")

    def _delete_group(self):
        selection = self.grp_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "請先選取要刪除的群組。", parent=self)
            return
        group = self.groups[selection[0]]
        if not messagebox.askyesno(
            "確認刪除",
            f"確定要刪除群組「{group.group_type} {group.name}」嗎？\n此操作無法復原。",
            parent=self,
        ):
            return
        self.groups.pop(selection[0])
        for row in self.mem_tree.get_children():
            self.mem_tree.delete(row)
        self.grp_name_var.set("（請選取左側群組）")
        self._refresh_group_listbox()
        self._update_rule_targets()
        self.status_var.set(f"已刪除群組：{group.group_type} {group.name}")

    def _refresh_group_listbox(self):
        self.grp_listbox.delete(0, END)
        for group in self.groups:
            self.grp_listbox.insert(
                END, f"[{group.group_type}]  {group.name}  ({len(group.members)} 人)")

    def _current_group(self) -> Optional[Group]:
        selection = self.grp_listbox.curselection()
        if not selection or selection[0] >= len(self.groups):
            return None
        return self.groups[selection[0]]

    def _add_member(self):
        group = self._current_group()
        if not group:
            messagebox.showinfo("提示", "請先在左側選取一個群組。", parent=self)
            return
        name = self.new_mem_var.get().strip()
        if not name:
            return
        warning = self._check_member_dup(group.group_type, name, exclude_group=group)
        if warning:
            messagebox.showwarning("重複成員", warning, parent=self)
            return
        if name in group.members:
            messagebox.showwarning("重複", f"「{name}」已在此群組中。", parent=self)
            return
        group.members.append(name)
        self._after_member_change(group)
        self.new_mem_var.set("")
        self.status_var.set(f"已將「{name}」加入群組 {group.name}")

    def _remove_member(self):
        group = self._current_group()
        if not group:
            return
        selection = self.mem_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "請先選取要移除的成員。", parent=self)
            return
        for item in selection:
            name = self.mem_tree.item(item, "values")[0]
            if name in group.members:
                group.members.remove(name)
        self._after_member_change(group)

    def _batch_add_members(self):
        group = self._current_group()
        if not group:
            messagebox.showinfo("提示", "請先在左側選取一個群組。", parent=self)
            return
        text = self.batch_text.get("1.0", END).strip()
        if not text:
            return
        names = [n.strip() for n in re.split(r"[\n,；，]", text) if n.strip()]
        added, skipped = [], []
        for name in names:
            warning = self._check_member_dup(group.group_type, name,
                                             exclude_group=group)
            if warning or name in group.members:
                skipped.append(name)
            else:
                group.members.append(name)
                added.append(name)
        self._after_member_change(group)
        self.batch_text.delete("1.0", END)
        message = f"已加入 {len(added)} 人。"
        if skipped:
            message += f"\n跳過重複或已存在：{', '.join(skipped)}"
        messagebox.showinfo("批次加入結果", message, parent=self)

    def _after_member_change(self, group: Group):
        self._refresh_members(group)
        self._refresh_group_listbox()
        self.grp_listbox.selection_set(self.groups.index(group))

    def _check_member_dup(self, gtype: str, name: str, exclude_group: Group) -> str:
        for group in self.groups:
            if group is exclude_group or group.group_type != gtype:
                continue
            if name in group.members:
                return (f"「{name}」已存在於同類型群組「{group.name}」中。\n"
                        f"同一成員只能屬於一個 {gtype}。")
        return ""

    # ─────────────────────────────────────────────────────────
    #  頁籤 3 事件
    # ─────────────────────────────────────────────────────────

    def _on_keyword_change(self, event=None):
        keyword = self.kw_var.get()
        spec = spec_for(keyword)

        self.feat_cb.configure(
            state="normal" if needs_feature(keyword) else "disabled")
        self.expdate_entry.configure(
            state="normal" if needs_feature(keyword) else "disabled")
        self.version_entry.configure(
            state="normal" if needs_feature(keyword) else "disabled")
        self.count_entry.configure(
            state="normal" if needs_count(keyword) else "disabled")
        self.target_type_cb.configure(
            state="readonly" if needs_target(keyword) else "disabled")
        self.target_name_cb.configure(
            state="normal" if needs_target(keyword) else "disabled")

        if spec:
            self.count_label_var.set(f"{spec.count_label}：")
            hint = spec.summary
            if spec.note:
                hint += f"　※ {spec.note}"
            self.kw_hint_var.set(hint)
            if needs_count(keyword) and not self.count_var.get().strip():
                self.count_var.set("7200" if spec.count_label == "秒數" else "1")

    def _on_feature_change(self, event=None):
        """選了 Feature 之後，同名有多份授權時自動帶入足以區分它們的修飾詞。

        同名的多份授權可能只差在版本（買了兩次，兩份都是 permanent），
        這時只有 VERSION 分得開；差在到期日的則用 EXPDATE。
        """
        entry = self._feat_choices.get(self.feat_var.get())
        if not entry:
            return
        same_name = [f for f in self.features if f.name == entry.name]
        if len(same_name) > 1 and len({f.version for f in same_name}) > 1:
            self.version_var.set(entry.version)
        else:
            self.version_var.set("")
        if len(same_name) > 1 and entry.expiry != "permanent":
            self.expdate_var.set(entry.expiry)
        else:
            self.expdate_var.set("")

    def _on_target_type_change(self, event=None):
        target_type = self.target_type_var.get()
        self.target_hint_var.set(f"對象類型說明：{TARGET_TYPES.get(target_type, '')}")
        self._update_rule_targets()

    def _update_rule_targets(self):
        target_type = self.target_type_var.get()
        if target_type in ("GROUP", "HOST_GROUP"):
            names = [g.name for g in self.groups if g.group_type == target_type]
        else:
            names = []
        self.target_name_cb["values"] = names
        if names and self.target_name_var.get() not in names:
            self.target_name_var.set(names[0])
        elif not names and target_type in ("GROUP", "HOST_GROUP"):
            self.target_name_var.set("")

    def _selected_feature_name(self) -> tuple[str, str, str]:
        """回傳 (feature, version, expdate)。

        手動輸入時允許直接打完整的 feature:VERSION=x 形式，這裡把修飾詞拆出來，
        免得整串被當成 Feature 名稱、後續檢查也對不上授權檔。
        """
        label = self.feat_var.get().strip()
        if not label:
            return "", "", ""
        entry = self._feat_choices.get(label)
        if entry:
            return entry.name, "", ""
        # 允許手動輸入沒被解析到的 Feature 名稱
        return split_feature_token(label.split()[0])

    def _add_rule(self):
        keyword = self.kw_var.get()
        feature, typed_version, typed_expdate = (
            self._selected_feature_name() if needs_feature(keyword)
            else ("", "", ""))
        # 欄位裡填的優先；沒填才採用直接打在 Feature 欄位裡的修飾詞
        version = (self.version_var.get().strip() if needs_feature(keyword)
                   else "") or typed_version
        expdate = (self.expdate_var.get().strip() if needs_feature(keyword)
                   else "") or typed_expdate
        count = self.count_var.get().strip() if needs_count(keyword) else ""
        target_type = self.target_type_var.get() if needs_target(keyword) else ""
        target_name = self.target_name_var.get().strip() if needs_target(keyword) else ""

        if needs_feature(keyword) and not feature:
            messagebox.showwarning("缺少資料", "請選擇或輸入 Feature 名稱。",
                                   parent=self)
            return
        if needs_count(keyword) and (not count.isdigit() or int(count) < 1):
            messagebox.showwarning("格式錯誤",
                                   f"{spec_for(keyword).count_label}必須為正整數。",
                                   parent=self)
            return
        if needs_target(keyword) and not target_name:
            messagebox.showwarning("缺少資料", "請輸入對象名稱。", parent=self)
            return

        self.rules.append(AccessRule(
            keyword=keyword, feature=feature, expdate=expdate, count=count,
            target_type=target_type, target_name=target_name,
            comment=self.rule_comment_var.get().strip(),
            version=version,
        ))
        self.rule_comment_var.set("")
        self._refresh_rule_tree()
        self.status_var.set(f"已新增規則：{render_rule(self.rules[-1])}")

    def _refresh_rule_tree(self):
        for row in self.rule_tree.get_children():
            self.rule_tree.delete(row)
        for rule in self.rules:
            try:
                line = render_rule(rule)
            except ValueError:
                line = f"（無法產生：{rule.keyword}）"
            self.rule_tree.insert("", END, values=(line, rule.comment))

    def _delete_rule(self):
        selection = self.rule_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "請先選取要刪除的規則。", parent=self)
            return
        for index in sorted((self.rule_tree.index(i) for i in selection),
                            reverse=True):
            if index < len(self.rules):
                self.rules.pop(index)
        self._refresh_rule_tree()
        self.status_var.set("已刪除選取規則。")

    def _on_global_change(self, event=None):
        spec = GLOBAL_SPECS.get(self.gopt_var.get(), {})
        choices = spec.get("choices", [])
        if spec.get("kind") == "onoff":
            choices = ["ON", "OFF"]
        self.gopt_value_cb["values"] = choices
        self.gopt_value_var.set(spec.get("placeholder", ""))
        hint = spec.get("summary", "")
        if spec.get("note"):
            hint += f"　※ {spec['note']}"
        self.gopt_hint_var.set(hint)

    def _add_global(self):
        keyword = self.gopt_var.get()
        value = self.gopt_value_var.get().strip()
        if not value:
            messagebox.showwarning("缺少資料", "請輸入設定值。", parent=self)
            return
        spec = GLOBAL_SPECS.get(keyword, {})
        if spec.get("kind") == "int" and not value.isdigit():
            messagebox.showwarning("格式錯誤", "這個項目的值必須是數字（秒）。",
                                   parent=self)
            return
        if spec.get("kind") == "onoff" and value.upper() not in ("ON", "OFF"):
            messagebox.showwarning("格式錯誤", "這個項目只能是 ON 或 OFF。",
                                   parent=self)
            return

        # NOLOG 可以重複多行，其餘同名項目只保留一份
        if keyword != "NOLOG":
            self.global_opts = [o for o in self.global_opts if o.keyword != keyword]
        self.global_opts.append(GlobalOption(
            keyword=keyword, value=value, comment=spec.get("summary", "")))
        self._refresh_global_tree()
        self.status_var.set(f"已設定 {keyword} {value}")

    def _quick_case_insensitive(self):
        self.gopt_var.set("GROUPCASEINSENSITIVE")
        self._on_global_change()
        self.gopt_value_var.set("ON")
        self._add_global()

    def _refresh_global_tree(self):
        for row in self.gopt_tree.get_children():
            self.gopt_tree.delete(row)
        for option in self.global_opts:
            self.gopt_tree.insert(
                "", END, values=(f"{option.keyword} {option.value}".strip(),
                                 option.comment))

    def _delete_global(self):
        selection = self.gopt_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "請先選取要刪除的設定。", parent=self)
            return
        for index in sorted((self.gopt_tree.index(i) for i in selection),
                            reverse=True):
            if index < len(self.global_opts):
                self.global_opts.pop(index)
        self._refresh_global_tree()

    # ─────────────────────────────────────────────────────────
    #  頁籤 4 事件
    # ─────────────────────────────────────────────────────────

    def _on_tab_change(self, event=None):
        if self.nb.index("current") == 3:
            self._refresh_preview()

    def _build_content(self) -> str:
        return OptGenerator.generate(
            self.groups, self.rules, self.global_opts,
            keep_comments=self.keep_comments_var.get(),
        )

    def _refresh_preview(self):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", END)
        self.preview_text.insert("1.0", self._build_content())
        self.preview_text.configure(state="disabled")
        self._run_validation()

    def _run_validation(self) -> list:
        self._issues = validate(self.groups, self.rules, self.global_opts,
                                self.features)
        for row in self.issue_tree.get_children():
            self.issue_tree.delete(row)
        label = {ERROR: "錯誤", WARNING: "警告", INFO: "提醒"}
        for issue in self._issues:
            self.issue_tree.insert(
                "", END, values=(label[issue.level], issue.message),
                tags=(issue.level,))

        errors = sum(1 for i in self._issues if i.level == ERROR)
        warnings = sum(1 for i in self._issues if i.level == WARNING)
        if not self._issues:
            self.status_var.set("✔ 檢查通過，沒有發現問題。")
        else:
            self.status_var.set(
                f"檢查結果：{errors} 個錯誤、{warnings} 個警告，"
                f"共 {len(self._issues)} 項。")
        return self._issues

    def _on_issue_select(self, event=None):
        selection = self.issue_tree.selection()
        if not selection:
            return
        index = self.issue_tree.index(selection[0])
        if index >= len(self._issues):
            return
        issue = self._issues[index]
        title = {ERROR: "錯誤", WARNING: "警告", INFO: "提醒"}[issue.level]
        messagebox.showinfo(
            f"{title}：{issue.code}",
            f"{issue.message}\n\n{issue.hint}" if issue.hint else issue.message,
            parent=self,
        )

    def _copy_preview(self):
        self.clipboard_clear()
        self.clipboard_append(self._build_content())
        self.status_var.set("✔ 已複製 opt 內容到剪貼簿。")

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="選擇輸出路徑", defaultextension=".opt",
            initialfile="ansyslmd.opt",
            filetypes=[("Options 檔案", "*.opt"), ("所有檔案", "*.*")],
        )
        if path:
            self.out_path_var.set(path)

    def _export_opt(self):
        out_path = self.out_path_var.get().strip()
        if not out_path:
            messagebox.showwarning("提示", "請設定輸出路徑。", parent=self)
            return

        if not self.groups and not self.rules and not self.global_opts:
            if not messagebox.askyesno(
                "確認匯出", "目前沒有任何設定，確定要匯出空白的 opt 檔嗎？",
                parent=self,
            ):
                return

        issues = self._run_validation()
        errors = [i for i in issues if i.level == ERROR]
        if errors:
            detail = "\n\n".join(str(e) for e in errors[:5])
            if len(errors) > 5:
                detail += f"\n\n（另有 {len(errors) - 5} 個錯誤未列出）"
            if not messagebox.askyesno(
                "檢查未通過",
                f"發現 {len(errors)} 個錯誤：\n\n{detail}\n\n"
                f"這些設定很可能不會如預期生效。仍要匯出嗎？",
                parent=self, default="no", icon="warning",
            ):
                return

        content = self._build_content()
        try:
            directory = os.path.dirname(out_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            backup = OptGenerator.export(content, out_path,
                                         backup=self.backup_var.get())
        except PermissionError:
            messagebox.showerror(
                "權限不足",
                f"無法寫入：\n{out_path}\n\n"
                f"請以系統管理員身分執行此工具，或選擇其他路徑。",
                parent=self,
            )
            return
        except OSError as exc:
            messagebox.showerror("匯出失敗", str(exc), parent=self)
            return

        message = f"✔ 已匯出至：\n{out_path}"
        if backup:
            message += f"\n\n原檔已備份為：\n{os.path.basename(backup)}"
        message += ("\n\n設定還沒生效。請用下方的 lmreread 讓 vendor daemon "
                    "重讀設定（不會中斷正在跑的工作）。")
        messagebox.showinfo("匯出成功", message, parent=self)
        self.status_var.set(f"✔ 已匯出：{out_path}")

    # ── 套用設定 ──

    def _refresh_reread_cmd(self):
        command = LmUtil.reread_command(self.lic_for_reread_var.get().strip())
        self.reread_cmd_var.set(LmUtil.quote(command))

    def _copy_reread_cmd(self):
        self.clipboard_clear()
        self.clipboard_append(self.reread_cmd_var.get())
        self.status_var.set("✔ 已複製 lmreread 指令。")

    def _run_reread(self):
        command = LmUtil.reread_command(self.lic_for_reread_var.get().strip())
        if not LmUtil.find():
            messagebox.showwarning(
                "找不到 lmutil",
                "在常見的安裝路徑下找不到 lmutil。\n\n"
                "可以用「複製指令」把指令貼到授權主機上執行，"
                "或確認 ANSYSLIC_DIR 環境變數是否正確。",
                parent=self,
            )
            return
        self.status_var.set("正在執行 lmreread…")

        def worker():
            code, output = LmUtil.run(command)
            self.after(0, lambda: self._show_reread_result(code, output))

        threading.Thread(target=worker, daemon=True).start()

    def _show_reread_result(self, code: int, output: str):
        text = output.strip() or "（沒有輸出）"
        if code == 0:
            messagebox.showinfo("lmreread 完成",
                                f"設定已重新讀取。\n\n{text}", parent=self)
            self.status_var.set("✔ lmreread 完成，設定已生效。")
        else:
            messagebox.showerror(
                "lmreread 失敗",
                f"回傳碼 {code}\n\n{text}\n\n"
                f"若這台不是授權主機，請在授權主機上執行這個指令。",
                parent=self,
            )
            self.status_var.set(f"lmreread 失敗（回傳碼 {code}）。")


# ─────────────────────────────────────────────────────────────
#  對話框
# ─────────────────────────────────────────────────────────────

class _GroupDialog(tk.Toplevel):
    """新增群組對話框"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("新增群組")
        self.resizable(False, False)
        self.result = None

        self.configure(bg="#2b2b2b")
        self.transient(parent)
        self.grab_set()

        pad = {"padx": 12, "pady": 6}

        tk.Label(self, text="群組類型：", font=("微軟正黑體", 10),
                 bg="#2b2b2b", fg="#eeeeee").grid(row=0, column=0, sticky=W, **pad)
        self.type_var = tk.StringVar(value="GROUP")
        ttk.Combobox(self, textvariable=self.type_var,
                     values=["GROUP", "HOST_GROUP"], state="readonly",
                     font=("Calibri", 10), width=16).grid(
            row=0, column=1, sticky=W, **pad)

        tk.Label(self, text="群組名稱：", font=("微軟正黑體", 10),
                 bg="#2b2b2b", fg="#eeeeee").grid(row=1, column=0, sticky=W, **pad)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(self, textvariable=self.name_var,
                               font=("Calibri", 10), width=20)
        name_entry.grid(row=1, column=1, sticky=W, **pad)
        name_entry.focus_set()

        tk.Label(self, text="建議使用英文命名，不含空白或中文。\n例如：TeamA、SI_Group",
                 font=("微軟正黑體", 9), bg="#2b2b2b", fg="#888888",
                 justify=LEFT).grid(row=2, column=0, columnspan=2, **pad)

        btn_frame = tk.Frame(self, bg="#2b2b2b")
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(4, 10))
        ttk.Button(btn_frame, text="確定", command=self._ok,
                   width=10).pack(side=LEFT, padx=6)
        ttk.Button(btn_frame, text="取消", command=self.destroy,
                   width=10).pack(side=LEFT)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        parent.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "群組名稱不能為空。", parent=self)
            return
        if re.search(r"[\s\u4e00-\u9fff]", name):
            messagebox.showwarning(
                "命名規則",
                "群組名稱不應包含空白或中文，請使用英文字母、數字與底線。",
                parent=self,
            )
            return
        self.result = (self.type_var.get(), name)
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
