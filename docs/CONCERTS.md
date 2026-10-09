# 演唱會與脫口秀專區整合說明

本次在獨立 concerts-section checkout 擴充，基於已整合的 main 279e960。未修改首頁、共用 style.css、展覽更新器或 workflow；未 push 或部署。由單一整合者 cherry-pick 本次 commit。checkout 未發現額外 AGENTS.md 或 .agents 規範。

## 資料範圍

台灣時間 2026-10-06 基準：演唱會 24 組活動／場館、28 場、6 縣市、18 場館；脫口秀 29 組、39 場、12 縣市、21 場館。演唱會包含文化部 12 組13場及人工12組15場；截至2027-01-06的未來三個月有24場，已宣布的較晚巡演保留。脫口秀39場均在該三個月內。不是全台無遺漏清單。

[文化部演唱會資料集6013](https://data.gov.tw/dataset/6013) category=17；[綜藝資料集6009](https://data.gov.tw/dataset/6009) category=11只取明確單口／脫口秀標題並排除課程。綜藝資料集本次沒有符合的單口節目；人工KKTIX補充卡米地與薩泰爾正式活動。相聲、音樂劇、一般劇場、即興、漫才及生日見面會不填入單口清單。OPENTIX非非藝術團隊屬音樂演唱會，只在演唱會頁。

KKTIX、拓元、ibon、年代、寬宏、OPENTIX均有已核對的實際活動網址。只儲存基本事實與自寫短摘要，不保存海報或複製長文。平台首頁僅出現在來源覆蓋區，不當成活動購票入口。三組既有文化部活動的購票入口仍未核對，不顯示購票按鈕。來源細節與數量以 data/live-platform-coverage.json 及頁面來源區為準。

## 每日更新的實際能力

文化部開放資料依政府資料開放授權條款第1版使用；每日對兩個分類各一次低頻請求、30秒逾時、8MB上限、沒有重試。除文化部外，另有低風險公開來源每日自動更新（台灣09:00，同一workflow）：卡米地與薩泰爾的KKTIX主辦公開events.json、臺北小巨蛋政府開放資料JSON、北流「最近活動」公開頁、OPENTIX sitemap與活動頁schema.org場次。全部檢查robots.txt、每次請求間隔1.2秒、只存基本事實，失敗或來源量驟減超過50%即保留最後成功資料；人工核對過的票價、開賣時間與備註不會被自動資料覆蓋。拓元、ibon、年代、寬宏與KKTIX總站因條款、robots或防機器人機制，仍為人工核對快照，顯示最近核對日期，不能解讀為每日重查或即時票況。詳見[自動擷取來源](LIVE_CRAWLERS.md)。其他獨立喜劇場館仍有覆蓋缺口；兩個男人網站本次失敗，不能推定沒有節目。

執行 python scripts/update_live_events.py 更新文化部；失敗保留前次資料、來源錯誤與最後成功時間，任一分類失敗exit 1，另一分類仍可更新。來源消失標unconfirmed，時間变化標changed，不推定取消或改期。確認公告後人工以cancelled／rescheduled、statusNote與revisions更新。

執行 python scripts/update_live_events.py --manual-only 可完全離線合併人工資料，保留文化部資料及原核對時間；適用雲端核實後補資料。不可藉此宣稱已重查文化部。

## 篩選與購票資料

schemaVersion=2，單一活動／場館可多日期與同日多時刻。tickets逐筆保存平台、已核對URL、日期／時刻範圍、票價、開賣時間及核對日期。同一平台不同場次URL保留；同URL且相同價格／開賣資訊合併範圍。文化部核對表另外限定日期、時刻與場館，新增或改期場次不會繼承舊票連結。未知售票平台、首頁URL、未核對URL被拒絕。無精確時刻以null及未提供文字顯示，不補猜；巴斯活動頁開演時間互相衝突，明示待確認。

Asia/Taipei計算今天。地區、場館、售票平台、日期、文字、顯示範圍為AND；平台與日期必須匹配同一場次，不能分別命中不同日期。選項依其餘條件連動，地區改變會清除不適用場館；資料全部縣市與場館都能選。卡片僅呈現符合場次。取消預設不顯示，全部狀態可查看。

## 整合

1. 本次只cherry-pick擴充commit，先前初版已在main，不需重套初版integration/live-events.patch。
2. 現有首頁與單一每日workflow已整合，這次沒有新的共享檔案patch。保留既有原子發布與失敗保留資料設定。
3. Pages產物繼續包含 concerts.html、comedy.html、concerts.js、concerts.css、data/concerts.json及data/comedy.json。來源覆蓋已嵌入公開JSON；人工檔、核對表、測試、原始來源不必公開。
4. 整合後跑 docs/LIVE_EVENTS_QA.md 的離線檢查，再由雲端瀏覽器完成新版手機操作驗證。只有整合者發布。

已核實的寬宏資料及雲端交接見 docs/LIVE_CLOUD_REVIEW.md。
