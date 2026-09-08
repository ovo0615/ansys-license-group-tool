# -*- coding: utf-8 -*-
"""匯出前的檢查。

把「只有做過的人才知道」的坑寫成規則，在按下匯出之前就攔下來，
而不是等到重啟服務、全公司取不到授權才發現。
"""

import difflib
from dataclasses import dataclass

from .model import (
    GROUP_TARGET_TYPES,
    AccessRule,
    FeatureEntry,
    GlobalOption,
    Group,
)

ERROR = "error"
WARNING = "warning"
INFO = "info"

_LEVEL_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}

# 兩種 HPC 增量不可混用，同時保留會讓運算工作直接失敗
HPC_CORE = "anshpc"
HPC_PACK = "anshpc_pack"

# LS-DYNA 吃不到標準 HPC 增量，要用自己的多核心增量
LSDYNA_FEATURES = ("dysmp", "dynapp", "ls-dyna", "lsdyna")

# FlexNet 對閒置回收秒數有下限，設太小會被忽略
MIN_TIMEOUT_SECONDS = 900


@dataclass
class Issue:
    level: str
    code: str
    message: str
    hint: str = ""

    def __str__(self) -> str:
        prefix = {ERROR: "錯誤", WARNING: "警告", INFO: "提醒"}[self.level]
        text = f"[{prefix}] {self.message}"
        if self.hint:
            text += f"\n        → {self.hint}"
        return text


def _feature_names(features: list[FeatureEntry]) -> set[str]:
    return {f.name for f in features}


def _total_count(features: list[FeatureEntry], name: str,
                 expdate: str = "", version: str = "") -> int | None:
    """該 Feature 在授權檔中的總數；找不到回傳 None。

    有指定 version 或 expdate 時只算對應的那個授權池。
    """
    matched = [f for f in features if f.name == name]
    if version:
        matched = [f for f in matched if f.version.lower() == version.lower()]
    if expdate:
        matched = [f for f in matched if f.expiry.lower() == expdate.lower()]
    if not matched:
        return None
    return sum(f.count for f in matched)


def _versions_of(features: list[FeatureEntry]) -> dict[str, set[str]]:
    """Feature 名稱 → 它在授權檔中出現過的版本集合。"""
    versions: dict[str, set[str]] = {}
    for feature in features:
        versions.setdefault(feature.name, set()).add(feature.version)
    return versions


def validate(groups: list[Group],
             rules: list[AccessRule],
             globals_: list[GlobalOption] | None = None,
             features: list[FeatureEntry] | None = None) -> list[Issue]:
    """回傳所有問題，依嚴重度排序。"""
    globals_ = globals_ or []
    features = features or []
    issues: list[Issue] = []

    issues += _check_groups(groups)
    issues += _check_targets(groups, rules)
    issues += _check_features(rules, features)
    issues += _check_counts(rules, features)
    issues += _check_hpc(rules, features)
    issues += _check_lockout(rules)
    issues += _check_conflicts(rules)
    issues += _check_expdate(rules, features)
    issues += _check_version(rules, features)
    issues += _check_timeouts(rules, globals_)
    issues += _check_case(groups, globals_)

    issues.sort(key=lambda i: _LEVEL_ORDER[i.level])
    return issues


# ─────────────────────────────────────────────────────────────
#  個別檢查
# ─────────────────────────────────────────────────────────────

def _check_groups(groups: list[Group]) -> list[Issue]:
    issues: list[Issue] = []
    seen_names: dict[tuple[str, str], Group] = {}

    for group in groups:
        key = (group.group_type, group.name)
        if key in seen_names:
            issues.append(Issue(
                ERROR, "GROUP_DUP",
                f"重複定義群組「{group.group_type} {group.name}」。",
                "同名群組只能定義一次，否則後面那行的成員可能被忽略。",
            ))
        seen_names[key] = group

        if not group.members:
            issues.append(Issue(
                WARNING, "GROUP_EMPTY",
                f"群組「{group.name}」沒有任何成員。",
                "空群組的規則不會對任何人生效。",
            ))

    # 同一成員被放進兩個同型別群組
    for gtype in ("GROUP", "HOST_GROUP"):
        owner: dict[str, str] = {}
        for group in groups:
            if group.group_type != gtype:
                continue
            for member in group.members:
                if member in owner and owner[member] != group.name:
                    issues.append(Issue(
                        ERROR, "MEMBER_DUP",
                        f"「{member}」同時屬於 {gtype} 的「{owner[member]}」與「{group.name}」。",
                        f"同一成員只能屬於一個 {gtype}，重複歸屬會讓分組結果無法預期。",
                    ))
                else:
                    owner[member] = group.name
    return issues


