# 既有對話跨模型切換排查與優化記錄

## 1. 遇到問題 (Problem Statement)
在 Codex Desktop 中使用舊有對話切換模型（由 OpenAI 切換為 Gemini 3.8 Flash）時，連續遇到以下異常：
1. **HTTP 400: `invalid compaction capsule`**
   - 舊對話曾經歷上下文壓縮（Compaction），內部儲存了 OpenAI 專有的 Fernet 加密摘要（`gAAAAAB...`）。
   - 切換至 Google Gemini / Claude 本機代理時，代理因無法識別外來壓縮膠囊格式而拒絕請求。
2. **HTTP 429: `RESOURCE_EXHAUSTED / Too Many Requests`**
   - Google/Gemini 帳號整體配額尚有 87% 以上，但單次送出的 Request Payload 體積高達近 2.9 MB。
   - 排查發現歷史對話中積累了 6 張龐大的二進位截圖（Base64 PNG，佔逾 2 MB），換算單次 Prompt 超過數十萬 Token，瞬間擊穿 Google Antigravity 的 Per-Request / TPM 限制。
3. **對話內容缺少**
   - Codex 原生 Compaction 機制在壓縮點前將數百輪互動折疊至單一歷史替換節點，導致前端介面折疊/隱藏早期詳細記錄。

---

## 2. 解決方案與工具優化 (Solution & Implementation)

1. **核心模組加固：`history_sanitizer.py`**
   - **壓縮膠囊轉譯**：自動將不相容的 `gAAAAAB...` 或 `ccswitch-compaction-v1` 壓縮膠囊平滑還原/轉譯為一般對話文字，消除 400 報錯。
   - **歷史圖片 Base64 瘦身**：新增 `is_heavy_image` 偵測機制，自動將歷史輪次中超過 1 KB 的圖片 Base64 數據替換為輕量標記，避免重複上傳膨脹，立即為單一對話檔案瘦身逾 6 MB。
   - **單元測試保護**：於 `test_history_sanitizer.py` 建立 5 項單元測試，涵蓋 Carrier 剝除、膠囊轉譯與圖片瘦身。

2. **切換流程全自動整合：`switch-model`**
   - 在全域指令 `switch-model`（`quota_switch_guard.py`）跨 Provider 切換流程中，自動觸發歷史清理與瘦身工具。
   - 切換模型時同步修復目錄、備份設定檔、清理舊歷史並重啟客戶端，一鍵杜絕跨模型歷史污染。

