# Ansys License 分組管理標準作業程序 (SOP)

> **依據**
> - Ansys 原廠 [License Management Guide（2026 R1）](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/pdf/ansys_license_management_guide.pdf)——各版次的 PDF 在 `v261` 的位置換成 `v252`、`v251` 即可
> - [FlexNet Publisher License Administration Guide](https://docs.revenera.com/fnp/2020r3/pdf/fnp_LicAdmin.pdf) 的 "Managing the Options File" 章節——`ansyslmd.opt` 就是標準的 FlexNet options file，關鍵字語法以這份為準
> - [Controlling access to the license using the options file](https://optics.ansys.com/hc/en-us/articles/4403333893267-Controlling-access-to-the-license-using-the-options-file)（Ansys Optics KB，例子較好讀，但屬於 Optics 產品線）

## 適用情境

當同一份 Ansys License File 需要依「使用者群組」或「主機群組」做權限切割時（例如：保留特定授權數量給特定部門、限制某群組只能使用特定 Feature、多組到期日不同的授權需分開管理），可透過 License Manager 的 **options file（ansyslmd.opt）** 來達成，**不需要重新申請或修改 License File 本身**。

## 事前準備

- [ ] 授權管理主機的系統管理員權限（Windows 需系統管理員；Linux 需 root）
- [ ] 已知道所有 Feature 名稱（例如 `hfss`、`ansys`、`meba` 等，可從現有 `ansyslmd.lic` 內的 `FEATURE` / `INCREMENT` 行取得）
- [ ] 若不確定代碼對應哪個產品，可查原廠的 **Product to License Feature Mapping** 文件（原廠入口網站 → Downloads → Installation and Licensing Help Tutorials → 展開 Licensing → Product to License feature mapping archive）
- [ ] 已列出要分組的「使用者清單」或「主機清單」（帳號需與登入系統的使用者名稱一致，區分大小寫）
- [ ] 確認 `lmutil` 的位置（Windows：`...\Shared Files\Licensing\winx64\lmutil.exe`）。用 `lmreread` 套用設定不需要停機；只有在改到 `SERVER` 行時才需要預留 5–10 分鐘的服務中斷時間

---

## Step 1：找到 options file 的位置

options file 檔名固定為 **`ansyslmd.opt`**，若資料夾內沒有這個檔案，就自行新增一個純文字檔（.txt 存成 .opt，注意不要有副檔名 .txt 殘留）。

| 系統 | 路徑 |
|---|---|
| Windows | `C:\Program Files\ANSYS Inc\Shared Files\Licensing\license_files\` |
| Linux | `/ansys_inc/shared_files/licensing/license_files/` |

> 提醒：路徑中的 `license_files` 資料夾要跟你目前 `ansyslmd.lic` 所在的資料夾一致，確保 License Manager 讀取的是同一份設定。

**放在預設位置就會被自動讀取，不需要去動 `ansyslmd.lic`。**

只有在 opt 檔必須放到別的資料夾（例如與授權檔分開管理）時，才要在 `ansyslmd.lic` 的
**第二行**（`SERVER` 行的下一行）加入 `options=` 指定路徑：

```
options="C:\LicenseAdmin\ansyslmd.opt"
```

路徑含空白必須用雙引號包起來。兩種做法效果相同，**但能不動 `ansyslmd.lic` 就不要動**
——手動編輯授權檔是 `-13`（讀不到 SERVER 行）最常見的來源。

## Step 2：備份現有設定

修改前務必備份，避免改壞導致所有人都無法取用授權：

```bat
:: Windows
copy ansyslmd.opt ansyslmd.opt.bak_20260729
```

```bash
# Linux
cp ansyslmd.opt ansyslmd.opt.bak_20260729
```

## Step 3：規劃分組架構

先決定要用哪一種分組方式（可同時使用）：

| 分組方式 | 語法 | 說明 |
|---|---|---|
| 使用者群組 | `GROUP 群組名 使用者1 使用者2 ...` | 依登入帳號分組 |
| 主機群組 | `HOST_GROUP 群組名 主機1 主機2 ...` | 依電腦名稱分組（適合叢集/固定工作站） |

**重要規則：**
- 語法**區分大小寫**（GROUP、HOST_GROUP、群組名稱、使用者名稱皆是）
- **同一個使用者只能屬於一個 GROUP**，同一台主機只能屬於一個 HOST_GROUP，不可重複歸屬
- 群組名稱建議用有意義的英文命名（例如 `TeamA`、`SI_Group`），避免中文或空白

> **分組設定不生效，第一名的原因就是帳號大小寫對不上。**
> 在檔案開頭加上這一行，成員名稱就不分大小寫，可以省掉大量的來回確認：
>
> ```
> GROUPCASEINSENSITIVE ON
> ```
>
> 預設值是 `OFF`。

範例（先定義兩個群組）：

```
GROUP TeamA user1 user2 user3
GROUP TeamB user4 user5
```

## Step 4：撰寫存取規則

決定好分組後，依需求選擇下列關鍵字組合，寫在 GROUP 定義的下方：

| 需求 | 關鍵字 | 語法範例 |
|---|---|---|
| 保留固定數量授權給群組/使用者 | `RESERVE` | `RESERVE 2 hfss GROUP TeamA` |
| 限制群組/使用者最多可用數量 | `MAX` | `MAX 2 hfss GROUP TeamB` |
| 限制可超額借用的數量 | `MAX_OVERDRAFT` | `MAX_OVERDRAFT hfss 2` |
| 只允許名單內的人使用該 Feature（其餘一律不可用） | `INCLUDE` | `INCLUDE hfss GROUP TeamA` |
| 只允許名單內的人使用**全部** Feature | `INCLUDEALL` | `INCLUDEALL GROUP TeamA` |
| 禁止名單內的人使用該 Feature | `EXCLUDE` | `EXCLUDE hfss GROUP TeamB` |
| 禁止名單內的人使用**全部**授權 | `EXCLUDEALL` | `EXCLUDEALL HOST 主機名` |
| 只允許/禁止名單內的人借出授權 | `INCLUDE_BORROW` / `EXCLUDE_BORROW` | `EXCLUDE_BORROW ansys GROUP TeamB` |
| **閒置授權自動回收** | `TIMEOUT` | `TIMEOUT ansys 7200` |
| 所有 Feature 的閒置回收秒數 | `TIMEOUTALL` | `TIMEOUTALL 7200` |
| 結束後仍保留給同一人的秒數 | `LINGER` | `LINGER hfss 300` |
| 同一 Feature 有多把、到期日不同，需分開管理 | 於 Feature 後加 `:EXPDATE=日期` | `RESERVE 1 hfss:EXPDATE=31-dec-2026 GROUP TeamA` |

> **`TIMEOUT` 往往比 `RESERVE` 更能解決真正的問題。**
> 「有人開著軟體去開會，授權占著不放」比「要保留給某部門」更常發生，
> 而分組解不掉這件事，閒置回收才行。秒數不得低於原廠設定的下限（一般為 900 秒），
> 設太小整行會被忽略。

### 對象類型不只有 GROUP 和 USER

`INCLUDE` / `EXCLUDE` / `RESERVE` / `MAX` 這幾個關鍵字後面的對象，可以是：

| 類型 | 說明 | 範例 |
|---|---|---|
| `USER` / `HOST` | 單一使用者帳號 / 單一主機名稱 | `EXCLUDE hfss USER user9` |
| `GROUP` / `HOST_GROUP` | 前面定義的群組 | `RESERVE 2 hfss GROUP TeamA` |
| `DISPLAY` | 顯示端名稱（終端機服務環境下為用戶端名稱） | `EXCLUDE hfss DISPLAY term1` |
| `INTERNET` | IP 位址，可用萬用字元 | `EXCLUDEALL INTERNET 203.0.113.*` |
| `PROJECT` | 取用端設定的 `LM_PROJECT` 環境變數值 | `MAX 4 ansys PROJECT proj-x` |

`INTERNET` 對「只允許某個網段或廠區使用」特別方便，不必逐台列出主機名稱。

> `INCLUDE` 與 `EXCLUDE` 衝突時，**EXCLUDE 優先生效**。
> 若同一 Feature 因不同合約產生重複項目（例如兩份到期日不同的授權），才需要用 `:EXPDATE=`（或 `VENDOR_STRING`、`ISSUED`、`SIGN` 等）區分，這些值必須跟 `ansyslmd.lic` 內容完全一致，可直接照抄。

### 範例情境 A：保留授權給特定群組

```
# 定義群組
GROUP TeamA user1 user2 user3

# 保留 2 個 hfss 授權給 TeamA
RESERVE 2 hfss GROUP TeamA
```

### 範例情境 B：兩組不同到期日的授權要分開，互不共用

```
GROUP GroupA bob john tim
GROUP GroupB anna suzanne

RESERVE 1 hfss:EXPDATE=31-jan-2027 GROUP GroupA
RESERVE 1 hfss:EXPDATE=31-mar-2027 GROUP GroupB
```

## Step 5：儲存檔案

- 存檔編碼使用 **ANSI / UTF-8 純文字**，不要用 Word 存檔（會夾帶格式字元）
- 檔名維持 `ansyslmd.opt`，不要有其他副檔名
- 每一行一個指令，可用 `#` 開頭加註解方便日後維護

## Step 6：讓設定生效

options file 修改後必須讓 License Manager 重讀設定才會套用。**優先用 `lmreread`，不需要停機。**

### 做法一：`lmreread`（建議）

只讓 vendor daemon 重新讀取授權檔與 options file，正在跑的工作不會斷線。

```bat
:: Windows —— lmutil.exe 隨 Ansys 授權管理元件一起安裝，很多文件沒提到這件事
"C:\Program Files\ANSYS Inc\Shared Files\Licensing\winx64\lmutil.exe" lmreread -c "C:\Program Files\ANSYS Inc\Shared Files\Licensing\license_files\ansyslmd.lic"
```

```bash
# Linux
lmutil lmreread -c /ansys_inc/shared_files/licensing/license_files/ansyslmd.lic
```

> 路徑中的 `winx64` 在部分版次為 `win64`，若找不到可依 `ANSYSLIC_DIR` 環境變數往下找。

### 做法二：停止再啟動（會中斷所有人）

只有在 `lmreread` 沒有效果時才需要——例如改到的是 `SERVER` 行本身、或 vendor daemon 沒有在跑。
這個做法會讓所有正在使用授權的人斷線，請挑離峰時段執行。

**Windows：**
1. 以系統管理員身分開啟「Ansys License Management Center」
2. 進入 **View Status/Start/Stop License Manager**
3. 按 **STOP**，等待數秒後再按 **START**
4. 確認狀態顯示為 Running

**Linux：**

```bash
sudo systemctl restart ansyslmd
```

## Step 7：驗證設定是否生效

```bash
lmutil lmstat -a -c ansyslmd.lic
```

檢查輸出中對應 Feature 是否出現 `Reservation` 或 `Users of xxx` 等訊息，確認保留/限制數量與設定的一致。若不符，回頭檢查：

- 使用者/群組名稱大小寫是否正確（或直接加上 `GROUPCASEINSENSITIVE ON`）
- 該使用者是否被重複放進兩個 GROUP
- Feature 名稱拼字是否跟 License File 內一致
- 同一 Feature 有多個到期日時，是否漏了 `:EXPDATE=`

**語法錯誤不會有明顯提示，會寫進 debug log。** 在 options file 加上這一行，
就能看到 vendor daemon 讀取設定時抱怨了什麼：

```
DEBUGLOG +C:\Temp\ansyslmd_debug.log
```

`+` 表示附加而非每次覆寫。個別使用者取不到授權時，也可以用 `lmutil lmdiag` 診斷。

## 容易踩到的坑

| 狀況 | 說明 |
|---|---|
| **`INCLUDE` 是白名單，不是「額外允許」** | 一旦對某個 Feature 下了 `INCLUDE`，名單外的所有人立刻不能用（收到 -39）。`INCLUDEALL` 影響範圍更大，會涵蓋全部 Feature |
| **`RESERVE` 的數量不會釋出** | 被保留的份數即使閒置也不會給別人。把某個 Feature 全數 `RESERVE` 完，等於名單外的人完全用不到 |
| **`anshpc` 與 `anshpc_pack` 不可混用** | 兩種 HPC 增量同時保留會導致運算工作失敗，只能擇一分配 |
| **HPC Pack 以「人」為單位** | 4 個 Pack 分給 2 個人，是把 Pack 拆開，不是把核心拆開 |
| **Ansys LS-DYNA 用不到標準 HPC 增量** | LS-DYNA 的多核心運算靠自己的增量（例如 `dysmp`），規則要下在那上面 |
| **`TIMEOUT` 秒數有下限** | 低於原廠設定的下限（一般 900 秒）整行會被忽略，等於沒設 |
| **註解不必刪掉** | FlexNet 完全支援 `#` 註解。留著它們，半年後接手的人才知道每條規則為什麼存在 |

## 常見錯誤對照

| 錯誤代碼 | 原因 | 對應處理 |
|---|---|---|
| -2 | options file 語法錯誤 | 開 `DEBUGLOG` 看是哪一行 |
| -5 | 沒有這個 Feature | Feature 名稱拼錯，或該增量不在授權檔中 |
| -38 | 使用者/主機被列在 `EXCLUDE` 名單 | 從 EXCLUDE 移除 |
| -39 | 使用者/主機沒被列在必要的 `INCLUDE` 名單 | 加入 INCLUDE。設了 `INCLUDE` / `INCLUDEALL` 卻漏掉某人時就是這個 |
| -194 | 超過 `MAX` 設定的可用數量上限 | 確認 MAX 數值或群組成員是否過多 |

完整的 FlexNet 錯誤碼對照，以及與 options file 無關的連線類問題，
見 [Ansys License 故障排除專區](https://github.com/ovo0615/ansys-license-troubleshooting)。
