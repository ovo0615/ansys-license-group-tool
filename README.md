# Ansys License 分組設定工具

---

## 功能簡介

本工具依據《Ansys License 分組管理標準作業程序（SOP）》設計，協助系統管理員以圖形介面完成 `ansyslmd.opt` 分組設定：

- 自動解析 Ansys License 檔案（`.lic` / `.txt`），擷取所有 Feature 名稱、到期日與授權數量，
  並把 Feature 代碼翻成看得懂的產品名稱（`meba` → Ansys Mechanical Enterprise Solver）
- 視覺化建立 GROUP（使用者群組）與 HOST_GROUP（主機群組）
- 支援 11 個 FlexNet 規則關鍵字與 7 種對象類型，含閒置回收（`TIMEOUT`）與 IP 網段（`INTERNET`）
- 支援 `:EXPDATE=` 語法（多組不同到期日授權），選到多重到期日的 Feature 時自動帶入
- **匯出前自動檢查**：數量超過授權總數、指向未定義的群組、HPC 增量混用、
  INCLUDE 白名單把人鎖在外面…等 20 種常見設定錯誤
- 可**載入既有的 `ansyslmd.opt`** 修改後再匯出，不必從頭重建
- 自動備份現有 opt 檔，並可直接用 `lmreread` 套用設定（不必停掉整個服務）

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
2. 解壓至任意資料夾（例如 `C:\Tools\AnsysLicenseTool\`）
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
3. 顯示 Server 資訊與所有 Feature 清單（藍色=永久，黃色=租約），
   並附上每個 Feature 代碼對應的**產品名稱**

> 已經有一份 `ansyslmd.opt`？點右下角「載入現有 opt 檔…」可以直接讀進來修改，
> 群組、規則與註解都會還原，不必從頭重建。

#### 補齊 Feature 對照表

授權檔裡只有 `meba`、`cfd_solve_level2`、`anshpc_pack` 這類代碼，不知道對應什麼產品
就很難判斷自己在保留什麼。工具內建一份對照表，但**刻意只收錄公開資料中可查證的常見代碼**，
不會涵蓋所有授權；查不到的代碼會顯示「（未收錄）」，工具不會亂猜。

要補齊自家授權的代碼，準備一份 CSV：

```csv
feature,product,category
meba,Ansys Mechanical Enterprise Solver,結構
your_code,你們的產品名稱,分類
```

點「匯入對照表 CSV…」載入即可，內容會存到使用者設定目錄，下次啟動自動套用。

> 權威來源是 Ansys 原廠的 **Product to License Feature Mapping** 文件
> （原廠入口網站 → Downloads → Installation and Licensing Help Tutorials →
> 展開 Licensing → Product to License feature mapping archive）。
> 那份文件是原廠內容，不會收進本專案，請自行下載後轉成上面的 CSV 格式。

### 步驟 2｜群組管理
1. 點擊「＋ 新增群組」，選擇類型（GROUP / HOST_GROUP）並輸入名稱
2. 選取群組後於右側輸入成員（支援批次輸入）
3. 工具自動驗證：同一使用者不可屬於兩個 GROUP

### 步驟 3｜存取規則設定

#### 存取規則

| 關鍵字 | 說明 | 需填數值 |
|---|---|---|
| `RESERVE` | 保留指定數量授權給對象，其他人取用不到 | 數量 |
| `MAX` | 限制對象最多同時取用幾份 | 數量 |
| `MAX_OVERDRAFT` | 限制可超額借用的數量 | 數量 |
| `INCLUDE` | **只有**名單內的對象可以使用該 Feature | — |
| `INCLUDEALL` | **只有**名單內的對象可以使用全部 Feature | — |
| `EXCLUDE` | 禁止名單內的對象使用該 Feature | — |
| `EXCLUDEALL` | 禁止名單內的對象使用全部 Feature | — |
| `INCLUDE_BORROW` | 只有名單內的對象可以借出該 Feature | — |
| `EXCLUDE_BORROW` | 禁止名單內的對象借出該 Feature | — |
| `TIMEOUT` | 該 Feature 閒置超過指定秒數自動回收 | 秒數 |
| `LINGER` | 結束後仍保留給同一人的秒數 | 秒數 |

> **`TIMEOUT` 常常比 `RESERVE` 更實用。** 「有人開著軟體去開會，授權占著不放」
> 是比「要保留給某部門」更常見的問題，用 `TIMEOUT` 讓閒置的授權自動回收即可。

#### 對象類型

| 類型 | 說明 |
|---|---|
| `GROUP` / `HOST_GROUP` | 步驟 2 定義的使用者群組 / 主機群組 |
| `USER` / `HOST` | 單一使用者帳號 / 單一主機名稱 |
| `DISPLAY` | 顯示端名稱（終端機服務環境下為用戶端名稱） |
| `INTERNET` | IP 位址，可用萬用字元，例如 `203.0.113.*`，適合限制網段 |
| `PROJECT` | 取用端設定的 `LM_PROJECT` 環境變數值 |

#### 全域設定

切到「全域設定」子頁籤，可設定整份檔案層級的項目：

| 項目 | 說明 |
|---|---|
| `GROUPCASEINSENSITIVE ON` | 成員名稱不分大小寫。**建議直接開啟**——帳號大小寫對不上是分組不生效的頭號原因，畫面上有一鍵按鈕 |
| `TIMEOUTALL` | 所有 Feature 的閒置回收秒數 |
| `DEBUGLOG` / `REPORTLOG` | 偵錯與用量記錄檔路徑（opt 檔的語法錯誤會寫進 DEBUGLOG） |
| `NOLOG` | 不記錄指定類型的事件（`IN` / `OUT` / `DENIED` / `QUEUED`） |

### 步驟 4｜檢查與匯出
1. 確認輸出路徑（預設 Windows 標準路徑）
2. 勾選「自動備份」與「保留註解」（兩者都建議保留）
3. 點擊「🔄 重新整理並檢查」，右側會列出檢查結果，點任一項可看處理建議
4. 點擊「💾 匯出 Opt 檔」——**若還有「錯誤」等級的問題，工具會先攔下來要你確認**

匯出的檔案預設**保留註解**。FlexNet 完全支援 `#` 註解，留著它們，半年後接手的人
才知道每條規則為什麼存在；需要純淨檔案時取消勾選即可。

