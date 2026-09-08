# -*- coding: utf-8 -*-
"""讀回既有的 ansyslmd.opt，讓工具能「載入 → 編輯 → 匯出」。

實務上管理員手上多半已經有一份 opt 檔，只能單向產生的工具很難用。
"""

import re

from .model import (
    ARITY_COUNT_FEATURE_TARGET,
    ARITY_FEATURE_NUMBER,
    ARITY_FEATURE_TARGET,
    ARITY_TARGET_ONLY,
    GLOBAL_SPECS,
    KEYWORD_SPECS,
    TARGET_TYPES,
    AccessRule,
    GlobalOption,
    Group,
    OptDocument,
)

# feature 後面可以掛一串 :KEY=VALUE，FlexNet 實務上會用到 VERSION 與 EXPDATE
_QUALIFIER_RE = re.compile(r":(VERSION|EXPDATE)=", re.IGNORECASE)


def split_feature_token(token: str) -> tuple[str, str, str]:
    """拆出 (feature, version, expdate)。

    hfss:EXPDATE=31-dec-2026            -> ("hfss", "", "31-dec-2026")
    electronics_desktop:VERSION=2024.0113 -> ("electronics_desktop", "2024.0113", "")

    認不得的修飾詞原樣留在 feature 名稱裡，寧可讓驗證器提出警告，
    也不要在寫回檔案時把使用者原本的字句弄丟。
    """
    parts = _QUALIFIER_RE.split(token)
    name = parts[0]
    version = expdate = ""
    # split 後為 [name, KEY, VALUE, KEY, VALUE, ...]
    for key, value in zip(parts[1::2], parts[2::2]):
        if key.upper() == "VERSION":
            version = value
        else:
            expdate = value
    return name, version, expdate


def _logical_lines(text: str) -> list[tuple[str, str]]:
    """回傳 [(內容, 該行前面累積的註解)]，並處理行末反斜線續行。

    多行註解以換行保留原本的分行。接手的人常常在規則上面寫好幾行說明，
    併成一行會讓那段說明在寫回檔案時變成無法閱讀的長條。
    """
    result: list[tuple[str, str]] = []
    pending_comment: list[str] = []
    buffer = ""

    for raw in text.splitlines():
        line = raw.rstrip()
        if buffer:
            line = buffer + " " + line.strip()
            buffer = ""

        stripped = line.strip()
        if not stripped:
            # 空行結束一個註解區塊：區塊註解（例如段落標題）不屬於後面那一行
            pending_comment = []
            continue
        if stripped.startswith("#"):
            pending_comment.append(stripped.lstrip("#").strip())
            continue
        if stripped.endswith("\\"):
            buffer = stripped[:-1].rstrip()
            continue

        result.append((stripped, "\n".join(pending_comment).strip()))
        pending_comment = []

    if buffer:
        result.append((buffer, "\n".join(pending_comment).strip()))
    return result


class OptParser:
    """把 ansyslmd.opt 文字還原成 OptDocument。"""

    @staticmethod
    def parse_text(text: str) -> OptDocument:
        doc = OptDocument()

        # 檔頭註解：第一段連續的 # 行
        header: list[str] = []
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped:
                if header:
                    break
                continue
            if stripped.startswith("#"):
                header.append(stripped.lstrip("#").strip())
            else:
                break
        doc.header_comment = "\n".join(header)

        for line, comment in _logical_lines(text):
            tokens = line.split()
            keyword = tokens[0].upper()
            rest = tokens[1:]

            if keyword in ("GROUP", "HOST_GROUP"):
                if len(rest) < 1:
                    doc.unknown_lines.append(line)
                    continue
                doc.groups.append(Group(
                    group_type=keyword, name=rest[0],
                    members=list(rest[1:]), comment=comment,
                ))
                continue

            if keyword in GLOBAL_SPECS:
                doc.globals.append(GlobalOption(
                    keyword=keyword, value=" ".join(rest), comment=comment,
                ))
                continue

            spec = KEYWORD_SPECS.get(keyword)
            if spec is None:
                doc.unknown_lines.append(line)
                continue

            rule = OptParser._parse_rule(spec.arity, keyword, rest, comment)
            if rule is None:
                doc.unknown_lines.append(line)
            else:
                doc.rules.append(rule)

        return doc

    @staticmethod
    def _parse_rule(arity: str, keyword: str,
                    rest: list[str], comment: str) -> AccessRule | None:
        if arity == ARITY_COUNT_FEATURE_TARGET:
            # KW n feature TYPE name
            if len(rest) < 4:
                return None
            count, feature_token, target_type = rest[0], rest[1], rest[2].upper()
            if target_type not in TARGET_TYPES:
                return None
            feature, version, expdate = split_feature_token(feature_token)
            return AccessRule(keyword, feature, expdate, count,
                              target_type, " ".join(rest[3:]), comment,
                              version=version)

        if arity == ARITY_FEATURE_TARGET:
            # KW feature TYPE name
            if len(rest) < 3:
                return None
            feature_token, target_type = rest[0], rest[1].upper()
            if target_type not in TARGET_TYPES:
                return None
            feature, version, expdate = split_feature_token(feature_token)
            return AccessRule(keyword, feature, expdate, "",
                              target_type, " ".join(rest[2:]), comment,
                              version=version)

        if arity == ARITY_TARGET_ONLY:
            # KW TYPE name
            if len(rest) < 2:
                return None
            target_type = rest[0].upper()
            if target_type not in TARGET_TYPES:
                return None
            return AccessRule(keyword, "", "", "",
                              target_type, " ".join(rest[1:]), comment)

        if arity == ARITY_FEATURE_NUMBER:
            # KW feature n
            if len(rest) < 2:
                return None
            feature, version, expdate = split_feature_token(rest[0])
            return AccessRule(keyword, feature, expdate, rest[1], "", "", comment,
                              version=version)

        return None

    @staticmethod
    def parse(filepath: str) -> OptDocument:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError as exc:
            raise IOError(f"無法讀取檔案：{exc}") from exc
        return OptParser.parse_text(text)
