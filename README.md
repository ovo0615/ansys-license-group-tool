# Ansys License 分組設定工具

> 此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供

---

## 功能簡介

本工具依據《Ansys License 分組管理標準作業程序（SOP）》設計，協助系統管理員以圖形介面完成 `ansyslmd.opt` 分組設定：

- 自動解析 Ansys License 檔案（`.lic` / `.txt`），擷取所有 Feature 名稱、到期日與授權數量
- 視覺化建立 GROUP（使用者群組）與 HOST_GROUP（主機群組）
- 以下拉選單方式設定存取規則（RESERVE / MAX / INCLUDE / INCLUDEALL / EXCLUDE / EXCLUDEALL）
- 支援 `:EXPDATE=` 語法（多組不同到期日授權）
- 自動備份現有 opt 檔並匯出無註解的純淨 `ansyslmd.opt`

---

## 系統需求

| 項目 | 需求 |
|---|---|
| 作業系統 | Windows 10 / Windows 11（64 位元） |
| Python | **3.10 ~ 3.12（64 位元）**（首次啟動若無相容版本可自動安裝） |
| 網路連線 | 首次啟動時需連網安裝依賴套件 |
| 執行權限 | 一般使用者即可；若輸出路徑在 `C:\Program Files\` 下需系統管理員 |

---

## 事前下載套件

首次執行 `run_tool.bat` 時，工具會**自動**透過 uv 安裝以下套件（需要網路連線）：

| 套件名稱 | 版本 | 用途 |
|---|---|---|
| `ttkbootstrap` | ≥ 2.0.1 | 現代化 tkinter Bootstrap 主題（GUI 框架） |
| `pillow` | ≥ 12.0 | ttkbootstrap 所需的圖像處理函式庫 |

> **第一次啟動時間較長**（需建立 `.venv` 虛擬環境並安裝套件），之後啟動速度正常。

---

## 下載與啟動方式

### 方式一：從 GitHub Release 下載 ZIP（推薦）

1. 前往 GitHub Releases 頁面，下載 `AnsysLicenseGroupTool_vX.X.X.zip`
2. 解壓至任意資料夾（例如 `D:\Tools\AnsysLicenseTool\`）
3. 雙擊執行 `run_tool.bat`
4. 首次啟動會自動建立 `.venv` 並安裝套件（需網路）

### 方式二：從 GitHub Source 下載

1. GitHub 頁面點擊「Code → Download ZIP」
2. 解壓後雙擊 `run_tool.bat`

---

## 啟動流程說明

```
run_tool.bat
  └─ start.ps1
       ├─ 偵測 Python 3.10~3.12（py.exe / 具名指令 / 使用者安裝路徑）
       ├─ 若找不到相容版本 → 嘗試 WinGet 安裝 Python 3.12
       ├─ uv sync（建立 .venv 並安裝套件）
       └─ uv run ansys_license_group_tool.py（啟動 GUI）
```

> `.venv` 虛擬環境建立在工具目錄內，不影響系統 Python 環境。

---

## 操作步驟

### 步驟 1｜載入授權檔案
1. 點擊「瀏覽…」選取 Ansys License 檔案（`.lic` 或 `.txt`）
2. 點擊「解析」
3. 自動顯示 Server 資訊與所有 Feature 清單（藍色=永久，黃色=租約）

### 步驟 2｜群組管理
1. 點擊「＋ 新增群組」，選擇類型（GROUP / HOST_GROUP）並輸入名稱
2. 選取群組後於右側輸入成員（支援批次輸入）
3. 工具自動驗證：同一使用者不可屬於兩個 GROUP

### 步驟 3｜存取規則設定

| 關鍵字 | 說明 | 需填數量 |
|---|---|---|
| `RESERVE` | 保留指定數量授權給群組 | ✅ |
| `MAX` | 限制群組最多可用數量 | ✅ |
| `INCLUDE` | 只允許名單內的人使用該 Feature | ❌ |
| `INCLUDEALL` | 允許名單內的人使用全部 Feature | ❌ |
| `EXCLUDE` | 禁止名單內的人使用該 Feature | ❌ |
| `EXCLUDEALL` | 禁止名單內的人使用全部授權 | ❌ |

### 步驟 4｜匯出 Opt 檔
1. 確認輸出路徑（預設 Windows 標準路徑）
2. 勾選「自動備份」（建議保留）
3. 點擊「🔄 重新整理預覽」確認內容
4. 點擊「💾 匯出 Opt 檔」

> 匯出的 `ansyslmd.opt` 為**純淨格式**（無任何 `#` 開頭的註解行）。

---

## 重啟 License Manager（設定生效必要步驟）

### Windows
1. 以系統管理員身分開啟「**Ansys License Management Center**」
2. 進入 **View Status/Start/Stop License Manager**
3. 按 **STOP**，等待數秒後再按 **START**
4. 確認狀態顯示為 **Running**

---

## 資料安全聲明

- 本工具**完全在本機運行**，所有資料不會上傳至任何伺服器
- 授權檔案（`.lic`）在本工具的 Git 儲存庫中已加入 `.gitignore`，**不會推送至 GitHub**
- `.venv` 虛擬環境不包含任何使用者資料

---

## 常見錯誤代碼

| 錯誤代碼 | 原因 | 處理方式 |
|---|---|---|
| -38 | 使用者/主機被列在 EXCLUDE 名單 | 從 EXCLUDE 移除 |
| -39 | 使用者/主機沒被列在必要的 INCLUDE 名單 | 加入 INCLUDE |
| -194 | 超過 MAX 設定的可用數量上限 | 確認 MAX 數值或群組成員是否過多 |

---

## 產生 Release 套件

```powershell
powershell -ExecutionPolicy Bypass -File generate_release.ps1 -Version "1.0.0"
```

執行後產生：
- `AnsysLicenseGroupTool_v1.0.0.zip`（Release 套件）
- `SHA256SUMS.txt`（SHA-256 雜湊驗證檔）

---

## 檔案結構

```
License_Group_Tooklit\
├── ansys_license_group_tool.py   # 主程式（GUI）
├── run_tool.bat                  # 一鍵啟動（BAT）
├── start.ps1                     # 啟動邏輯（含 Python 探測）
├── generate_release.ps1          # 產生 Release ZIP + SHA256
├── pyproject.toml                # uv 依賴設定
├── uv.lock                       # 鎖定版本（確保可重現）
├── .gitignore                    # 排除 .venv 與敏感授權檔
├── README.md                     # 本說明文件
└── Ansys_License_分組設定_SOP.md  # 原始 SOP 文件
```

---

此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供