#### 匯出前會檢查什麼

| 類別 | 例子 |
|---|---|
| 數量 | RESERVE / MAX 超過授權總數；同一 Feature 的 RESERVE 總和把授權全部保留光 |
| 對象 | 規則指向未定義的群組；同一成員被放進兩個同類型群組；空群組 |
| Feature | 名稱不在授權檔中（會提示最接近的正確拼字）；EXPDATE 與授權檔對不上 |
| 多重到期日 | 同一 Feature 有多組到期日卻沒指定 `:EXPDATE=` |
| HPC | `anshpc` 與 `anshpc_pack` 混用；LS-DYNA 用不到標準 HPC 增量；HPC Pack 以人為單位 |
| 存取控制 | INCLUDE / INCLUDEALL 把名單外的人全部鎖在外面；INCLUDE 與 EXCLUDE 互相衝突 |
| 大小寫 | 成員名稱只差大小寫；有大小寫混用但沒開 GROUPCASEINSENSITIVE |
| 秒數 | TIMEOUT / TIMEOUTALL 低於下限會被忽略 |

---

## 讓設定生效

options file 改完之後**必須讓 License Manager 重讀設定**才會套用。有兩種做法：

### 做法一：`lmreread`（建議，不中斷服務）

只讓 vendor daemon 重新讀取授權檔與 options file，**正在跑的工作不會斷線**。
工具的步驟 4 下方就有這個功能，可以直接按「執行 lmreread」，或複製指令到授權主機上執行：

```bat
:: Windows（lmutil.exe 隨 Ansys 授權管理元件一起安裝）
"C:\Program Files\ANSYS Inc\Shared Files\Licensing\winx64\lmutil.exe" lmreread -c "C:\Program Files\ANSYS Inc\Shared Files\Licensing\license_files\ansyslmd.lic"
```

```bash
# Linux
lmutil lmreread -c /ansys_inc/shared_files/licensing/license_files/ansyslmd.lic
```

> 過去的做法多半是把服務停掉再啟動，代價是所有人斷線、要挑離峰時段。
> 其實 Windows 也有 `lmutil.exe`，只是很少被提到。

### 做法二：停止再啟動（會中斷所有人）

只有在 `lmreread` 沒有效果（例如 `SERVER` 行本身有變動）時才需要：

1. 以系統管理員身分開啟「**Ansys License Management Center**」
2. 進入 **View Status/Start/Stop License Manager**
3. 按 **STOP**，等待數秒後再按 **START**
4. 確認狀態顯示為 **Running**

