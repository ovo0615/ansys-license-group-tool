# Ansys License 分組管理標準作業程序 (SOP)

> 依據：[Controlling access to the license using the options file](https://optics.ansys.com/hc/en-us/articles/4403333893267-Controlling-access-to-the-license-using-the-options-file)（Ansys Optics 官方文件）

## 適用情境

當同一份 Ansys License File 需要依「使用者群組」或「主機群組」做權限切割時（例如：保留特定授權數量給特定部門、限制某群組只能使用特定 Feature、多組到期日不同的授權需分開管理），可透過 License Manager 的 **options file（ansyslmd.opt）** 來達成，**不需要重新申請或修改 License File 本身**。

## 事前準備

- [ ] 授權管理主機的系統管理員權限（Windows 需系統管理員；Linux 需 root）
- [ ] 已知道所有 Feature 名稱（例如 `hfss`、`ansys`、`aim_acs` 等，可從現有 `ansyslmd.lic` 內的 `FEATURE` / `INCREMENT` 行取得，或參考各產品授權對照表）
- [ ] 已列出要分組的「使用者清單」或「主機清單」（帳號需與登入系統的使用者名稱一致，區分大小寫）
- [ ] 預留 5–10 分鐘的服務中斷時間（重啟 License Manager 時，正在使用授權的使用者會短暫斷線）

---

## Step 1：找到 options file 的位置

options file 檔名固定為 **`ansyslmd.opt`**，若資料夾內沒有這個檔案，就自行新增一個純文字檔（.txt 存成 .opt，注意不要有副檔名 .txt 殘留）。

| 系統 | 路徑 |
|---|---|
| Windows | `C:\Program Files\ANSYS Inc\Shared Files\Licensing\license_files\` |
| Linux | `/ansys_inc/shared_files/licensing/license_files/` |

> 提醒：路徑中的 `license_files` 資料夾要跟你目前 `ansyslmd.lic` 所在的資料夾一致，確保 License Manager 讀取的是同一份設定。

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

範例（先定義兩個群組）：

```
GROUP TeamA jeff.hong userA userB
GROUP TeamB userC userD
```

## Step 4：撰寫存取規則

決定好分組後，依需求選擇下列關鍵字組合，寫在 GROUP 定義的下方：

| 需求 | 關鍵字 | 語法範例 |
|---|---|---|
| 保留固定數量授權給群組/使用者 | `RESERVE` | `RESERVE 2 hfss GROUP TeamA` |
| 限制群組/使用者最多可用數量 | `MAX` | `MAX 2 hfss GROUP TeamB` |
| 只允許名單內的人使用該 Feature（其餘一律不可用） | `INCLUDE` | `INCLUDE hfss GROUP TeamA` |
| 允許名單內的人使用**全部** Feature | `INCLUDEALL` | `INCLUDEALL GROUP TeamA` |
| 禁止名單內的人使用該 Feature | `EXCLUDE` | `EXCLUDE hfss GROUP TeamB` |
| 禁止名單內的人使用**全部**授權 | `EXCLUDEALL` | `EXCLUDEALL HOST 主機名` |
| 同一 Feature 有多把、到期日不同，需分開管理 | 於 Feature 後加 `:EXPDATE=日期` | `RESERVE 1 hfss:EXPDATE=31-dec-2026 GROUP TeamA` |

> `INCLUDE` 與 `EXCLUDE` 衝突時，**EXCLUDE 優先生效**。
> 若同一 Feature 因不同合約產生重複項目（例如兩份到期日不同的授權），才需要用 `:EXPDATE=`（或 `VENDOR_STRING`、`ISSUED`、`SIGN` 等）區分，這些值必須跟 `ansyslmd.lic` 內容完全一致，可直接照抄。

### 範例情境 A：保留授權給特定群組

```
# 定義群組
GROUP TeamA jeff.hong userA userB

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

## Step 6：重新啟動 License Manager 讓設定生效

options file 修改後**必須重啟 License Manager 服務**才會套用，重啟過程中所有人的授權會短暫中斷，建議挑離峰時段執行。

**Windows：**
1. 以系統管理員身分開啟「Ansys License Management Center」
2. 進入 **View Status/Start/Stop License Manager**
3. 按 **STOP**，等待數秒後再按 **START**
4. 確認狀態顯示為 Running

**Linux：**

```bash
# 若使用 systemd 管理
sudo systemctl restart ansyslmd

# 或使用 lmutil 指令，僅重新讀取設定（不中斷服務，較平順）
lmutil lmreread -c /ansys_inc/shared_files/licensing/license_files/ansyslmd.lic
```

## Step 7：驗證設定是否生效

```bash
lmutil lmstat -a -c ansyslmd.lic
```

檢查輸出中對應 Feature 是否出現 `Reservation` 或 `Users of xxx` 等訊息，確認保留/限制數量與設定的一致。若不符，回頭檢查：

- 使用者/群組名稱大小寫是否正確
- 該使用者是否被重複放進兩個 GROUP
- Feature 名稱拼字是否跟 License File 內一致

## 常見錯誤對照

| 錯誤代碼 | 原因 | 對應處理 |
|---|---|---|
| -38 | 使用者/主機被列在 `EXCLUDE` 名單 | 從 EXCLUDE 移除 |
| -39 | 使用者/主機沒被列在必要的 `INCLUDE` 名單 | 加入 INCLUDE |
| -194 | 超過 `MAX` 設定的可用數量上限 | 確認 MAX 數值或群組成員是否過多 |

---
此工具由 虎門科技資深技術工程師 Jeff Hong 洪敬傑提供
