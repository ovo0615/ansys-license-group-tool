# -*- coding: utf-8 -*-
from ansys_opt import LmUtil


def test_reread_command_shape():
    command = LmUtil.reread_command("/path/to/ansyslmd.lic", "/path/to/lmutil")
    assert command == ["/path/to/lmutil", "lmreread", "-c", "/path/to/ansyslmd.lic"]


def test_status_command_shape():
    command = LmUtil.status_command("/path/to/ansyslmd.lic", "/path/to/lmutil")
    assert command == ["/path/to/lmutil", "lmstat", "-a", "-c", "/path/to/ansyslmd.lic"]


def test_falls_back_to_bare_command_when_not_installed():
    assert LmUtil.reread_command("/tmp/x.lic")[0] in ("lmutil", LmUtil.find())


def test_quote_wraps_paths_containing_spaces():
    quoted = LmUtil.quote(["/a b/lmutil", "lmreread", "-c", "/c/plain.lic"])
    assert '"/a b/lmutil"' in quoted
    assert '"/c/plain.lic"' not in quoted


def test_env_var_paths_are_searched_first(monkeypatch):
    monkeypatch.setenv("ANSYSLIC_DIR", "/opt/anslic")
    candidates = LmUtil.candidates()
    assert candidates[0].startswith("/opt/anslic")


def test_run_reports_a_missing_executable_instead_of_raising():
    code, output = LmUtil.run(["/definitely/not/here/lmutil", "lmreread"])
    assert code == -1
    assert "lmutil" in output
