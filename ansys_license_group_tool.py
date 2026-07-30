# -*- coding: utf-8 -*-
"""
Ansys License 分組設定 GUI 工具
此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供

依據：Ansys_License_分組設定_SOP.md
功能：協助使用者透過圖形介面完成 ansyslmd.opt 分組設定
"""

import re
import os
import shutil
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from dataclasses import dataclass, field
from typing import Optional
import ttkbootstrap as tbs
from ttkbootstrap.constants import *


# ─────────────────────────────────────────────────────────────
#  資料結構
# ─────────────────────────────────────────────────────────────

@dataclass
class FeatureEntry:
    """授權 Feature 條目"""
    name: str
    version: str
    expiry: str          # "permanent" 或 "31-oct-2026"
    count: int
    issued: str = ""     # ISSUED= 值，用於 EXPDATE 語法


@dataclass
class Group:
    """使用者群組或主機群組"""
    group_type: str      # "GROUP" 或 "HOST_GROUP"
    name: str
    members: list[str] = field(default_factory=list)


@dataclass
class AccessRule:
    """存取規則條目"""
    keyword: str         # RESERVE / MAX / INCLUDE / INCLUDEALL / EXCLUDE / EXCLUDEALL
    feature: str         # Feature 名稱（INCLUDEALL / EXCLUDEALL 時為空）
    expdate: str         # 附加 :EXPDATE=日期（可空）
    count: str           # 數量（僅 RESERVE / MAX 需要）
    target_type: str     # "GROUP" / "HOST_GROUP" / "USER" / "HOST"
    target_name: str     # 群組名稱 / 使用者 / 主機名稱
    comment: str = ""    # 註解


# ─────────────────────────────────────────────────────────────
#  License 解析器
# ─────────────────────────────────────────────────────────────

class LicenseParser:
    """解析 Ansys License 檔案，擷取 Feature / INCREMENT 資訊"""

    @staticmethod
    def parse(filepath: str) -> tuple[dict, list[FeatureEntry]]:
        """
        回傳 (server_info, features)
        server_info: {"server": ..., "vendor": ...}
        features: List[FeatureEntry]
        """
        server_info = {}
        features: list[FeatureEntry] = []
        feature_groups: dict[tuple[str, str], list[FeatureEntry]] = {}

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            raise IOError(f"無法讀取檔案：{e}")

        # 解析 SERVER 行
        m = re.search(r"^SERVER\s+(\S+)", content, re.MULTILINE)
        if m:
            server_info["server"] = m.group(1)

        # 解析 VENDOR 行
        m = re.search(r"^VENDOR\s+(\S+)", content, re.MULTILINE)
        if m:
            server_info["vendor"] = m.group(1)

        # 將多行合併（行末 \ 繼續）
        joined = re.sub(r"\\\s*\n\s*", " ", content)

        # 解析 INCREMENT / FEATURE 行
        pattern = re.compile(
            r"^(?:INCREMENT|FEATURE)\s+(\S+)\s+\S+\s+(\S+)\s+(\S+)\s+(\d+)",
            re.MULTILINE
        )
        issued_pattern = re.compile(r"ISSUED=(\S+)")

        for m in pattern.finditer(joined):
            name = m.group(1)
            version = m.group(2)
            expiry = m.group(3)
            count = int(m.group(4))

            # 擷取 ISSUED
            line_rest = joined[m.start():m.start() + 500]
            issued_m = issued_pattern.search(line_rest)
            issued = issued_m.group(1) if issued_m else ""

            # permanent 標準化
            if expiry.lower() == "permanent":
                expiry = "permanent"

            fe = FeatureEntry(name=name, version=version,
                              expiry=expiry, count=count, issued=issued)

            key = (name, expiry)
            if key not in feature_groups:
                feature_groups[key] = []
            feature_groups[key].append(fe)

        # 彙整：相同 name+expiry 的數量加總
        seen: dict[tuple[str, str], FeatureEntry] = {}
        for (name, expiry), entries in feature_groups.items():
            total = sum(e.count for e in entries)
            fe = FeatureEntry(
                name=name, version=entries[0].version,
                expiry=expiry, count=total,
                issued=entries[0].issued
            )
            seen[(name, expiry)] = fe

        features = sorted(seen.values(), key=lambda x: x.name)
        return server_info, features


# ─────────────────────────────────────────────────────────────
#  Opt 產生器
# ─────────────────────────────────────────────────────────────

class OptGenerator:
    """將群組與規則資料產生 ansyslmd.opt 文字"""

    @staticmethod
    def generate(groups: list[Group], rules: list[AccessRule],
                 extra_comment: str = "") -> str:
        lines = []

        # 群組定義
        if groups:
            for g in groups:
                members_str = " ".join(g.members)
                lines.append(f"{g.group_type} {g.name} {members_str}")
            lines.append("")

        # 存取規則
        if rules:
            for r in rules:
                feature_part = r.feature
                if r.expdate:
                    feature_part += f":EXPDATE={r.expdate}"

                if r.keyword in ("RESERVE", "MAX"):
                    lines.append(
                        f"{r.keyword} {r.count} {feature_part} {r.target_type} {r.target_name}"
                    )
                elif r.keyword in ("INCLUDEALL", "EXCLUDEALL"):
                    lines.append(
                        f"{r.keyword} {r.target_type} {r.target_name}"
                    )
                else:
                    lines.append(
                        f"{r.keyword} {feature_part} {r.target_type} {r.target_name}"
                    )
        return "\n".join(lines)


    @staticmethod
    def export(content: str, filepath: str, backup: bool = True):
        """匯出 opt 檔，若已存在則先備份"""
        if backup and os.path.exists(filepath):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = filepath + f".bak_{ts}"
            shutil.copy2(filepath, backup_path)

        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)


