# CC Switch × Antigravity：Codex Desktop 模型清單排查紀錄

> 驗證日期：2026-10-09  
> 環境：macOS、CC Switch 4.0.5、Antigravity CLI（`agy`）1.3.1、CLIProxyAPI 8.0.4  
> 本文件以 `agy models`、`agy --effort` 與代理實際請求紀錄為準；若與 README 舊版模型表衝突，以本文件為準。

## 1. 問題現象

Codex Desktop 使用 CC Switch 聚合模式後，模型選單出現以下問題：

- Antigravity 代理回傳的內部或實驗模型全部進入選單，數量由正式 7 個邏輯模型膨脹成 12 個。
- 顯示名稱直接使用模型 ID，例如 `gemini-3.8-flash-high`、`claude-opus-4-6-thinking`。
- Gemini 同系列模型排序分散，Claude、GPT-OSS 混在其中。
- CC Switch 將「未設定思考等級」輸出為 `none/high`，使固定 Thinking 模型出現誤導滑桿。
- 只修改 `~/.codex/cc-switch-model-catalog.json` 可以暫時修正畫面，但 CC Switch 重啟或再次儲存供應商後會重新產生檔案，舊問題會復發。
- 只關閉 Codex 視窗不會重新載入模型目錄；macOS 必須使用 `⌘Q` 完全結束。

## 2. 先排除的錯誤前提

### 2.1 不要直接相信代理的 `/v1/models`

CLIProxyAPI 的 `/v1/models` 是代理可接受的路由 ID，不等於 Antigravity CLI 提供給使用者的正式模型清單。Image、Lite、Pro Agent 等 ID 可能存在於代理，但不應自動全部放入 Codex 模型選單。

### 2.2 不要依模型名稱猜測思考檔位

`-high`、`-medium`、`-low` 可能是上游模型變體，也可能由代理透過 `reasoning.effort` 轉換。是否支援滑桿必須用 Antigravity CLI 實測。

### 2.3 不要替 Claude 補上低／中／高

本次環境的 `agy` 對 Claude 回報 `--effort` 不支援。Claude 模型本身是固定 Thinking 模式；在 Codex 目錄中應只保留單一 `high`，避免產生可切換的假滑桿。

## 3. 權威清單與實測方式

### 3.1 列出 Antigravity 正式模型

```bash
agy --version
agy models
```

本次 `agy models` 回傳的正式模型族群：

- Gemini 3.8 Flash：High / Medium / Low
- Gemini 3.7 Flash：High / Medium / Low
- Gemini 3.6 Flash：High / Medium / Low
- Gemini 3.1 Pro：High / Low
- Claude Sonnet 4.6
- Claude Opus 4.6 Thinking
- GPT-OSS 120B Medium

### 3.2 用唯讀命令檢查 effort

`/effort` 只回報模型的 effort 能力，適合用於驗證，不需要執行長任務：

```bash
agy --model gemini-3.8-flash --effort low    -p '/effort' --output-format json
agy --model gemini-3.8-flash --effort medium -p '/effort' --output-format json
agy --model gemini-3.8-flash --effort high   -p '/effort' --output-format json

agy --model gemini-3.1-pro --effort low  -p '/effort' --output-format json
agy --model gemini-3.1-pro --effort high -p '/effort' --output-format json
```

反向測試也很重要：

```bash
agy --model gemini-3.1-pro --effort medium -p '/effort' --output-format json
agy --model claude-sonnet-4-6 --effort low -p '/effort' --output-format json
agy --model claude-opus-4-6-thinking --effort high -p '/effort' --output-format json
agy --model gpt-oss-120b --effort low -p '/effort' --output-format json
```

預期結果：

- Gemini 3.8／3.7／3.6：接受 low、medium、high。
- Gemini 3.1 Pro：只接受 low、high；medium 不支援。
- Claude Sonnet／Opus：不接受 `--effort`。
- GPT-OSS 120B：固定 medium。

## 4. 最終模型清單

| 顯示名稱 | 實際請求 ID | Codex effort |
| --- | --- | --- |
| Gemini 3.8 Flash | `gemini-3.8-flash-high` | low / medium / high |
| Gemini 3.7 Flash | `gemini-3.7-flash-high` | low / medium / high |
| Gemini 3.6 Flash | `gemini-3.6-flash-high` | low / medium / high |
| Gemini 3.1 Pro | `gemini-3.1-pro-low` | low / high |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 固定 high |
| Claude Opus 4.6 Thinking | `claude-opus-4-6-thinking` | 固定 high |
| GPT-OSS 120B | `gpt-oss-120b-medium` | 固定 medium |

排序固定為：

1. Gemini 3.8
2. Gemini 3.7
3. Gemini 3.6
4. Gemini 3.1 Pro
5. Claude Sonnet
6. Claude Opus
7. GPT-OSS

## 5. 為什麼 Codex 滑桿可以控制 Gemini

Codex 會在 Responses API 請求中送出：

```json
{
  "model": "gemini-3.8-flash-high",
  "reasoning": {
    "effort": "low"
  }
}
```

CLIProxyAPI 會將它轉成 Antigravity 的原生參數：

