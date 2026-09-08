# -*- coding: utf-8 -*-
"""資料模型與 FlexNet options file 關鍵字規格表。

這個模組不匯入 tkinter，可獨立測試。GUI 與產生器、解析器、驗證器
都從這裡的 KEYWORD_SPECS / TARGET_TYPES 取得語法規則，
新增關鍵字時只需要改這一份表。

語法依據：FlexNet Publisher License Administration Guide,
"Managing the Options File" 章節。
"""

from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────
#  基本資料結構
# ─────────────────────────────────────────────────────────────

@dataclass
class FeatureEntry:
    """授權 Feature 條目（來自 .lic 的 INCREMENT / FEATURE 行）"""
    name: str
    version: str
    expiry: str          # "permanent" 或 "31-oct-2026"
    count: int
    issued: str = ""     # ISSUED= 值
    product: str = ""    # 由 feature_map 補上的產品名稱（非授權檔內容）


@dataclass
class Group:
    """使用者群組或主機群組"""
    group_type: str      # "GROUP" 或 "HOST_GROUP"
    name: str
    members: list[str] = field(default_factory=list)
    comment: str = ""


@dataclass
class AccessRule:
    """單一 options file 規則行。

    依 keyword 的 arity 決定哪些欄位有意義，見 KEYWORD_SPECS。

    version 語意上屬於 feature 那一組，但刻意排在最後：這個欄位是後來補的，
    放中間會讓既有的位置引數呼叫整排錯位。新程式請一律用具名引數。
    """
    keyword: str
    feature: str = ""        # arity 含 feature 時使用
    expdate: str = ""        # 附加 :EXPDATE=日期
    count: str = ""          # RESERVE/MAX 的數量，或 TIMEOUT/LINGER 的秒數
    target_type: str = ""    # USER / HOST / DISPLAY / GROUP / HOST_GROUP / INTERNET / PROJECT
    target_name: str = ""
    comment: str = ""
    version: str = ""        # 附加 :VERSION=版本，用來區分同名 Feature 的不同授權池


@dataclass
class GlobalOption:
    """不繫結到 feature 或對象的整體設定行（TIMEOUTALL、DEBUGLOG…）"""
    keyword: str
    value: str = ""
    comment: str = ""


@dataclass
class OptDocument:
    """一份完整的 ansyslmd.opt 內容"""
    globals: list[GlobalOption] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    rules: list[AccessRule] = field(default_factory=list)
    header_comment: str = ""
    unknown_lines: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
#  語法規格
# ─────────────────────────────────────────────────────────────

# 規則行的排列形狀
ARITY_COUNT_FEATURE_TARGET = "count_feature_target"   # KW n feature TYPE name
ARITY_FEATURE_TARGET = "feature_target"               # KW feature TYPE name
ARITY_TARGET_ONLY = "target_only"                     # KW TYPE name
ARITY_FEATURE_NUMBER = "feature_number"               # KW feature n


@dataclass(frozen=True)
class KeywordSpec:
    name: str
    arity: str
    summary: str          # 一句話說明，GUI 直接顯示
    note: str = ""        # 補充提醒
    count_label: str = "數量"


KEYWORD_SPECS: dict[str, KeywordSpec] = {
    spec.name: spec for spec in [
        # ── 配額 ──
        KeywordSpec(
            "RESERVE", ARITY_COUNT_FEATURE_TARGET,
            "保留指定數量的授權給對象，其他人取用不到",
            "被保留的數量即使沒人在用也不會釋出給別人。",
        ),
        KeywordSpec(
            "MAX", ARITY_COUNT_FEATURE_TARGET,
            "限制對象最多同時取用幾份該 Feature",
            "超過上限時取用端會收到 -194。",
        ),
        KeywordSpec(
            "MAX_OVERDRAFT", ARITY_FEATURE_NUMBER,
            "限制該 Feature 可超額借用的數量",
            "只有授權本身帶 OVERDRAFT 時才有意義。",
            count_label="超額數量",
        ),

        # ── 允許 / 拒絕 ──
        KeywordSpec(
            "INCLUDE", ARITY_FEATURE_TARGET,
            "只有名單內的對象可以使用該 Feature",
            "一旦設定，名單外的所有人都會被拒絕（-39）。",
        ),
        KeywordSpec(
            "INCLUDEALL", ARITY_TARGET_ONLY,
            "只有名單內的對象可以使用「全部」Feature",
            "影響範圍最大，設定前務必確認名單完整。",
        ),
        KeywordSpec(
            "EXCLUDE", ARITY_FEATURE_TARGET,
            "禁止名單內的對象使用該 Feature",
            "與 INCLUDE 衝突時 EXCLUDE 優先（被拒者收到 -38）。",
        ),
        KeywordSpec(
            "EXCLUDEALL", ARITY_TARGET_ONLY,
            "禁止名單內的對象使用「全部」Feature",
        ),
        KeywordSpec(
            "INCLUDE_BORROW", ARITY_FEATURE_TARGET,
            "只有名單內的對象可以借出（BORROW）該 Feature",
            "只對本身支援 BORROW 的授權有效。",
        ),
        KeywordSpec(
            "EXCLUDE_BORROW", ARITY_FEATURE_TARGET,
            "禁止名單內的對象借出（BORROW）該 Feature",
        ),

        # ── 閒置回收 ──
        KeywordSpec(
            "TIMEOUT", ARITY_FEATURE_NUMBER,
            "該 Feature 閒置超過指定秒數就自動回收",
            "秒數不得低於原廠設定的下限，太小會被忽略。",
            count_label="秒數",
        ),
        KeywordSpec(
            "LINGER", ARITY_FEATURE_NUMBER,
            "取用端結束後，該 Feature 仍保留給同一人的秒數",
            "設太長會讓授權長時間無法被其他人取用。",
            count_label="秒數",
        ),
    ]
}

