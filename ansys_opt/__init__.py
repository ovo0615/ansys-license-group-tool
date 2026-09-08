# -*- coding: utf-8 -*-
"""Ansys License 分組設定工具的核心邏輯。

刻意不匯入 tkinter，讓解析、產生與驗證都能在沒有圖形介面的環境下測試。
"""

from .feature_map import FeatureMap, FeatureInfo
from .license_parser import LicenseParser
from .lmutil import LmUtil
from .model import (
    GLOBAL_SPECS,
    KEYWORD_SPECS,
    TARGET_TYPES,
    AccessRule,
    FeatureEntry,
    GlobalOption,
    Group,
    OptDocument,
    needs_count,
    needs_feature,
    needs_target,
    spec_for,
)
from .opt_generator import OptGenerator, render_group, render_rule
from .opt_parser import OptParser, split_feature_token
from .validator import ERROR, INFO, WARNING, Issue, validate

__all__ = [
    "AccessRule", "FeatureEntry", "FeatureInfo", "FeatureMap", "GlobalOption",
    "Group", "Issue", "LicenseParser", "LmUtil", "OptDocument", "OptGenerator",
    "OptParser", "ERROR", "WARNING", "INFO", "GLOBAL_SPECS", "KEYWORD_SPECS",
    "TARGET_TYPES", "needs_count", "needs_feature", "needs_target",
    "render_group", "render_rule", "spec_for", "split_feature_token",
    "validate",
]
