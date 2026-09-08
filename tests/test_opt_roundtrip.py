# -*- coding: utf-8 -*-
"""產生器與解析器要互為反向運算。"""

import pytest

from ansys_opt import (
    AccessRule,
    GlobalOption,
    Group,
    OptGenerator,
    OptParser,
    render_rule,
)


@pytest.mark.parametrize("rule,expected", [
    (AccessRule("RESERVE", "hfss", "", "2", "GROUP", "TeamA"),
     "RESERVE 2 hfss GROUP TeamA"),
    (AccessRule("RESERVE", "hfss", "31-dec-2026", "1", "GROUP", "TeamA"),
     "RESERVE 1 hfss:EXPDATE=31-dec-2026 GROUP TeamA"),
    (AccessRule("MAX", "ansys", "", "3", "USER", "user1"),
     "MAX 3 ansys USER user1"),
    (AccessRule("INCLUDE", "hfss", "", "", "GROUP", "TeamA"),
     "INCLUDE hfss GROUP TeamA"),
    (AccessRule("INCLUDEALL", "", "", "", "HOST_GROUP", "LabHosts"),
     "INCLUDEALL HOST_GROUP LabHosts"),
    (AccessRule("EXCLUDEALL", "", "", "", "INTERNET", "203.0.113.*"),
     "EXCLUDEALL INTERNET 203.0.113.*"),
    (AccessRule("EXCLUDE_BORROW", "ansys", "", "", "GROUP", "TeamB"),
     "EXCLUDE_BORROW ansys GROUP TeamB"),
    (AccessRule("TIMEOUT", "ansys", "", "7200"),
     "TIMEOUT ansys 7200"),
    (AccessRule("LINGER", "hfss", "", "300"),
     "LINGER hfss 300"),
    (AccessRule("MAX_OVERDRAFT", "ansys", "", "2"),
     "MAX_OVERDRAFT ansys 2"),
    (AccessRule("EXCLUDE", "ansys", "", "", "PROJECT", "proj-x"),
     "EXCLUDE ansys PROJECT proj-x"),
])
def test_render_rule(rule, expected):
    assert render_rule(rule) == expected


def test_unknown_keyword_is_rejected():
    with pytest.raises(ValueError):
        render_rule(AccessRule("NOT_A_KEYWORD", "ansys", "", "1", "USER", "user1"))


def _sample_doc():
    groups = [
        Group("GROUP", "TeamA", ["user1", "user2"], comment="電磁組"),
        Group("HOST_GROUP", "LabHosts", ["node1", "node2"]),
    ]
    rules = [
        AccessRule("RESERVE", "hfss", "31-jan-2027", "2", "GROUP", "TeamA",
                   comment="專案期間保留"),
        AccessRule("MAX", "ansys", "", "3", "HOST_GROUP", "LabHosts"),
        AccessRule("TIMEOUT", "ansys", "", "7200"),
        AccessRule("EXCLUDEALL", "", "", "", "INTERNET", "203.0.113.*"),
    ]
    globals_ = [
        GlobalOption("GROUPCASEINSENSITIVE", "ON"),
        GlobalOption("TIMEOUTALL", "14400", comment="全域閒置回收"),
    ]
    return groups, rules, globals_


def test_roundtrip_preserves_everything():
    groups, rules, globals_ = _sample_doc()
    text = OptGenerator.generate(groups, rules, globals_, keep_comments=True)
    doc = OptParser.parse_text(text)

    assert [(g.group_type, g.name, g.members) for g in doc.groups] == \
           [(g.group_type, g.name, g.members) for g in groups]
    assert [(r.keyword, r.feature, r.expdate, r.count, r.target_type, r.target_name)
            for r in doc.rules] == \
           [(r.keyword, r.feature, r.expdate, r.count, r.target_type, r.target_name)
            for r in rules]
    assert [(o.keyword, o.value) for o in doc.globals] == \
           [(o.keyword, o.value) for o in globals_]
    assert not doc.unknown_lines


def test_roundtrip_recovers_comments():
    groups, rules, globals_ = _sample_doc()
    text = OptGenerator.generate(groups, rules, globals_, keep_comments=True)
    doc = OptParser.parse_text(text)

    assert doc.rules[0].comment == "專案期間保留"
    assert next(g for g in doc.groups if g.name == "TeamA").comment == "電磁組"
    assert next(o for o in doc.globals if o.keyword == "TIMEOUTALL").comment \
        == "全域閒置回收"


def test_comments_can_be_switched_off():
    groups, rules, globals_ = _sample_doc()
    text = OptGenerator.generate(groups, rules, globals_, keep_comments=False)
    assert "#" not in text
    # 關掉註解也不能改變語法本身
    doc = OptParser.parse_text(text)
    assert len(doc.rules) == len(rules)
    assert len(doc.groups) == len(groups)


def test_comments_are_kept_by_default():
    groups, rules, globals_ = _sample_doc()
    assert "#" in OptGenerator.generate(groups, rules, globals_)


def test_parser_handles_hand_written_file():
    text = """\
# 手寫的檔案，格式比較隨性
GROUP  TeamA   user1 user2
   # 縮排的註解
RESERVE 2 hfss GROUP TeamA
EXCLUDE ansys USER user3
groupcaseinsensitive ON
CompletelyUnknownLine foo bar
"""
    doc = OptParser.parse_text(text)
    assert doc.groups[0].members == ["user1", "user2"]
    assert doc.rules[0].keyword == "RESERVE"
    assert doc.rules[1].keyword == "EXCLUDE"
    assert doc.globals[0].keyword == "GROUPCASEINSENSITIVE"
    assert doc.unknown_lines == ["CompletelyUnknownLine foo bar"]


def test_parser_handles_continuation_lines():
    text = "GROUP TeamA user1 user2 \\\n    user3 user4\n"
    doc = OptParser.parse_text(text)
    assert doc.groups[0].members == ["user1", "user2", "user3", "user4"]


def test_export_writes_trailing_newline(tmp_path):
    target = tmp_path / "out.txt"
    OptGenerator.export("RESERVE 1 ansys USER user1", str(target), backup=False)
    assert target.read_text(encoding="utf-8").endswith("\n")


def test_export_backs_up_existing_file(tmp_path):
    target = tmp_path / "out.txt"
    target.write_text("原本的內容\n", encoding="utf-8")
    backup = OptGenerator.export("新的內容", str(target), backup=True)

    assert backup and ".bak_" in backup
    with open(backup, encoding="utf-8") as fh:
        assert fh.read() == "原本的內容\n"
    assert target.read_text(encoding="utf-8") == "新的內容\n"


def test_multi_line_comments_keep_their_line_breaks():
    """接手的人常在規則上面寫好幾行說明，載入再匯出不該把它壓成一長條。"""
    text = (
        "# 第一行說明\n"
        "# 第二行說明\n"
        "# 第三行說明\n"
        "EXCLUDE hfss HOST_GROUP LabHosts\n"
    )
    doc = OptParser.parse_text(text)
    assert doc.rules[0].comment == "第一行說明\n第二行說明\n第三行說明"

    out = OptGenerator.generate(doc.groups, doc.rules, doc.globals,
                                keep_comments=True)
    body = [l for l in out.splitlines() if "行說明" in l or l.startswith("EXCLUDE")]
    assert body == [
        "# 第一行說明", "# 第二行說明", "# 第三行說明",
        "EXCLUDE hfss HOST_GROUP LabHosts",
    ]