def _check_targets(groups: list[Group], rules: list[AccessRule]) -> list[Issue]:
    issues: list[Issue] = []
    defined = {(g.group_type, g.name) for g in groups}

    for rule in rules:
        if rule.target_type not in GROUP_TARGET_TYPES:
            continue
        if (rule.target_type, rule.target_name) not in defined:
            issues.append(Issue(
                ERROR, "TARGET_UNDEFINED",
                f"規則「{rule.keyword} … {rule.target_type} {rule.target_name}」"
                f"指向未定義的群組。",
                f"請先在步驟 2 建立 {rule.target_type} {rule.target_name}，"
                f"否則整行會被忽略。",
            ))
    return issues


def _check_features(rules: list[AccessRule],
                    features: list[FeatureEntry]) -> list[Issue]:
    if not features:
        return []
    issues: list[Issue] = []
    known = _feature_names(features)

    for rule in rules:
        if not rule.feature or rule.feature in known:
            continue
        close = difflib.get_close_matches(rule.feature, sorted(known), n=1, cutoff=0.7)
        hint = "Feature 名稱必須與授權檔內的拼字完全一致（區分大小寫）。"
        if close:
            hint = f"你是不是想輸入「{close[0]}」？{hint}"
        issues.append(Issue(
            WARNING, "FEATURE_UNKNOWN",
            f"「{rule.feature}」不在已載入的授權檔中。",
            hint,
        ))
    return issues


def _check_counts(rules: list[AccessRule],
                  features: list[FeatureEntry]) -> list[Issue]:
    if not features:
        return []
    issues: list[Issue] = []

    # 單條規則數量超過授權總數
    for rule in rules:
        if rule.keyword not in ("RESERVE", "MAX") or not rule.count.isdigit():
            continue
        total = _total_count(features, rule.feature, rule.expdate, rule.version)
        if total is not None and int(rule.count) > total:
            issues.append(Issue(
                ERROR, "COUNT_EXCEEDS",
                f"{rule.keyword} {rule.count} {rule.feature} 超過授權總數 {total}。",
                "數量大於實際擁有的授權時，這條規則不會如預期生效。",
            ))

    # 同一 Feature 的 RESERVE 總和超過授權總數
    reserved: dict[tuple[str, str, str], int] = {}
    for rule in rules:
        if rule.keyword != "RESERVE" or not rule.count.isdigit():
            continue
        key = (rule.feature, rule.expdate, rule.version)
        reserved[key] = reserved.get(key, 0) + int(rule.count)

    for (feature, expdate, version), amount in reserved.items():
        total = _total_count(features, feature, expdate, version)
        if total is not None and amount > total:
            issues.append(Issue(
                ERROR, "RESERVE_TOTAL_EXCEEDS",
                f"「{feature}」的 RESERVE 總和為 {amount}，超過授權總數 {total}。",
                "保留的數量即使閒置也不會釋出，全部保留完就沒有人能臨時取用。",
            ))
        elif total is not None and amount == total:
            issues.append(Issue(
                WARNING, "RESERVE_TOTAL_FULL",
                f"「{feature}」的 {total} 份授權已被 RESERVE 全數保留。",
                "名單外的人將完全無法取用這個 Feature，請確認這是預期行為。",
            ))
    return issues


def _check_hpc(rules: list[AccessRule],
               features: list[FeatureEntry]) -> list[Issue]:
    """HPC 增量的兩個已知地雷。"""
    issues: list[Issue] = []
    touched = {r.feature for r in rules if r.feature}

    if HPC_CORE in touched and HPC_PACK in touched:
        issues.append(Issue(
            ERROR, "HPC_MIX",
            f"同時對「{HPC_CORE}」與「{HPC_PACK}」設定規則。",
            "標準 HPC 與 HPC Pack 兩種增量不可混用，同時保留會導致運算工作失敗。"
            "請只選擇其中一種來分配。",
        ))

    lsdyna_in_license = {
        f.name for f in features if f.name.lower() in LSDYNA_FEATURES
    }
    if lsdyna_in_license and touched & {HPC_CORE, HPC_PACK}:
        issues.append(Issue(
            INFO, "LSDYNA_HPC",
            "授權檔中有 LS-DYNA 增量，同時也對標準 HPC 增量設定了規則。",
            f"Ansys LS-DYNA 用不到 {HPC_CORE} / {HPC_PACK}，"
            f"它的多核心運算靠自己的增量（例如 dysmp）。"
            "若目的是分配 LS-DYNA 的核心數，規則要下在 LS-DYNA 的增量上。",
        ))

    if HPC_PACK in touched:
        issues.append(Issue(
            INFO, "HPC_PACK_PER_USER",
            "HPC Pack 是以「每位使用者」為單位分配，不是以核心數分配。",
            "4 個 Pack 分給 2 個人，是把 Pack 拆開，不是把核心拆開；"
            "RESERVE 的數量請以 Pack 數來想。",
        ))
    return issues


