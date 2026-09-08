# -*- coding: utf-8 -*-
"""Feature 代碼 → 產品名稱。

解析授權檔只會得到 anshpc、meba、cfd_solve_level2 這類代碼，
管理員很難據此判斷自己在保留什麼東西。這個模組把代碼翻成產品名稱。

內建的 data/feature_map.json 只是公開資料整理出來的種子檔，刻意不追求完整；
權威來源是 Ansys 原廠的 Product to License Feature Mapping 文件。
使用者可以匯入自己的 CSV 來覆蓋與補齊，匯入結果存在使用者設定目錄，不進版控。
"""

import csv
import json
import os
from dataclasses import dataclass

_BUNDLED = os.path.join(os.path.dirname(__file__), "data", "feature_map.json")


@dataclass
class FeatureInfo:
    product: str
    category: str = ""
    confidence: str = ""
    caution: str = ""
    source: str = "bundled"      # bundled 或 user


def user_map_path() -> str:
    """使用者自訂對照表的存放位置（不進版控）。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    return os.path.join(base, "AnsysLicenseGroupTool", "feature_map_user.csv")


class FeatureMap:
    def __init__(self, entries: dict[str, FeatureInfo] | None = None):
        self._entries: dict[str, FeatureInfo] = entries or {}

    # ── 建立 ──

    @classmethod
    def load(cls, include_user_map: bool = True) -> "FeatureMap":
        fmap = cls()
        fmap.load_bundled()
        if include_user_map:
            path = user_map_path()
            if os.path.exists(path):
                try:
                    fmap.load_csv(path)
                except (OSError, ValueError):
                    # 使用者的檔案壞掉不該讓工具開不起來
                    pass
        return fmap

    def load_bundled(self) -> None:
        try:
            with open(_BUNDLED, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return
        for name, info in raw.get("features", {}).items():
            self._entries[name.lower()] = FeatureInfo(
                product=info.get("product", ""),
                category=info.get("category", ""),
                confidence=info.get("confidence", ""),
                caution=info.get("caution", ""),
                source="bundled",
            )

    def load_csv(self, path: str) -> int:
        """匯入 CSV（feature,product[,category]），回傳匯入筆數。

        有標題列會自動略過。相同代碼以匯入的內容為準。
        """
        added = 0
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.reader(fh):
                if len(row) < 2:
                    continue
                name = row[0].strip()
                product = row[1].strip()
                if not name or not product:
                    continue
                if name.lower() == "feature" and product.lower() == "product":
                    continue  # 標題列
                self._entries[name.lower()] = FeatureInfo(
                    product=product,
                    category=row[2].strip() if len(row) > 2 else "",
                    source="user",
                )
                added += 1
        if added == 0:
            raise ValueError("CSV 中沒有可用的資料列（需要至少 feature,product 兩欄）。")
        return added

    def save_user_csv(self, path: str | None = None) -> str:
        """把目前使用者匯入的項目寫回 CSV，回傳檔案路徑。"""
        path = path or user_map_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["feature", "product", "category"])
            for name, info in sorted(self._entries.items()):
                if info.source == "user":
                    writer.writerow([name, info.product, info.category])
        return path

    # ── 查詢 ──

    def get(self, feature: str) -> FeatureInfo | None:
        return self._entries.get(feature.lower())

    def product_of(self, feature: str) -> str:
        """找不到就回傳空字串，絕不猜。"""
        info = self.get(feature)
        return info.product if info else ""

    def caution_of(self, feature: str) -> str:
        info = self.get(feature)
        return info.caution if info else ""

    def annotate(self, features: list) -> list:
        """把產品名稱寫進 FeatureEntry.product，回傳原本的清單。"""
        for entry in features:
            entry.product = self.product_of(entry.name)
        return features

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def user_entry_count(self) -> int:
        return sum(1 for info in self._entries.values() if info.source == "user")
