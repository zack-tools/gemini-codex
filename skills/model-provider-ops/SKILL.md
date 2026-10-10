---
name: model-provider-ops
description: 查詢 Codex 訂閱及 Antigravity 模型額度、解讀低額度警示、依授權切換供應商，以及診斷和修復跨供應商對話加密或壓縮錯誤。不用於 API 帳務餘額或 ChatGPT／Gemini 網頁版額度。
---

# 模型供應商維護

依目的只讀取需要的流程；不自動切換模型、清理對話、重啟程式或建立常駐監控。

- **查剩餘額度**：讀 [額度查詢](references/quota.md)，執行 `python3 scripts/check_quota.py --json`。本機 Codex 原生 `get_usage_limits` 可用時優先用它讀 Codex 額度；Antigravity 查詢才使用相應本機腳本。
- **警示／切換**：讀 [供應商切換](references/switch.md)。使用已核實模型及既有授權，缺失比例保留未知。
- **對話錯誤修復**：讀 [對話修復](references/session-repair.md)，先觀察錯誤和影響範圍，再做必要處理。

所有 scripts 是工具庫根目錄實作的相對符號連結，根目錄是唯一維護來源。此技能需安裝完整 CLIProxyAPI 工具庫；不要只複製技能資料夾。macOS / Linux 用 Python 3；Windows 可用 `python`，終端需要時設 `PYTHONIOENCODING=utf-8`。腳本支援的模型或服務變動時核實實際設定，不沿用舊清單。

查詢不得輸出 token、cookies、密碼或憑證內容。分清 ChatGPT 訂閱、Antigravity、網頁與 API 帳務；失敗服務單獨報告，不掩蓋仍成功的資料。