def _check_lockout(rules: list[AccessRule]) -> list[Issue]:
    """INCLUDE / INCLUDEALL 是白名單，最容易一次鎖掉全公司。"""
    issues: list[Issue] = []

    if any(r.keyword == "INCLUDEALL" for r in rules):
        targets = [f"{r.target_type} {r.target_name}"
                   for r in rules if r.keyword == "INCLUDEALL"]
        issues.append(Issue(
            WARNING, "INCLUDEALL_LOCKOUT",
            "設定了 INCLUDEALL：只有名單內的對象能使用全部 Feature。",
            f"目前名單為 {', '.join(targets)}。"
            "不在名單內的所有人都會被拒絕（-39），套用前請確認名單完整。",
        ))

    included = {r.feature for r in rules if r.keyword == "INCLUDE" and r.feature}
    for feature in sorted(included):
        issues.append(Issue(
            WARNING, "INCLUDE_LOCKOUT",
            f"「{feature}」設定了 INCLUDE：名單外的人將無法使用它。",
            "INCLUDE 是白名單而非「額外允許」，這是最常被誤解的一點。",
        ))
    return issues


def _check_conflicts(rules: list[AccessRule]) -> list[Issue]:
    """同一對象對同一 Feature 同時 INCLUDE 與 EXCLUDE。"""
    issues: list[Issue] = []
    include_keys = {
        (r.feature, r.target_type, r.target_name)
        for r in rules if r.keyword == "INCLUDE"
    }
    for rule in rules:
        if rule.keyword != "EXCLUDE":
            continue
        key = (rule.feature, rule.target_type, rule.target_name)
        if key in include_keys:
            issues.append(Issue(
                WARNING, "INCLUDE_EXCLUDE_CONFLICT",
                f"「{rule.target_type} {rule.target_name}」對「{rule.feature}」"
                f"同時有 INCLUDE 與 EXCLUDE。",
                "兩者衝突時 EXCLUDE 優先，這個對象最終會被拒絕。",
            ))
    return issues


def _check_expdate(rules: list[AccessRule],
                   features: list[FeatureEntry]) -> list[Issue]:
    if not features:
        return []
    issues: list[Issue] = []

    # 同一 Feature 有多個不同到期日時，沒指定 EXPDATE 會落在哪一份是不確定的
    expiries: dict[str, set[str]] = {}
    for feature in features:
        expiries.setdefault(feature.name, set()).add(feature.expiry)

    for rule in rules:
        if not rule.feature:
            continue
        available = expiries.get(rule.feature)
        if not available:
            continue

        if rule.expdate:
            if rule.expdate.lower() not in {e.lower() for e in available}:
                issues.append(Issue(
                    WARNING, "EXPDATE_UNKNOWN",
                    f"「{rule.feature}」沒有到期日為 {rule.expdate} 的授權。",
                    f"授權檔中的到期日為：{', '.join(sorted(available))}。"
                    "EXPDATE 的值必須與授權檔完全一致。",
                ))
        elif len(available) > 1 and rule.keyword in ("RESERVE", "MAX"):
            issues.append(Issue(
                WARNING, "EXPDATE_NEEDED",
                f"「{rule.feature}」有 {len(available)} 組不同到期日的授權，"
                f"但規則沒有指定 EXPDATE。",
                f"到期日為：{', '.join(sorted(available))}。"
                "沒有指定時會套用到哪一份並不確定，建議加上 :EXPDATE= 明確區分。",
            ))
    return issues


