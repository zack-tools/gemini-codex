# 更新後模型路由檢查

2026-10-22：Gemini 裸模型名稱經 CC Switch 聚合入口送往 OpenAI，導致 HTTP 400；完整 ccs-gemini/ 名稱實測成功。

ensure_model_routes.py 只在 live-state.json 顯示聚合模式時工作：驗證 CC Switch 產生的目錄，修正頂層 model_catalog_json，為已知的預設模型補路由前綴，並同步舊版 model_catalog.json。修改前建立備份，寫入採用原子替換。它不改供應商資料庫、憑證、既有對話或應用程式封裝。

build_catalog.py 及目前三份 Portable 更新入口會執行檢查。若更換更新工具、CC Switch 改變目錄格式或手機仍使用快取／既有對話的裸模型名稱，仍需重新檢查；此防護不會攔截或改寫手機送出的 API 請求。

驗證：python -m unittest test_ensure_model_routes -v。已模擬清單被更新覆寫、重複執行、直接模式及異常清單。三份 PowerShell 更新程式均通過語法解析；未執行完整版本升級。實際 Gemini 3.8 請求 HTTP 200、response.completed、ROUTE_OK。
