# 本次擴充驗證證據

台灣時間2026-10-06，独立checkout，未部署。

- python -m unittest discover -s tests -p test_live_events.py -v：10/10通過。涵蓋多場去重、失敗保留、來源消失、場館／日期更動、URL安全、錯類型、票連結場次範圍、平台不猜填、離線重建不請求來源也不提前來源時間、TLS維持驗證。Windows tempfile fixture需在允許的提權環境執行；未修改安全設定。
- node --check concerts.js 及 node --check scripts/live_browser_qa.js：通過。
- node scripts/live_filter_regression.js：40,335個地區／全場館／平台／日期組合通過，含不存在的組合；另驗證臺灣午夜、搜尋、取消、已過日期、同日不同時刻／多平台及連動選項。
- python scripts/validate_live_events.py：演唱會24組28場、脫口秀29組39場公開schema通過，檢查重複場次、逐場票連結範圍、HTTPS、允許平台、個資與敏感欄位排除。
- python scripts/update_live_events.py --manual-only：離線重建成功，文化部快照及原來源核對時間保留。本次完成前未再進行官方網站或API查詢。

ibon都暻秀、OPENTIX非非及寬宏小宇、鄭恩地、郭子、工藤静香由父任務雲端核實回傳，已更新資料。非非開賣只公布2026/08/19，沒有時刻，因此saleAt保持null並文字註明。其他已收錄人工資料為先前正式活動頁基本事實核對，非即時售票狀態。

本次新增平台與場次後尚未實跑手機瀏覽器。先前初版390x844的結果不能作本次證據。已準備 scripts/live_browser_qa.js：390x844，逐組地區／场館／平台／日期比對JSON，搜尋、空結果與reset、橫向溢出；交雲端在授權頁面執行。不得使用個人Chrome或本機瀏覽器重新核對。整合者可用雲端QA核實手機操作後再發布。

舊瀏覽器嘗試因本機8876服務未運行而connection refused；沒有取得新版UI通過結果，也沒有登入或購票。最後git diff --check另納入交付檢查。