### 驗證是否生效

```bash
lmutil lmstat -a -c <授權檔路徑>
```

檢查對應 Feature 是否出現 `Reservation` 或 `Users of xxx` 等訊息。

---

## 資料安全聲明

- 本工具**完全在本機運行**，所有資料不會上傳至任何伺服器
- 授權檔案（`.lic`）在本工具的 Git 儲存庫中已加入 `.gitignore`，**不會推送至 GitHub**
- `.venv` 虛擬環境不包含任何使用者資料
- 匯入的 Feature 對照表存在使用者設定目錄（Windows 為 `%APPDATA%\AnsysLicenseGroupTool\`），
  不會進版控

---

## 常見錯誤代碼

與 options file 設定直接相關的錯誤代碼：

| 錯誤代碼 | 原因 | 處理方式 |
|---|---|---|
| -2 | options file 語法錯誤 | 檢查 DEBUGLOG 指定的記錄檔，裡面會寫出哪一行有問題 |
| -5 | 沒有這個 Feature | Feature 名稱拼錯，或該增量不在授權檔中 |
| -38 | 使用者/主機被列在 EXCLUDE 名單 | 從 EXCLUDE 移除 |
| -39 | 使用者/主機沒被列在必要的 INCLUDE 名單 | 加入 INCLUDE。**設了 INCLUDE / INCLUDEALL 卻忘了把人放進名單，就會收到這個** |
| -194 | 超過 MAX 設定的可用數量上限 | 確認 MAX 數值或群組成員是否過多 |

完整的 FlexNet 錯誤碼對照，以及與 options file 無關的連線類問題（-4／-15／-96…），
見姊妹專區 [Ansys License 故障排除](https://github.com/ovo0615/ansys-license-troubleshooting)。

---

## 產生 Release 套件

```powershell
powershell -ExecutionPolicy Bypass -File generate_release.ps1 -Version "1.1.0"
```

執行後產生：
- `AnsysLicenseGroupTool_v1.1.0.zip`（Release 套件）
- `SHA256SUMS.txt`（SHA-256 雜湊驗證檔）

---

## 檔案結構

```
ansys-license-group-tool\
├── ansys_license_group_tool.py   # 主程式（只負責 GUI）
├── ansys_opt\                    # 核心邏輯（不依賴 tkinter，可獨立測試）
│   ├── model.py                  # 資料結構與關鍵字規格表
│   ├── license_parser.py         # 解析 .lic
│   ├── opt_parser.py             # 讀回既有的 ansyslmd.opt
│   ├── opt_generator.py          # 產生 ansyslmd.opt
│   ├── validator.py              # 匯出前的檢查規則
│   ├── feature_map.py            # Feature 代碼 → 產品名稱
│   ├── lmutil.py                 # lmreread / lmstat 指令包裝
│   └── data\feature_map.json     # 內建對照表種子檔
├── tests\                        # 單元測試與 GUI 煙霧測試
├── run_tool.bat                  # 一鍵啟動（BAT）
├── start.ps1                     # 啟動邏輯（含 Python 探測）
├── generate_release.ps1          # 產生 Release ZIP + SHA256
├── pyproject.toml                # uv 依賴設定
├── uv.lock                       # 鎖定版本（確保可重現）
├── .gitignore                    # 排除 .venv 與敏感授權檔
├── README.md                     # 本說明文件
└── Ansys_License_分組設定_SOP.md  # 原始 SOP 文件
```

> **新增關鍵字只需要改 `ansys_opt/model.py` 的規格表**，GUI 的下拉選單、
> 產生器與解析器都會自動跟上；測試會驗證這件事。

---

## 開發

```bash
# 執行測試（80 項：核心邏輯 + GUI 煙霧測試）
uv run --extra dev pytest tests -q
```

GUI 測試需要顯示裝置，沒有的話那一份會自動跳過。Linux 上可用 `xvfb-run -a` 跑完整套。

---

本 Repository 為 Jeff Hong 個人技術作品集之公開展示內容，非 Taiwan Auto-Design Co.（TADC，虎門科技）官方帳號，亦非 Ansys, Inc. 官方合作項目；Ansys、HFSS、SIwave 為 Ansys, Inc. 之商標。原始碼與內容僅供技術展示，未經授權不得商業使用、散布或製作衍生作品，詳見 [LICENSE](LICENSE)。如需授權或合作，請洽 jeff.hong@cadmen.com。
