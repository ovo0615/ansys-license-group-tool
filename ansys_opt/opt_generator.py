# -*- coding: utf-8 -*-
"""把群組與規則資料產生 ansyslmd.opt 文字。"""

import datetime
import os
import shutil

from .model import (
    ARITY_COUNT_FEATURE_TARGET,
    ARITY_FEATURE_NUMBER,
    ARITY_FEATURE_TARGET,
    ARITY_TARGET_ONLY,
    KEYWORD_SPECS,
    AccessRule,
    GlobalOption,
    Group,
)

HEADER_MARK = "# ansyslmd.opt"


def _feature_token(rule: AccessRule) -> str:
    """組出 feature[:VERSION=x][:EXPDATE=y]。

    同一個 Feature 常常同時存在於數個授權池（例如 Maxwell 那份與 Enterprise
    那份都含 electronics_desktop）。兩份都是 permanent 時，EXPDATE 分不開它們，
    只有 VERSION 可以。
    """
    token = rule.feature
    if rule.version:
        token += f":VERSION={rule.version}"
    if rule.expdate:
        token += f":EXPDATE={rule.expdate}"
    return token


def render_rule(rule: AccessRule) -> str:
    """單一規則轉成一行 options file 語法。"""
    spec = KEYWORD_SPECS.get(rule.keyword)
    if spec is None:
        raise ValueError(f"未知的關鍵字：{rule.keyword}")

    if spec.arity == ARITY_COUNT_FEATURE_TARGET:
        return (f"{rule.keyword} {rule.count} {_feature_token(rule)} "
                f"{rule.target_type} {rule.target_name}")
    if spec.arity == ARITY_FEATURE_TARGET:
        return (f"{rule.keyword} {_feature_token(rule)} "
                f"{rule.target_type} {rule.target_name}")
    if spec.arity == ARITY_TARGET_ONLY:
        return f"{rule.keyword} {rule.target_type} {rule.target_name}"
    if spec.arity == ARITY_FEATURE_NUMBER:
        return f"{rule.keyword} {_feature_token(rule)} {rule.count}"
    raise ValueError(f"未知的語法形狀：{spec.arity}")


def _comment_lines(comment: str) -> list[str]:
    """把可能有多行的註解逐行加上 #。"""
    return [f"# {line}".rstrip() for line in comment.splitlines()]


def render_group(group: Group) -> str:
    return f"{group.group_type} {group.name} {' '.join(group.members)}"


def render_global(option: GlobalOption) -> str:
    return f"{option.keyword} {option.value}".strip()


class OptGenerator:
    """產生 ansyslmd.opt 內容。

    keep_comments=True（預設）會輸出檔頭說明與每一條規則的註解。
    FlexNet 完全支援 # 註解，保留註解讓接手的人看得懂為什麼有這條規則；
    需要純淨檔案時再關掉。
    """

    @staticmethod
    def generate(groups: list[Group],
                 rules: list[AccessRule],
                 globals_: list[GlobalOption] | None = None,
                 keep_comments: bool = True,
                 header_note: str = "") -> str:
        globals_ = globals_ or []
        lines: list[str] = []

        if keep_comments:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            lines += [
                f"{HEADER_MARK} — 由 Ansys License 分組設定工具產生於 {stamp}",
                "# 修改後需重讀設定才會生效：lmutil lmreread -c <授權檔>",
            ]
            if header_note:
                for note_line in header_note.splitlines():
                    lines.append(f"# {note_line}")
            lines.append("")

        if globals_:
            if keep_comments:
                # 段落標題後留一行空白，這樣它才不會被讀回時誤認成下一行的註解
                lines += ["# ── 全域設定 ──", ""]
            for opt in globals_:
                if keep_comments and opt.comment:
                    lines += _comment_lines(opt.comment)
                lines.append(render_global(opt))
            lines.append("")

        if groups:
            if keep_comments:
                lines += ["# ── 群組定義 ──", ""]
            for group in groups:
                if keep_comments and group.comment:
                    lines += _comment_lines(group.comment)
                lines.append(render_group(group))
            lines.append("")

        if rules:
            if keep_comments:
                lines += ["# ── 存取規則 ──", ""]
            for rule in rules:
                if keep_comments and rule.comment:
                    lines += _comment_lines(rule.comment)
                lines.append(render_rule(rule))

        # 去掉結尾多餘空行，保留單一換行結尾
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)

    @staticmethod
    def export(content: str, filepath: str, backup: bool = True) -> str:
        """寫出 opt 檔，回傳實際建立的備份路徑（沒備份則為空字串）。"""
        backup_path = ""
        if backup and os.path.exists(filepath):
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{filepath}.bak_{stamp}"
            shutil.copy2(filepath, backup_path)

        if not content.endswith("\n"):
            content += "\n"
        with open(filepath, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        return backup_path