def _check_version(rules: list[AccessRule],
                   features: list[FeatureEntry]) -> list[Issue]:
    """檢查 :VERSION= 的用法。

    同一個 Feature 出現在多個授權池是很常見的事（買了 Maxwell，後來又買
    Enterprise，兩份都含 electronics_desktop）。兩份都是 permanent 時
    EXPDATE 分不開它們，只有 VERSION 可以。沒指定版本的規則會套用到全部的池，
    這正是「想擋 Enterprise，結果連自己那份也一起擋掉」的來源。
    """
    if not features:
        return []
    issues: list[Issue] = []
    versions = _versions_of(features)

    for rule in rules:
        if not rule.feature or not rule.version:
            continue
        available = versions.get(rule.feature)
        if not available:
            continue  # feature 本身不存在，_check_features 已經報過了
        if rule.version not in available:
            issues.append(Issue(
                WARNING, "VERSION_UNKNOWN",
                f"「{rule.feature}」沒有版本為 {rule.version} 的授權。",
                f"授權檔中的版本為：{', '.join(sorted(available))}。"
                "VERSION 的值必須與授權檔的 INCREMENT 行完全一致。",
            ))

    # 沒指定版本、而該 Feature 確實有多個池的規則，逐個 Feature 彙總提醒一次
    ambiguous: dict[str, list[str]] = {}
    for rule in rules:
        if not rule.feature or rule.version:
            continue
        if rule.keyword not in ("EXCLUDE", "INCLUDE", "RESERVE", "MAX",
                                "EXCLUDE_BORROW", "INCLUDE_BORROW"):
            continue
        available = versions.get(rule.feature)
        if not available or len(available) < 2:
            continue
        ambiguous.setdefault(rule.feature, []).append(rule.keyword)

    for feature, keywords in sorted(ambiguous.items()):
        available = sorted(versions[feature])
        issues.append(Issue(
            INFO, "VERSION_NOT_SPECIFIED",
            f"「{feature}」有 {len(available)} 個版本的授權，"
            f"但 {'/'.join(sorted(set(keywords)))} 規則沒有指定 VERSION。",
            f"版本為：{', '.join(available)}。"
            "這條規則會同時套用到全部的授權池；"
            "只想針對其中一個池時，請填入 :VERSION=。",
        ))
    return issues


def _check_timeouts(rules: list[AccessRule],
                    globals_: list[GlobalOption]) -> list[Issue]:
    issues: list[Issue] = []

    for rule in rules:
        if rule.keyword != "TIMEOUT" or not rule.count.isdigit():
            continue
        if int(rule.count) < MIN_TIMEOUT_SECONDS:
            issues.append(Issue(
                WARNING, "TIMEOUT_TOO_SMALL",
                f"TIMEOUT {rule.feature} {rule.count} 秒低於一般下限"
                f" {MIN_TIMEOUT_SECONDS} 秒。",
                "低於原廠設定的下限時這行會被忽略，等於沒有設定。",
            ))

    for option in globals_:
        if option.keyword != "TIMEOUTALL":
            continue
        value = option.value.strip()
        if value.isdigit() and int(value) < MIN_TIMEOUT_SECONDS:
            issues.append(Issue(
                WARNING, "TIMEOUTALL_TOO_SMALL",
                f"TIMEOUTALL {value} 秒低於一般下限 {MIN_TIMEOUT_SECONDS} 秒。",
                "低於原廠設定的下限時這行會被忽略。",
            ))
    return issues


def _check_case(groups: list[Group],
                globals_: list[GlobalOption]) -> list[Issue]:
    """大小寫是分組不生效的頭號原因。"""
    case_insensitive = any(
        o.keyword == "GROUPCASEINSENSITIVE" and o.value.strip().upper() == "ON"
        for o in globals_
    )
    if case_insensitive:
        return []

    issues: list[Issue] = []
    seen_lower: dict[str, str] = {}
    collisions: set[tuple[str, str]] = set()
    has_mixed_case = False

    for group in groups:
        for member in group.members:
            if member != member.lower():
                has_mixed_case = True
            lower = member.lower()
            if lower in seen_lower and seen_lower[lower] != member:
                collisions.add(tuple(sorted((seen_lower[lower], member))))
            else:
                seen_lower[lower] = member

    for first, second in sorted(collisions):
        issues.append(Issue(
            WARNING, "MEMBER_CASE_COLLISION",
            f"「{first}」與「{second}」只差在大小寫，會被當成兩個不同的對象。",
            "加上 GROUPCASEINSENSITIVE ON 可以讓成員名稱不分大小寫。",
        ))

    if has_mixed_case and not collisions:
        issues.append(Issue(
            INFO, "CASE_SENSITIVE_HINT",
            "群組成員中有大小寫混用的名稱，而目前沒有設定 GROUPCASEINSENSITIVE。",
            "預設是區分大小寫的，登入帳號大小寫對不上就會分組失效。"
            "在步驟 3 的全域設定加上 GROUPCASEINSENSITIVE ON 可以避免這個問題。",
        ))
    return issues