# ─────────────────────────────────────────────────────────────
#  主視窗 App
# ─────────────────────────────────────────────────────────────

class App(tbs.Window):

    FONT_TITLE = ("微軟正黑體", 14, "bold")
    FONT_LABEL = ("微軟正黑體", 10)
    FONT_BOLD  = ("微軟正黑體", 10, "bold")
    FONT_SMALL = ("微軟正黑體", 9)
    FONT_MONO  = ("Calibri", 10)

    def __init__(self):
        super().__init__(
            title="Ansys License 分組設定工具",
            themename="darkly",
            size=(1050, 720),
        )
        self.resizable(True, True)
        self.minsize(900, 620)

        # 資料狀態
        self.features: list[FeatureEntry] = []
        self.server_info: dict = {}
        self.groups: list[Group] = []
        self.rules: list[AccessRule] = []
        self.license_file: str = ""

        self._build_ui()
        self.center_window()

    def center_window(self):
        self.update_idletasks()
        w, h = 1050, 720
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI 建構 ─────────────────────────────────────────────

    def _build_ui(self):
        # 頂部標題列
        header = tbs.Frame(self, bootstyle="dark", padding=(16, 10))
        header.pack(fill=X)

        tbs.Label(
            header,
            text="Ansys License 分組設定工具",
            font=("微軟正黑體", 15, "bold"),
            bootstyle="light",
        ).pack(side=LEFT)

        tbs.Label(
            header,
            text="此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供",
            font=self.FONT_SMALL,
            bootstyle="secondary",
        ).pack(side=RIGHT, padx=8)

        # Notebook（四頁籤）
        self.nb = tbs.Notebook(self, bootstyle="dark")
        self.nb.pack(fill=BOTH, expand=True, padx=12, pady=8)

        self._build_tab1_load()
        self._build_tab2_groups()
        self._build_tab3_rules()
        self._build_tab4_export()

        # 底部狀態列
        self.status_var = tk.StringVar(value="就緒。請從「步驟 1」載入授權檔案。")
        status_bar = tbs.Label(
            self, textvariable=self.status_var,
            font=self.FONT_SMALL, bootstyle="secondary",
            anchor=W, padding=(12, 4)
        )
        status_bar.pack(fill=X, side=BOTTOM)

    # ── 頁籤 1：載入授權檔案 ────────────────────────────────

    def _build_tab1_load(self):
        tab = tbs.Frame(self.nb, padding=16)
        self.nb.add(tab, text="  步驟 1｜載入授權檔案  ")

        # 說明
        tbs.Label(tab, text="步驟 1：選擇 Ansys License 檔案",
                  font=self.FONT_TITLE, bootstyle="info").pack(anchor=W, pady=(0, 4))
        tbs.Label(
            tab,
            text="支援 .lic 與 .txt 格式。工具將自動解析所有 Feature 名稱、到期日與授權數量。",
            font=self.FONT_SMALL, bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 12))
        tbs.Separator(tab, bootstyle="secondary").pack(fill=X, pady=(0, 12))

        # 選擇檔案列
        file_row = tbs.Frame(tab)
        file_row.pack(fill=X, pady=(0, 8))

        tbs.Label(file_row, text="授權檔案：", font=self.FONT_LABEL).pack(side=LEFT)
        self.lic_path_var = tk.StringVar()
        tbs.Entry(
            file_row, textvariable=self.lic_path_var,
            font=self.FONT_MONO, width=60
        ).pack(side=LEFT, padx=(4, 8), fill=X, expand=True)

        tbs.Button(
            file_row, text="瀏覽…", bootstyle="outline-info",
            command=self._browse_license, width=8
        ).pack(side=LEFT, padx=(0, 4))

        tbs.Button(
            file_row, text="解析", bootstyle="success",
            command=self._parse_license, width=8
        ).pack(side=LEFT)

        # Server 資訊
        info_frame = tbs.LabelFrame(tab, text=" 授權伺服器資訊 ", padding=10,
                                     bootstyle="info")
        info_frame.pack(fill=X, pady=(0, 12))

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

        cols = ("feature", "version", "expiry", "count")
        self.feat_tree = tbs.Treeview(
            feat_frame, columns=cols, show="headings",
            bootstyle="info", height=12
        )
        for col, hdr, w in [
            ("feature", "Feature 名稱", 220),
            ("version", "版本", 110),
            ("expiry", "到期日", 140),
            ("count", "授權數量", 90),
        ]:
            self.feat_tree.heading(col, text=hdr)
            self.feat_tree.column(col, width=w, anchor=W)

        scrolly = tbs.Scrollbar(feat_frame, orient=VERTICAL,
                                 command=self.feat_tree.yview, bootstyle="info-round")
        self.feat_tree.configure(yscrollcommand=scrolly.set)

        self.feat_tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrolly.pack(side=RIGHT, fill=Y)

        tbs.Label(
            tab,
            text="💡 提示：解析完成後，Feature 清單可在步驟 3「存取規則」中直接選用。",
            font=self.FONT_SMALL, bootstyle="warning"
        ).pack(anchor=W, pady=(8, 0))

    # ── 頁籤 2：群組管理 ────────────────────────────────────

    def _build_tab2_groups(self):
        tab = tbs.Frame(self.nb, padding=16)
        self.nb.add(tab, text="  步驟 2｜群組管理  ")

        tbs.Label(tab, text="步驟 2：建立使用者群組 / 主機群組",
                  font=self.FONT_TITLE, bootstyle="warning").pack(anchor=W, pady=(0, 4))
        tbs.Label(
            tab,
            text="GROUP：依登入帳號分組 ｜ HOST_GROUP：依電腦名稱分組（注意大小寫）",
            font=self.FONT_SMALL, bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 12))
        tbs.Separator(tab, bootstyle="secondary").pack(fill=X, pady=(0, 12))

        # 主體左右分割
        paned = tbs.Panedwindow(tab, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        # ── 左側：群組列表 ──
        left = tbs.Frame(paned, padding=(0, 0, 8, 0))
        paned.add(left, weight=1)

        tbs.Label(left, text="群組列表", font=self.FONT_BOLD,
                  bootstyle="warning").pack(anchor=W, pady=(0, 6))

        self.grp_listbox = tk.Listbox(
            left, font=self.FONT_MONO, height=16,
            bg="#2b2b2b", fg="#eeeeee", selectbackground="#F4A21A",
            selectforeground="#1a1a1a", activestyle="none",
            relief="flat", borderwidth=1
        )
        self.grp_listbox.pack(fill=BOTH, expand=True)
        self.grp_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        btn_row = tbs.Frame(left)
        btn_row.pack(fill=X, pady=(6, 0))

        tbs.Button(
            btn_row, text="＋ 新增群組", bootstyle="warning-outline",
            command=self._add_group, width=12
        ).pack(side=LEFT, padx=(0, 4))
        tbs.Button(
            btn_row, text="✕ 刪除群組", bootstyle="danger-outline",
            command=self._delete_group, width=12
        ).pack(side=LEFT)

        # ── 右側：成員管理 ──
        right = tbs.Frame(paned, padding=(8, 0, 0, 0))
        paned.add(right, weight=2)

        self.grp_name_var = tk.StringVar(value="（請選取左側群組）")
        tbs.Label(right, textvariable=self.grp_name_var,
                  font=self.FONT_BOLD, bootstyle="warning").pack(anchor=W, pady=(0, 6))

        # 成員 Treeview
        mem_frame = tbs.Frame(right)
        mem_frame.pack(fill=BOTH, expand=True)

        self.mem_tree = tbs.Treeview(
            mem_frame, columns=("member",), show="headings",
            bootstyle="warning", height=14
        )
        self.mem_tree.heading("member", text="成員名稱（使用者帳號 / 主機名稱）")
        self.mem_tree.column("member", width=300, anchor=W)

        mem_scroll = tbs.Scrollbar(mem_frame, orient=VERTICAL,
                                    command=self.mem_tree.yview, bootstyle="warning-round")
        self.mem_tree.configure(yscrollcommand=mem_scroll.set)
        self.mem_tree.pack(side=LEFT, fill=BOTH, expand=True)
        mem_scroll.pack(side=RIGHT, fill=Y)

        # 新增成員
        add_mem_frame = tbs.Frame(right)
        add_mem_frame.pack(fill=X, pady=(6, 0))

        tbs.Label(add_mem_frame, text="新成員名稱：",
                  font=self.FONT_LABEL).pack(side=LEFT)
        self.new_mem_var = tk.StringVar()
        mem_entry = tbs.Entry(
            add_mem_frame, textvariable=self.new_mem_var,
            font=self.FONT_MONO, width=28
        )
        mem_entry.pack(side=LEFT, padx=(4, 8))
        mem_entry.bind("<Return>", lambda e: self._add_member())

        tbs.Button(
            add_mem_frame, text="加入", bootstyle="warning",
            command=self._add_member, width=8
        ).pack(side=LEFT, padx=(0, 4))
        tbs.Button(
            add_mem_frame, text="移除選取", bootstyle="danger-outline",
            command=self._remove_member, width=10
        ).pack(side=LEFT)

        # 批次輸入
        batch_frame = tbs.LabelFrame(right, text=" 批次輸入成員（每行一個名稱）",
                                      padding=8, bootstyle="warning")
        batch_frame.pack(fill=X, pady=(8, 0))

        self.batch_text = tk.Text(
            batch_frame, height=4, font=self.FONT_MONO,
            bg="#2b2b2b", fg="#eeeeee", insertbackground="white",
            relief="flat"
        )
        self.batch_text.pack(fill=X, pady=(0, 4))
        tbs.Button(
            batch_frame, text="批次加入", bootstyle="warning-outline",
            command=self._batch_add_members
        ).pack(anchor=E)

        tbs.Label(
            right,
            text="⚠ 注意：同一個使用者只能屬於一個 GROUP，同一台主機只能屬於一個 HOST_GROUP。",
            font=self.FONT_SMALL, bootstyle="danger"
        ).pack(anchor=W, pady=(6, 0))

    # ── 頁籤 3：存取規則 ────────────────────────────────────

    def _build_tab3_rules(self):
        tab = tbs.Frame(self.nb, padding=16)
        self.nb.add(tab, text="  步驟 3｜存取規則  ")

        tbs.Label(tab, text="步驟 3：設定存取規則",
                  font=self.FONT_TITLE, bootstyle="success").pack(anchor=W, pady=(0, 4))
        tbs.Label(
            tab,
            text="選擇規則關鍵字、目標 Feature 與群組/使用者，產生對應的 opt 語法。",
            font=self.FONT_SMALL, bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 8))
        tbs.Separator(tab, bootstyle="secondary").pack(fill=X, pady=(0, 10))

        # 新增規則面板
        rule_panel = tbs.LabelFrame(tab, text=" 新增規則 ", padding=12, bootstyle="success")
        rule_panel.pack(fill=X, pady=(0, 10))

        # 第一列：關鍵字 / Feature / EXPDATE
        row1 = tbs.Frame(rule_panel)
        row1.pack(fill=X, pady=(0, 6))

        tbs.Label(row1, text="規則關鍵字：", font=self.FONT_LABEL).pack(side=LEFT)
        self.kw_var = tk.StringVar(value="RESERVE")
        kw_cb = tbs.Combobox(
            row1, textvariable=self.kw_var, state="readonly",
            values=["RESERVE", "MAX", "INCLUDE", "INCLUDEALL", "EXCLUDE", "EXCLUDEALL"],
            width=14, font=self.FONT_MONO, bootstyle="success"
        )
        kw_cb.pack(side=LEFT, padx=(4, 16))
        kw_cb.bind("<<ComboboxSelected>>", self._on_keyword_change)

        tbs.Label(row1, text="Feature：", font=self.FONT_LABEL).pack(side=LEFT)
        self.feat_var = tk.StringVar()
        self.feat_cb = tbs.Combobox(
            row1, textvariable=self.feat_var, state="readonly",
            values=[], width=26, font=self.FONT_MONO, bootstyle="success"
        )
        self.feat_cb.pack(side=LEFT, padx=(4, 16))

        tbs.Label(row1, text=":EXPDATE=", font=self.FONT_LABEL).pack(side=LEFT)
        self.expdate_var = tk.StringVar()
        tbs.Entry(
            row1, textvariable=self.expdate_var,
            font=self.FONT_MONO, width=14
        ).pack(side=LEFT, padx=(2, 4))
        tbs.Label(row1, text="（選填，例：31-oct-2026）",
                  font=self.FONT_SMALL, bootstyle="secondary").pack(side=LEFT)

        # 第二列：數量 / 目標類型 / 目標名稱
        row2 = tbs.Frame(rule_panel)
        row2.pack(fill=X, pady=(0, 6))

        self.count_label = tbs.Label(row2, text="數量：", font=self.FONT_LABEL)
        self.count_label.pack(side=LEFT)
        self.count_var = tk.StringVar(value="1")
        self.count_entry = tbs.Entry(
            row2, textvariable=self.count_var,
            font=self.FONT_MONO, width=6
        )
        self.count_entry.pack(side=LEFT, padx=(4, 16))

        tbs.Label(row2, text="目標類型：", font=self.FONT_LABEL).pack(side=LEFT)
        self.target_type_var = tk.StringVar(value="GROUP")
        tbs.Combobox(
            row2, textvariable=self.target_type_var, state="readonly",
            values=["GROUP", "HOST_GROUP", "USER", "HOST"],
            width=12, font=self.FONT_MONO, bootstyle="success"
        ).pack(side=LEFT, padx=(4, 16))

        tbs.Label(row2, text="目標名稱：", font=self.FONT_LABEL).pack(side=LEFT)
        self.target_name_var = tk.StringVar()
        self.target_name_cb = tbs.Combobox(
            row2, textvariable=self.target_name_var,
            values=[], width=20, font=self.FONT_MONO, bootstyle="success"
        )
        self.target_name_cb.pack(side=LEFT, padx=(4, 16))

        tbs.Label(row2, text="說明/註解（選填）：", font=self.FONT_LABEL).pack(side=LEFT)
        self.rule_comment_var = tk.StringVar()
        tbs.Entry(
            row2, textvariable=self.rule_comment_var,
            font=self.FONT_MONO, width=22
        ).pack(side=LEFT, padx=(4, 0))

        # 新增按鈕
        tbs.Button(
            rule_panel, text="  ＋ 加入規則  ", bootstyle="success",
            command=self._add_rule
        ).pack(anchor=E, pady=(4, 0))

        # 規則列表
        list_frame = tbs.LabelFrame(tab, text=" 目前規則清單 ", padding=10, bootstyle="success")
        list_frame.pack(fill=BOTH, expand=True, pady=(0, 8))

        rule_cols = ("keyword", "feature", "expdate", "count", "target", "comment")
        self.rule_tree = tbs.Treeview(
            list_frame, columns=rule_cols, show="headings",
            bootstyle="success", height=10
        )
        for col, hdr, w in [
            ("keyword", "關鍵字", 110),
            ("feature", "Feature", 190),
            ("expdate", "EXPDATE", 120),
            ("count", "數量", 60),
            ("target", "目標", 170),
            ("comment", "說明", 160),
        ]:
            self.rule_tree.heading(col, text=hdr)
            self.rule_tree.column(col, width=w, anchor=W)

        rule_scrolly = tbs.Scrollbar(list_frame, orient=VERTICAL,
                                      command=self.rule_tree.yview, bootstyle="success-round")
        self.rule_tree.configure(yscrollcommand=rule_scrolly.set)
        self.rule_tree.pack(side=LEFT, fill=BOTH, expand=True)
        rule_scrolly.pack(side=RIGHT, fill=Y)

        btn_row = tbs.Frame(tab)
        btn_row.pack(fill=X)
        tbs.Button(
            btn_row, text="✕ 刪除選取規則", bootstyle="danger-outline",
            command=self._delete_rule
        ).pack(side=LEFT)

        tbs.Label(
            btn_row,
            text="💡 EXCLUDE 與 INCLUDE 衝突時，EXCLUDE 優先生效。",
            font=self.FONT_SMALL, bootstyle="warning"
        ).pack(side=RIGHT)

    # ── 頁籤 4：匯出 ────────────────────────────────────────

    def _build_tab4_export(self):
        tab = tbs.Frame(self.nb, padding=16)
        self.nb.add(tab, text="  步驟 4｜匯出 Opt 檔  ")

        tbs.Label(tab, text="步驟 4：匯出 ansyslmd.opt 設定檔",
                  font=self.FONT_TITLE, bootstyle="danger").pack(anchor=W, pady=(0, 4))
        tbs.Label(
            tab,
            text="產生 ansyslmd.opt 並儲存至指定路徑。完成後需重啟 License Manager 讓設定生效。",
            font=self.FONT_SMALL, bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 12))
        tbs.Separator(tab, bootstyle="secondary").pack(fill=X, pady=(0, 12))

        # 輸出設定
        cfg_frame = tbs.LabelFrame(tab, text=" 輸出設定 ", padding=12, bootstyle="danger")
        cfg_frame.pack(fill=X, pady=(0, 12))

        out_row = tbs.Frame(cfg_frame)
        out_row.pack(fill=X, pady=(0, 8))

        tbs.Label(out_row, text="輸出路徑：", font=self.FONT_LABEL).pack(side=LEFT)
        self.out_path_var = tk.StringVar(
            value=r"C:\Program Files\ANSYS Inc\Shared Files\Licensing\license_files\ansyslmd.opt"
        )
        tbs.Entry(
            out_row, textvariable=self.out_path_var,
            font=self.FONT_MONO, width=60
        ).pack(side=LEFT, padx=(4, 8), fill=X, expand=True)
        tbs.Button(
            out_row, text="瀏覽…", bootstyle="outline-danger",
            command=self._browse_output, width=8
        ).pack(side=LEFT)

        opt_row = tbs.Frame(cfg_frame)
        opt_row.pack(fill=X)

        self.backup_var = tk.BooleanVar(value=True)
        tbs.Checkbutton(
            opt_row, text="自動備份現有 opt 檔（加上 _bak_日期時間 後綴）",
            variable=self.backup_var, bootstyle="danger"
        ).pack(side=LEFT)

        # 預覽區
        preview_frame = tbs.LabelFrame(tab, text=" 即時預覽（opt 檔內容）",
                                        padding=10, bootstyle="danger")
        preview_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        self.preview_text = tk.Text(
            preview_frame, font=("Calibri", 10),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
            relief="flat", state="disabled", wrap="none"
        )
        scr_y = tbs.Scrollbar(preview_frame, orient=VERTICAL,
                               command=self.preview_text.yview, bootstyle="danger-round")
        scr_x = tbs.Scrollbar(preview_frame, orient=HORIZONTAL,
                               command=self.preview_text.xview, bootstyle="danger-round")
        self.preview_text.configure(
            yscrollcommand=scr_y.set,
            xscrollcommand=scr_x.set
        )
        scr_y.pack(side=RIGHT, fill=Y)
        scr_x.pack(side=BOTTOM, fill=X)
        self.preview_text.pack(fill=BOTH, expand=True)

        # 按鈕列
        btn_row = tbs.Frame(tab)
        btn_row.pack(fill=X)

        tbs.Button(
            btn_row, text="🔄 重新整理預覽", bootstyle="outline-danger",
            command=self._refresh_preview, width=16
        ).pack(side=LEFT, padx=(0, 8))

        tbs.Button(
            btn_row, text="📋 複製到剪貼簿", bootstyle="outline-info",
            command=self._copy_preview, width=16
        ).pack(side=LEFT, padx=(0, 8))

        tbs.Button(
            btn_row, text="💾  匯出 Opt 檔", bootstyle="danger",
            command=self._export_opt, width=16
        ).pack(side=RIGHT)

        # 重啟提醒
        remind_frame = tbs.LabelFrame(tab, text=" ⚠ 重啟 License Manager 步驟（Windows）",
                                       padding=10, bootstyle="warning")
        remind_frame.pack(fill=X, pady=(10, 0))

        remind_text = (
            "1. 以系統管理員身分開啟「Ansys License Management Center」\n"
            "2. 進入 View Status/Start/Stop License Manager\n"
            "3. 按 STOP，等待數秒後再按 START\n"
            "4. 確認狀態顯示為 Running"
        )
        tbs.Label(
            remind_frame, text=remind_text,
            font=self.FONT_SMALL, bootstyle="warning", justify=LEFT
        ).pack(anchor=W)

        # 頁籤切換時自動重新整理
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

    # ─────────────────────────────────────────────────────────
    #  事件處理 — 頁籤 1
    # ─────────────────────────────────────────────────────────

    def _browse_license(self):
        fp = filedialog.askopenfilename(
            title="選擇 Ansys License 檔案",
            filetypes=[("License 檔案", "*.lic *.txt"), ("所有檔案", "*.*")]
        )
        if fp:
            self.lic_path_var.set(fp)

    def _parse_license(self):
        fp = self.lic_path_var.get().strip()
        if not fp:
            messagebox.showwarning("提示", "請先選擇 License 檔案。", parent=self)
            return
        if not os.path.exists(fp):
            messagebox.showerror("錯誤", f"找不到檔案：\n{fp}", parent=self)
            return

        try:
            server_info, features = LicenseParser.parse(fp)
        except Exception as e:
            messagebox.showerror("解析失敗", str(e), parent=self)
            return

        self.server_info = server_info
        self.features = features
        self.license_file = fp

        self.server_var.set(server_info.get("server", "（未偵測到）"))
        self.vendor_var.set(server_info.get("vendor", "（未偵測到）"))

        # 更新 Treeview
        for row in self.feat_tree.get_children():
            self.feat_tree.delete(row)
        for fe in features:
            tag = "perm" if fe.expiry == "permanent" else "lease"
            self.feat_tree.insert(
                "", END,
                values=(fe.name, fe.version, fe.expiry, fe.count),
                tags=(tag,)
            )
        self.feat_tree.tag_configure("perm", foreground="#7ec8e3")
        self.feat_tree.tag_configure("lease", foreground="#f4c542")

        # 更新步驟 3 Feature 下拉
        feat_names = [f"{fe.name}  ({fe.expiry}, ×{fe.count})" for fe in features]
        self.feat_cb["values"] = feat_names
        if feat_names:
            self.feat_var.set(feat_names[0])

        self.status_var.set(
            f"✔ 已解析：{os.path.basename(fp)} — 共 {len(features)} 個 Feature 條目"
        )

    # ─────────────────────────────────────────────────────────
    #  事件處理 — 頁籤 2
    # ─────────────────────────────────────────────────────────

    def _on_group_select(self, event=None):
        sel = self.grp_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.groups):
            return
        g = self.groups[idx]
        self.grp_name_var.set(f"群組：{g.group_type}  {g.name}")
        self._refresh_members(g)

    def _refresh_members(self, group: Group):
        for row in self.mem_tree.get_children():
            self.mem_tree.delete(row)
        for m in group.members:
            self.mem_tree.insert("", END, values=(m,))

    def _add_group(self):
        dlg = _GroupDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        gtype, gname = dlg.result
        # 名稱重複檢查
        for g in self.groups:
            if g.group_type == gtype and g.name == gname:
                messagebox.showwarning("重複", f"群組「{gtype} {gname}」已存在。", parent=self)
                return
        self.groups.append(Group(group_type=gtype, name=gname))
        self._refresh_group_listbox()
        self._update_rule_targets()
        self.status_var.set(f"已新增群組：{gtype} {gname}")

    def _delete_group(self):
        sel = self.grp_listbox.curselection()
        if not sel:
            messagebox.showinfo("提示", "請先選取要刪除的群組。", parent=self)
            return
        idx = sel[0]
        g = self.groups[idx]
        if not messagebox.askyesno(
            "確認刪除",
            f"確定要刪除群組「{g.group_type} {g.name}」嗎？\n此操作無法復原。",
            parent=self
        ):
            return
        self.groups.pop(idx)
        for row in self.mem_tree.get_children():
            self.mem_tree.delete(row)
        self.grp_name_var.set("（請選取左側群組）")
        self._refresh_group_listbox()
        self._update_rule_targets()
        self.status_var.set(f"已刪除群組：{g.group_type} {g.name}")

    def _refresh_group_listbox(self):
        self.grp_listbox.delete(0, END)
        for g in self.groups:
            self.grp_listbox.insert(END, f"[{g.group_type}]  {g.name}  ({len(g.members)} 人)")

    def _current_group(self) -> Optional[Group]:
        sel = self.grp_listbox.curselection()
        if not sel or sel[0] >= len(self.groups):
            return None
        return self.groups[sel[0]]

    def _add_member(self):
        g = self._current_group()
        if not g:
            messagebox.showinfo("提示", "請先在左側選取一個群組。", parent=self)
            return
        name = self.new_mem_var.get().strip()
        if not name:
            return
        # 重複成員檢查（同類型群組間）
        warn = self._check_member_dup(g.group_type, name, exclude_group=g)
        if warn:
            messagebox.showwarning("重複成員", warn, parent=self)
            return
        if name in g.members:
            messagebox.showwarning("重複", f"「{name}」已在此群組中。", parent=self)
            return
        g.members.append(name)
        self._refresh_members(g)
        self._refresh_group_listbox()
        # 保持選取
        idx = self.groups.index(g)
        self.grp_listbox.selection_set(idx)
        self.new_mem_var.set("")
        self.status_var.set(f"已將「{name}」加入群組 {g.name}")

    def _remove_member(self):
        g = self._current_group()
        if not g:
            return
        sel = self.mem_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "請先選取要移除的成員。", parent=self)
            return
        for item in sel:
            name = self.mem_tree.item(item, "values")[0]
            if name in g.members:
                g.members.remove(name)
        self._refresh_members(g)
        self._refresh_group_listbox()
        idx = self.groups.index(g)
        self.grp_listbox.selection_set(idx)

    def _batch_add_members(self):
        g = self._current_group()
        if not g:
            messagebox.showinfo("提示", "請先在左側選取一個群組。", parent=self)
            return
        text = self.batch_text.get("1.0", END).strip()
        if not text:
            return
        names = [n.strip() for n in re.split(r"[\n,；，]", text) if n.strip()]
        added, skipped = [], []
        for name in names:
            warn = self._check_member_dup(g.group_type, name, exclude_group=g)
            if warn or name in g.members:
                skipped.append(name)
            else:
                g.members.append(name)
                added.append(name)
        self._refresh_members(g)
        self._refresh_group_listbox()
        idx = self.groups.index(g)
        self.grp_listbox.selection_set(idx)
        self.batch_text.delete("1.0", END)
        msg = f"已加入 {len(added)} 人。"
        if skipped:
            msg += f"\n跳過重複或已存在：{', '.join(skipped)}"
        messagebox.showinfo("批次加入結果", msg, parent=self)

    def _check_member_dup(self, gtype: str, name: str, exclude_group: Group) -> str:
        """檢查是否在同型別其他群組中已有此成員"""
        for g in self.groups:
            if g is exclude_group:
                continue
            if g.group_type != gtype:
                continue
            if name in g.members:
                return (
                    f"「{name}」已存在於同類型群組「{g.name}」中。\n"
                    f"依 SOP 規定，同一成員只能屬於一個 {gtype}。"
                )
        return ""

    # ─────────────────────────────────────────────────────────
    #  事件處理 — 頁籤 3
    # ─────────────────────────────────────────────────────────

    def _on_keyword_change(self, event=None):
        kw = self.kw_var.get()
        # INCLUDEALL / EXCLUDEALL 不需要 Feature 和數量
        needs_feature = kw not in ("INCLUDEALL", "EXCLUDEALL")
        needs_count = kw in ("RESERVE", "MAX")

        self.feat_cb.configure(state="readonly" if needs_feature else "disabled")
        self.count_entry.configure(state="normal" if needs_count else "disabled")
        if not needs_count:
            self.count_var.set("")

    def _update_rule_targets(self):
        """更新步驟 3 的目標名稱下拉選單"""
        names = [g.name for g in self.groups]
        self.target_name_cb["values"] = names
        if names and not self.target_name_var.get():
            self.target_name_var.set(names[0])

    def _add_rule(self):
        kw = self.kw_var.get()
        raw_feat = self.feat_var.get().strip()
        # 取 Feature 名稱（去掉後面的括號說明）
        feat_name = raw_feat.split()[0] if raw_feat else ""
        expdate = self.expdate_var.get().strip()
        count = self.count_var.get().strip()
        ttype = self.target_type_var.get()
        tname = self.target_name_var.get().strip()
        comment = self.rule_comment_var.get().strip()

        # 驗證
        if kw in ("RESERVE", "MAX"):
            if not feat_name:
                messagebox.showwarning("缺少資料", "請選擇 Feature。", parent=self)
                return
            if not count.isdigit() or int(count) < 1:
                messagebox.showwarning("格式錯誤", "數量必須為正整數。", parent=self)
                return
        elif kw in ("INCLUDE", "EXCLUDE"):
            if not feat_name:
                messagebox.showwarning("缺少資料", "請選擇 Feature。", parent=self)
                return

        if not tname:
            messagebox.showwarning("缺少資料", "請輸入目標名稱（群組/使用者/主機）。", parent=self)
            return

        rule = AccessRule(
            keyword=kw, feature=feat_name, expdate=expdate,
            count=count, target_type=ttype, target_name=tname,
            comment=comment
        )
        self.rules.append(rule)

        # 顯示在列表
        feat_disp = feat_name
        if expdate:
            feat_disp += f":{expdate}"
        target_disp = f"{ttype} {tname}"
        self.rule_tree.insert(
            "", END,
            values=(kw, feat_name, expdate, count, target_disp, comment)
        )
        self.status_var.set(f"已新增規則：{kw} {feat_disp} {target_disp}")

    def _delete_rule(self):
        sel = self.rule_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "請先選取要刪除的規則。", parent=self)
            return
        for item in sel:
            idx = self.rule_tree.index(item)
            if idx < len(self.rules):
                self.rules.pop(idx)
            self.rule_tree.delete(item)
        self.status_var.set("已刪除選取規則。")

    # ─────────────────────────────────────────────────────────
    #  事件處理 — 頁籤 4
    # ─────────────────────────────────────────────────────────

    def _on_tab_change(self, event=None):
        tab_idx = self.nb.index("current")
        if tab_idx == 3:  # 步驟 4
            self._refresh_preview()
            self._update_rule_targets()

    def _refresh_preview(self):
        content = OptGenerator.generate(self.groups, self.rules)
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", END)
        self.preview_text.insert("1.0", content)
        self.preview_text.configure(state="disabled")

    def _copy_preview(self):
        content = self.preview_text.get("1.0", END)
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set("✔ 已複製 opt 內容到剪貼簿。")

    def _browse_output(self):
        fp = filedialog.asksaveasfilename(
            title="選擇輸出路徑",
            defaultextension=".opt",
            initialfile="ansyslmd.opt",
            filetypes=[("Options 檔案", "*.opt"), ("所有檔案", "*.*")]
        )
        if fp:
            self.out_path_var.set(fp)

    def _export_opt(self):
        out_path = self.out_path_var.get().strip()
        if not out_path:
            messagebox.showwarning("提示", "請設定輸出路徑。", parent=self)
            return

        if not self.groups and not self.rules:
            if not messagebox.askyesno(
                "確認匯出",
                "目前沒有任何群組或規則。確定要匯出空白的 opt 檔嗎？",
                parent=self
            ):
                return

        content = OptGenerator.generate(self.groups, self.rules)
        backup = self.backup_var.get()

        try:
            os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".",
                        exist_ok=True)
            OptGenerator.export(content, out_path, backup=backup)
        except PermissionError:
            messagebox.showerror(
                "權限不足",
                f"無法寫入至：\n{out_path}\n\n請以系統管理員身分執行此工具，或選擇其他路徑。",
                parent=self
            )
            return
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e), parent=self)
            return

        msg = f"✔ 已成功匯出至：\n{out_path}"
        if backup and os.path.exists(out_path):
            msg += "\n（已自動備份原有 opt 檔）"
        messagebox.showinfo("匯出成功", msg + "\n\n⚠ 請記得重啟 License Manager 讓設定生效！", parent=self)
        self.status_var.set(f"✔ 已匯出：{out_path}")


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

        tk.Label(self, text="群組類型：",
                 font=("微軟正黑體", 10), bg="#2b2b2b", fg="#eeeeee").grid(
            row=0, column=0, sticky=W, **pad)
        self.type_var = tk.StringVar(value="GROUP")
        type_cb = ttk.Combobox(self, textvariable=self.type_var,
                                values=["GROUP", "HOST_GROUP"],
                                state="readonly", font=("Calibri", 10), width=16)
        type_cb.grid(row=0, column=1, sticky=W, **pad)

        tk.Label(self, text="群組名稱：",
                 font=("微軟正黑體", 10), bg="#2b2b2b", fg="#eeeeee").grid(
            row=1, column=0, sticky=W, **pad)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(self, textvariable=self.name_var,
                                font=("Calibri", 10), width=20)
        name_entry.grid(row=1, column=1, sticky=W, **pad)
        name_entry.focus_set()

        tk.Label(
            self,
            text="建議使用英文命名，不含空白或中文。\n例如：TeamA、SI_Group",
            font=("微軟正黑體", 9), bg="#2b2b2b", fg="#888888", justify=LEFT
        ).grid(row=2, column=0, columnspan=2, **pad)

        btn_frame = tk.Frame(self, bg="#2b2b2b")
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(4, 10))

        ttk.Button(btn_frame, text="確定", command=self._ok, width=10).pack(side=LEFT, padx=6)
        ttk.Button(btn_frame, text="取消", command=self.destroy, width=10).pack(side=LEFT)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

        # 置中
        self.update_idletasks()
        parent.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")

    def _ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "群組名稱不能為空。", parent=self)
            return
        if re.search(r"[\s\u4e00-\u9fff]", name):
            messagebox.showwarning(
                "命名規則",
                "群組名稱不應包含空白或中文，請使用英文字母、數字與底線。",
                parent=self
            )
            return
        self.result = (self.type_var.get(), name)
        self.destroy()


# ─────────────────────────────────────────────────────────────
#  程式入口
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