```json
{
  "model": "gemini-3.8-flash-high",
  "generationConfig": {
    "thinkingConfig": {
      "thinkingLevel": "low",
      "includeThoughts": true
    }
  }
}
```

本次低檔請求取得 HTTP 200，代理紀錄也顯示 `thinkingLevel: low`。因此不需要另外寫「low 時把模型 ID 改成 `gemini-3.8-flash-low`」的請求覆寫規則。多餘覆寫會增加維護成本，且可能與代理新版的原生轉換衝突。

## 6. 排查順序

### 第一步：確認 Codex 使用哪個模型目錄

```bash
rg -n '^(model_provider|model_catalog_json)\s*=' ~/.codex/config.toml
```

聚合模式應指向：

```toml
model_provider = "custom"
model_catalog_json = "cc-switch-model-catalog.json"
```

### 第二步：確認代理模型

```bash
curl -sS http://127.0.0.1:8317/v1/models \
  -H 'Authorization: Bearer <LOCAL_PROXY_KEY>' |
  jq -r '.data[].id'
```

這一步只確認代理能路由哪些 ID，不能直接拿結果生成 Codex 選單。

### 第三步：檢查 CC Switch 的來源資料

macOS 資料庫：

```text
~/.cc-switch/cc-switch.db
```

先備份：

```bash
sqlite3 ~/.cc-switch/cc-switch.db \
  ".backup '$HOME/.cc-switch/cc-switch.db.bak-model-cleanup'"
```

檢查聚合供應商：

```bash
sqlite3 -noheader ~/.cc-switch/cc-switch.db \
  "SELECT settings_config
   FROM providers
   WHERE app_type='codex';" |
jq '.modelCatalog.models'
```

正確狀態應只有前述 7 個模型，且 `reasoningLevels` 分別為：

- Gemini 3.8／3.7／3.6：`["low","medium","high"]`
- Gemini 3.1 Pro：`["low","high"]`
- Claude Sonnet／Opus：`["high"]`
- GPT-OSS：`["medium"]`

Claude 使用單一 `high`，不是空陣列。CC Switch 4.0.5 會把空白或缺少的 reasoning 設定補成 `none/high`。

### 第四步：檢查產生後的 Codex 目錄

```bash
jq -r '
  .models[]
  | select(.visibility == "list")
  | [
      .priority,
      .display_name,
      .slug,
      ([.supported_reasoning_levels[]?.effort] | join(","))
    ]
  | @tsv
' ~/.codex/cc-switch-model-catalog.json
```

Antigravity 區塊應恰好 7 筆，優先序連續，名稱為易讀格式。

### 第五步：分別重啟 CC Switch 與 Codex

1. 完全結束 CC Switch，再重新開啟，確認畫面顯示「Antigravity · 7 個模型」。
2. macOS 使用 `⌘Q` 完全結束 Codex Desktop。
3. 重新開啟 Codex，檢查模型選單。
4. 只關閉視窗不會清除 Codex 的模型目錄快取。

## 7. 修復原則

### 7.1 修改來源，不只修改輸出檔

`~/.codex/cc-switch-model-catalog.json` 是 CC Switch 產生物。直接修改可以驗證方向，但不是永久修復。

永久修復應更新：

```text
~/.cc-switch/cc-switch.db
providers.settings_config
modelCatalog.models
```

然後重啟 CC Switch，讓它重新產生目錄。

### 7.2 不要在 GitHub 提交本機資料

以下檔案可能包含端點、Token 或帳號資訊，不應加入版本控制：

```text
~/.cc-switch/cc-switch.db
~/.codex/config.toml
~/.codex/auth.json
~/.cli-proxy-api/*.json
CLIProxyAPI/config.yaml
```

文件中只保留欄位範例，API Key 使用 `<LOCAL_PROXY_KEY>` 佔位。

## 8. 驗證清單

完成後逐項確認：

- [ ] `agy models` 的正式模型族群與 Codex 選單一致。
- [ ] CC Switch 顯示 Antigravity 共有 7 個模型。
- [ ] Gemini 3.8／3.7／3.6 顯示低、中、高。
- [ ] Gemini 3.1 Pro 只顯示低、高。
- [ ] Claude 模型沒有可切換的多檔滑桿。
- [ ] GPT-OSS 固定 medium。
- [ ] 代理收到 Gemini low 時實際產生 `thinkingLevel: low`。
- [ ] 完全重啟 Codex 後，名稱與排序仍正確。
- [ ] 再次重啟 CC Switch 後，12 個原始模型不會復活。

## 9. 回復方式

若修改後 CC Switch 無法啟動或供應商消失：

1. 完全結束 CC Switch。
2. 用備份還原資料庫：

```bash
cp ~/.cc-switch/cc-switch.db.bak-model-cleanup \
   ~/.cc-switch/cc-switch.db
```

3. 重新開啟 CC Switch。
4. 切換一次聚合模式，重新產生 Codex 模型目錄。
5. 完全重啟 Codex Desktop。

不要只還原 `cc-switch-model-catalog.json`；若資料庫來源仍錯誤，CC Switch 下次啟動會再次覆寫。
