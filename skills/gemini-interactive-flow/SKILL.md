---
name: gemini-interactive-flow
description: 適用於使用 Gemini 等自訂模型時，賦予其在 Codex 桌面端輸出「階段進度回報（不中斷自動流程）」、「內嵌互動式卡片（Inline Visualization）」與「原生一鍵點擊自動回覆按鈕（:codex-followup）」，包含在向使用者提問或多方案決策時主動觸發。
metadata:
  short-description: Gemini 階段進度回報、互動卡片與點擊自動回覆
---

# Gemini Interactive Flow

本技能專為在 Codex 桌面端使用 Gemini（包含 `ccs-gemini/*` 或自訂代理模型）設計，用以克服通用模型在桌面端缺乏「即時進度反饋」、「內嵌互動式元件」以及「按鈕一鍵送出回覆」的預設行為差異。

---

## 一、階段進度即時回報（Progress Milestone Updates）

### 1. 核心節奏：報進度但不中斷
- **一段落回報**：執行耗時、多步驟或複雜任務時，每完成一個階段目標或重要檢查點，應以**精簡的單一段落**回報進度，讓使用者即時掌握當前狀態，避免長達數十秒至數分鐘的無聲黑箱。
- **持續推進（不暫停）**：輸出進度摘要後，**立即自動繼續執行後續動作**，不需要停下來等待使用者回覆確認（除非遭遇不可逆的破壞性操作或真實阻塞條件）。

### 2. 進度段落撰寫原則
- **精準俐落**：以 1–3 句話交代「剛剛完成了什麼」與「接下來進行什麼」。
- **事實優先**：帶出關鍵數據、路徑或測試結果，不寫冗長的虛詞或推論。

---

## 二、內嵌互動式視覺化能力（Inline Visualization Contract）

當任務涉及介面設計、主題配色挑選、參數調校、即時監控模擬或方案決策時，主動製作成 Codex 桌面端原生支援的**互動式卡片**。

### 1. 輸出契約（Strict Fragment Contract）
- **純 HTML 片段**：只能包含局部標籤（如 `<div id="...">...</div>`、`<style>`、`<script>`），**嚴禁**包含 `<!DOCTYPE html>`、`<html>`、`<head>`、`<body>`。
- **獨立唯一根 ID**：片段外層必須有一個專屬 ID，所有的 CSS 選擇器與 JavaScript 操作皆以此 ID 為根（例如 `#my-widget .btn`），防止樣式外溢或命名衝突。
- **內置狀態與事件**：在 `<script>` 中以純 JavaScript 綁定事件（如點選按鈕、滑桿切換、主題更換），並直接修改局部 DOM 屬性實現即時互動反饋。

### 2. 純本機零外網安全規範（Air-Gapped / Zero External Network）
- **嚴禁外網靜態資源**：禁止引用外部 CSS/JS（嚴禁 Google Fonts、CDN scripts）、嚴禁使用 `<link rel="stylesheet" href="http...">`。
- **字型全本機回退棧**：字型必須採用作業系統原生字型：
  ```css
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft JhengHei', 'PingFang TC', sans-serif;
  ```
- **圖示全內嵌向量（Inline SVG / Pure CSS）**：禁止引用外網圖床或外部圖示字型（如 FontAwesome、Material Icons CDN），所有圖示必須以內嵌 `<svg>` 或純 CSS 形狀實現。
- **離線自給自足**：卡片在工控現場斷網、隔離內網或阻擋外網連接的沙盒環境中，必須保證 100% 正常渲染與互動，無任何外網請求逾時報錯。

### 3. 檔案寫入與觸發語法
1. **寫入檔案**：將 HTML 片段儲存於本機可存取路徑（優先選擇任務環境中的視覺化目錄，例如 `~/.codex/visualizations/...` 或任務工作目錄下的 `.html` 檔案）。
2. **調用標記**：在回覆的文字中，以**單獨一行**輸出專屬觸發語法：
   ```text
   visualize{"path":"<本機絕對路徑>/<檔名>.html"}
   ```
   * 桌上型完整寬度預覽時，可加入參數 `"mode":"wide"`：
   ```text
   visualize{"path":"<本機絕對路徑>/<檔名>.html","mode":"wide"}
   ```
3. **語法禁忌**：**絕不可**將 `visualize...` 包裹在 Markdown 代碼塊（```）或引號內，否則桌面端客戶端無法捕捉該 Token。

---

## 三、提問與決策的最佳組合拳（視覺卡片 ＋ 點擊自動送出按鈕）

### 1. 安全邊界認知（為什麼 iframe 內無法直接發送訊息）
- 視覺化卡片位於獨立的沙盒 `<iframe>` 中，受瀏覽器同源與 CSP 安全策略限制，**無法穿透至父視窗直接向聊天框發送訊息**（防止未經授權的惡意腳本在背景自動執行危險指令）。
- 因此，純卡片內提供的是「選項即時切換分析」與「剪貼簿複製備援」。

### 2. 原生點擊自動送出指令（`:codex-followup`）
- 在對話串中（卡片下方），若需要使用者確認或點擊後**直接自動發送回覆**，必須使用 Codex 桌面端原生的 Inline Follow-up 語法：
  ```markdown
  - :codex-followup[按鈕顯示文字]{prompt="點擊後自動送出的指令內容"}
  ```
- **運作效果**：Codex 桌面端會將該行 Markdown 直接渲染為原生的快捷按鈕（Action Chip）。**使用者只要點擊該按鈕，桌面端就會自動將其內容發送到對話中**，徹底實現「按按鈕就自動回覆」！
- **標準搭配結構**：
  1. 上方：以 `visualize` 呈現互動決策卡片（詳細分析與即時切換）。
  2. 下方：列出 2–3 個 `:codex-followup` 原生按鈕，點選即自動送出該選項。

---

## 四、Gemini 模型執行最佳化

1. **降低思考延遲（TTFT）**：
   - 建議推理強度（Reasoning Effort）設置為 `low`，確保串流輸出低延遲，階段性進度與卡片隨產出隨呈現。
2. **工具調用透明化**：
   - 將終端或檔案操作提煉為 1–2 句清晰的自然語言進度，不輸出大段原始 JSON 或雜訊日誌。
