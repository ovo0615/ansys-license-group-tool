# -*- coding: utf-8 -*-
from ansys_opt import ERROR, WARNING, AccessRule, GlobalOption, Group, validate


def codes(issues, level=None):
    return {i.code for i in issues if level is None or i.level == level}


def test_clean_setup_has_no_errors(features):
    groups = [Group("GROUP", "TeamA", ["user1", "user2"])]
    rules = [AccessRule("RESERVE", "hfss", "31-jan-2027", "1", "GROUP", "TeamA")]
    assert codes(validate(groups, rules, [], features), ERROR) == set()


def test_member_in_two_groups_of_same_type():
    groups = [
        Group("GROUP", "TeamA", ["user1"]),
        Group("GROUP", "TeamB", ["user1"]),
    ]
    assert "MEMBER_DUP" in codes(validate(groups, []), ERROR)


def test_same_member_in_group_and_host_group_is_fine():
    groups = [
        Group("GROUP", "TeamA", ["node1"]),
        Group("HOST_GROUP", "LabHosts", ["node1"]),
    ]
    assert "MEMBER_DUP" not in codes(validate(groups, []))


def test_rule_pointing_at_undefined_group():
    rules = [AccessRule("RESERVE", "ansys", "", "1", "GROUP", "NoSuchTeam")]
    assert "TARGET_UNDEFINED" in codes(validate([], rules), ERROR)


def test_user_target_needs_no_group_definition():
    rules = [AccessRule("RESERVE", "ansys", "", "1", "USER", "user1")]
    assert "TARGET_UNDEFINED" not in codes(validate([], rules))


def test_typo_in_feature_name_is_caught_with_suggestion(features):
    rules = [AccessRule("RESERVE", "hfs", "", "1", "USER", "user1")]
    issues = validate([], rules, [], features)
    assert "FEATURE_UNKNOWN" in codes(issues, WARNING)
    assert "hfss" in next(i for i in issues if i.code == "FEATURE_UNKNOWN").hint


def test_count_larger_than_licensed_amount(features):
    rules = [AccessRule("RESERVE", "hfss", "31-jan-2027", "99", "USER", "user1")]
    assert "COUNT_EXCEEDS" in codes(validate([], rules, [], features), ERROR)


def test_reserve_total_across_rules_exceeds_licensed_amount(features):
    rules = [
        AccessRule("RESERVE", "hfss", "31-jan-2027", "2", "USER", "user1"),
        AccessRule("RESERVE", "hfss", "31-jan-2027", "1", "USER", "user2"),
    ]
    assert "RESERVE_TOTAL_EXCEEDS" in codes(validate([], rules, [], features), ERROR)


def test_reserving_every_seat_is_flagged(features):
    rules = [AccessRule("RESERVE", "hfss", "31-jan-2027", "2", "USER", "user1")]
    assert "RESERVE_TOTAL_FULL" in codes(validate([], rules, [], features), WARNING)


def test_mixing_hpc_and_hpc_pack_is_an_error():
    rules = [
        AccessRule("RESERVE", "anshpc", "", "8", "USER", "user1"),
        AccessRule("RESERVE", "anshpc_pack", "", "1", "USER", "user2"),
    ]
    assert "HPC_MIX" in codes(validate([], rules), ERROR)


def test_hpc_alone_is_not_an_error():
    rules = [AccessRule("RESERVE", "anshpc", "", "8", "USER", "user1")]
    assert "HPC_MIX" not in codes(validate([], rules))


def test_hpc_rule_alongside_lsdyna_licence_is_flagged(features):
    rules = [AccessRule("RESERVE", "anshpc", "", "8", "USER", "user1")]
    assert "LSDYNA_HPC" in codes(validate([], rules, [], features))


def test_hpc_pack_gets_per_user_reminder():
    rules = [AccessRule("RESERVE", "anshpc_pack", "", "1", "USER", "user1")]
    assert "HPC_PACK_PER_USER" in codes(validate([], rules))