# 全域設定（沒有 feature、沒有對象）
GLOBAL_SPECS: dict[str, dict] = {
    "TIMEOUTALL": {
        "summary": "所有 Feature 的閒置回收秒數",
        "kind": "int",
        "placeholder": "7200",
        "note": "個別 Feature 的 TIMEOUT 會覆蓋這個值。",
    },
    "GROUPCASEINSENSITIVE": {
        "summary": "GROUP / HOST_GROUP 的成員名稱不分大小寫",
        "kind": "onoff",
        "placeholder": "ON",
        "note": "預設為 OFF。設為 ON 可解掉「帳號大小寫打錯導致分組不生效」這個最常見的問題。",
    },
    "DEBUGLOG": {
        "summary": "偵錯記錄檔路徑（前面加 + 表示附加而非覆寫）",
        "kind": "path",
        "placeholder": r"+C:\Temp\ansyslmd_debug.log",
        "note": "options file 的語法錯誤會寫進這個檔案，排錯時很有用。",
    },
    "REPORTLOG": {
        "summary": "用量報表記錄檔路徑（前面加 + 表示附加）",
        "kind": "path",
        "placeholder": r"+C:\Temp\ansyslmd_report.log",
        "note": "供用量統計工具讀取。",
    },
    "NOLOG": {
        "summary": "不要記錄指定類型的事件",
        "kind": "choice",
        "choices": ["IN", "OUT", "DENIED", "QUEUED"],
        "placeholder": "IN",
        "note": "可重複設定多行。記錄檔太大時才建議使用。",
    },
}

# 對象類型
TARGET_TYPES: dict[str, str] = {
    "GROUP": "使用者群組（需先在步驟 2 定義）",
    "HOST_GROUP": "主機群組（需先在步驟 2 定義）",
    "USER": "單一使用者登入帳號",
    "HOST": "單一主機名稱",
    "DISPLAY": "顯示端名稱（終端機服務環境下為用戶端名稱）",
    "INTERNET": "IP 位址，可用 * 萬用字元，例如 203.0.113.*",
    "PROJECT": "取用端設定的 LM_PROJECT 環境變數值",
}

# 需要事先以 GROUP / HOST_GROUP 定義的對象類型
GROUP_TARGET_TYPES = ("GROUP", "HOST_GROUP")


def spec_for(keyword: str) -> KeywordSpec | None:
    return KEYWORD_SPECS.get(keyword)


def needs_feature(keyword: str) -> bool:
    spec = KEYWORD_SPECS.get(keyword)
    return bool(spec) and spec.arity in (
        ARITY_COUNT_FEATURE_TARGET, ARITY_FEATURE_TARGET, ARITY_FEATURE_NUMBER
    )


def needs_count(keyword: str) -> bool:
    spec = KEYWORD_SPECS.get(keyword)
    return bool(spec) and spec.arity in (
        ARITY_COUNT_FEATURE_TARGET, ARITY_FEATURE_NUMBER
    )


def needs_target(keyword: str) -> bool:
    spec = KEYWORD_SPECS.get(keyword)
    return bool(spec) and spec.arity in (
        ARITY_COUNT_FEATURE_TARGET, ARITY_FEATURE_TARGET, ARITY_TARGET_ONLY
    )
