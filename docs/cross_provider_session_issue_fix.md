# 既有對話跨模型切換排查與優化記錄

## 1. 遇到問題 (Problem Statement)
在 Codex Desktop 中使用舊有對話切換模型（由 OpenAI 切換為 Gemini 3.8 Flash）或在 CC Switch 聚合模式下使用外接 MCP 工具時，連續遇到以下異常：
1. **HTTP 400: `invalid compaction capsule`**
   - 舊對話曾經歷上下文壓縮（Compaction），內部儲存了 OpenAI 專有的 Fernet 加密摘要（`gAAAAAB...`）。
   - 切換至 Google Gemini / Claude 本機代理時，代理因無法識別外來壓縮膠囊格式而拒絕請求。
2. **HTTP 429: `RESOURCE_EXHAUSTED / Too Many Requests`**
   - Google/Gemini 帳號整體配額尚有 87% 以上，但單次送出的 Request Payload 體積高達近 2.9 MB。
   - 排查發現歷史對話中積累了多張龐大的二進位截圖（Base64 PNG，佔逾 2 MB），換算單次 Prompt 超過數十萬 Token，瞬間擊穿 Google Antigravity 的 Per-Request / TPM 限制。
3. **聚合模式下反覆壓縮循環（Compaction Thrashing）**
   - CC Switch 在「聚合模式」下，預設將自訂代理模型的 `contextWindow` 寫入為 128K（128,000 tokens）。
   - 當 Codex 啟用大型 MCP 工具（如 Gmail、GitNexus、Google Drive 等）時，System Instructions 與 Tool Definitions 就佔據了約 114,000～115,000 tokens（達 128K 的 90%）。
   - 只要模型呼叫一次工具並回傳結果，總長度便立刻突破 128K 門檻觸發自動精簡；由於壓縮無法精簡系統提示詞與工具定義，精簡後依然維持在 115K，導致隨後每個回合或工具呼叫都重複觸發「上下文已自動精簡 / 正在壓縮情境」的死循環。
4. **對話內容缺少（視窗歷史看似遺失）**
   - Codex 原生 Compaction 機制在壓縮點前將數百輪互動折疊至單一歷史替換節點，導致前端介面折疊/隱藏早期詳細記錄。
   - 加上切換模型時若連續遇到 400 或 429 錯誤中斷，對話窗底部被大量報錯卡片填滿，容易讓使用者誤以為前期對話被洗掉。

---

## 2. 解決方案與工具優化 (Solution & Implementation)

1. **核心模組加固：`history_sanitizer.py`**
   - **壓縮膠囊轉譯**：自動將不相容的 `gAAAAAB...` 或 `ccswitch-compaction-v1` 壓縮膠囊平滑還原/轉譯為一般對話文字，消除 400 報錯。
   - **歷史圖片 Base64 瘦身**：新增 `is_heavy_image` 偵測機制，自動將歷史輪次中超過 1 KB 的圖片 Base64 數據替換為輕量標記，避免重複上傳膨脹，立即為單一對話檔案瘦身逾 6 MB。
   - **單元測試保護**：於 `test_history_sanitizer.py` 建立單元測試，涵蓋 Carrier 剝除、膠囊轉譯與圖片瘦身。

2. **聚合模式 Context Window 擴展與目錄重構**
   - **更新 CC Switch 資料庫**：修改 `~/.cc-switch/cc-switch.db`（`providers.settings_config`），將 Gemini 的 `contextWindow` 由 128,000 調高為 272,000（272K）。
   - **目錄整合腳本 `build_catalog.py`**：將官方目錄與 CC Switch 聚合模型合併，並將自訂模型的 `context_window` 正式設定為 272,000，消除 MCP 工具架構造成的死循環壓縮空間。

3. **完整歷史無損導出工具：`export_thread_history.py`**
   - 提供直接自 SQLite 資料庫（`~/.codex/thread_history_1.sqlite`）讀取並導出對話的工具：
     ```bash
     # 列出最近對話
     python3 /Users/Zack/Tools/CLIProxyAPI/export_thread_history.py -l

     # 完整導出包含所有被折疊輪次的 Markdown
     python3 /Users/Zack/Tools/CLIProxyAPI/export_thread_history.py <thread_id> -o transcript.md
     ```

4. **切換流程全自動整合：`switch-model`**
   - 在全域指令 `switch-model`（`quota_switch_guard.py`）跨 Provider 切換流程中，自動觸發歷史清理與瘦身工具。
   - 切換模型時同步修復目錄、備份設定檔、清理舊歷史並重啟客戶端，一鍵杜絕跨模型歷史污染。