def test_includeall_warns_about_locking_everyone_out():
    groups = [Group("GROUP", "TeamA", ["user1"])]
    rules = [AccessRule("INCLUDEALL", "", "", "", "GROUP", "TeamA")]
    assert "INCLUDEALL_LOCKOUT" in codes(validate(groups, rules), WARNING)


def test_include_warns_that_it_is_a_whitelist():
    rules = [AccessRule("INCLUDE", "ansys", "", "", "USER", "user1")]
    assert "INCLUDE_LOCKOUT" in codes(validate([], rules), WARNING)


def test_include_and_exclude_on_same_target():
    rules = [
        AccessRule("INCLUDE", "ansys", "", "", "USER", "user1"),
        AccessRule("EXCLUDE", "ansys", "", "", "USER", "user1"),
    ]
    assert "INCLUDE_EXCLUDE_CONFLICT" in codes(validate([], rules), WARNING)


def test_expdate_not_present_in_licence(features):
    rules = [AccessRule("RESERVE", "hfss", "31-dec-2099", "1", "USER", "user1")]
    assert "EXPDATE_UNKNOWN" in codes(validate([], rules, [], features), WARNING)


def test_multiple_expiry_dates_without_expdate(features):
    rules = [AccessRule("RESERVE", "hfss", "", "1", "USER", "user1")]
    assert "EXPDATE_NEEDED" in codes(validate([], rules, [], features), WARNING)


def test_single_expiry_date_needs_no_expdate(features):
    rules = [AccessRule("RESERVE", "ansys", "", "1", "USER", "user1")]
    assert "EXPDATE_NEEDED" not in codes(validate([], rules, [], features))


def test_timeout_below_the_floor():
    rules = [AccessRule("TIMEOUT", "ansys", "", "60")]
    assert "TIMEOUT_TOO_SMALL" in codes(validate([], rules), WARNING)


def test_timeoutall_below_the_floor():
    globals_ = [GlobalOption("TIMEOUTALL", "30")]
    assert "TIMEOUTALL_TOO_SMALL" in codes(validate([], [], globals_), WARNING)


def test_members_differing_only_by_case():
    groups = [
        Group("GROUP", "TeamA", ["User1"]),
        Group("GROUP", "TeamB", ["user1"]),
    ]
    assert "MEMBER_CASE_COLLISION" in codes(validate(groups, []), WARNING)


def test_case_hint_disappears_when_case_insensitive_is_on():
    groups = [Group("GROUP", "TeamA", ["User1", "USER2"])]
    assert "CASE_SENSITIVE_HINT" in codes(validate(groups, []))

    globals_ = [GlobalOption("GROUPCASEINSENSITIVE", "ON")]
    assert "CASE_SENSITIVE_HINT" not in codes(validate(groups, [], globals_))


def test_empty_group_is_flagged():
    assert "GROUP_EMPTY" in codes(validate([Group("GROUP", "TeamA", [])], []), WARNING)


def test_duplicate_group_name():
    groups = [Group("GROUP", "TeamA", ["user1"]), Group("GROUP", "TeamA", ["user2"])]
    assert "GROUP_DUP" in codes(validate(groups, []), ERROR)


def test_errors_are_sorted_first():
    groups = [Group("GROUP", "TeamA", [])]                       # warning
    rules = [AccessRule("RESERVE", "ansys", "", "1", "GROUP", "Nope")]  # error
    issues = validate(groups, rules)
    assert issues[0].level == ERROR


def test_validation_works_without_a_licence_file():
    """還沒載入授權檔時，跟授權數量無關的檢查仍要能跑。"""
    groups = [Group("GROUP", "TeamA", ["user1"]), Group("GROUP", "TeamB", ["user1"])]
    issues = validate(groups, [AccessRule("RESERVE", "ansys", "", "1", "GROUP", "TeamA")])
    assert "MEMBER_DUP" in codes(issues, ERROR)
    assert "FEATURE_UNKNOWN" not in codes(issues)
