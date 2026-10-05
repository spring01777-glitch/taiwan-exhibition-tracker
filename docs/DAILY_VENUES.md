# 三場館每日公開頁面整理

沿用既有每日台灣 09:00（UTC 01:00）GitHub Actions，不新增排程。入口為 `scripts/update_venue_sources.py`，其後 `scripts/update.py` 合併文化部資料及每來源狀態，最後部署同一個静態網站。GitHub 排程可能延遲。

| 來源 | 公開入口與檢查範圍 | 限制 |
| --- | --- | --- |
| 松山文創園區 | [展演資訊](https://www.songshanculturalpark.org/exhibition) 的活動連結及已收錄未結束詳情 | [robots](https://www.songshanculturalpark.org/robots.txt)允許公開頁面；[政策](https://www.songshanculturalpark.org/privacy)保留文案與圖像等權利，使用範圍為個人及非商業；本站沒有商業服務，不搬運文案、圖片或原列表排版 |
| 華山1914 | [公開首頁](https://www.huashan1914.com/exhibition) 可見活動及已收錄的無 query 詳情 | [robots](https://www.huashan1914.com/robots.txt)禁止 query、API、搜尋與會員頁；不讀第二頁 query，因此不保證新活動完整。官方實際 href 可能含尾端空白，保留其正確百分比編碼，不自行猜網址 |
| 駁二藝術特區 | [展演清單](https://pier2.org/exhibition/)正常瀏覽器渲染及官方詳情 | robots 回404表示沒有提供該檔案，不據此推定API授權。正常瀏覽公開頁面，不直接呼叫內部API；[隱私政策](https://pier2.org/privacy/)未列禁止此類正常公開閱讀，文案與圖像仍保留權利 |

只收錄名稱、明確起迄日期、地點、票價標示及官方連結，摘要以基本欄位自行產生。駁二票務標籤明示免票／售票時才記錄；松菸、華山沒有可靠結構化票價時明示未提供或前次人工核對，不把舊票價冒充每日確認。保留首次收錄、歷史活動、改期紀錄與原有「狀態待確認」提示。

每来源讀一次 robots 及政策，政策正文指紋比對本次人工核對版本；政策改變即停止該來源，需重新閱讀政策。無 query、同官方 HTTPS host、公開路徑，單來源最多24個詳情、請求至少間隔1.2秒、單次逾時12秒（瀏覽器18秒）、不重試、不開多個瀏覽器。駁二瀏覽器阻擋 image/font/media 及海報上傳路徑，不保存DOM全文。使用 runner 既有Chrome，不下載新瀏覽器、不關閉TLS或瀏覽器沙箱。

駁二等待頁面實際名稱與完整起迄日期欄位，不要求背景網路完全閒置；其公開清單分為目前活動與歷史，僅目前活動作每日新資料入口，已收錄歷史仍由本站快照保留，不另外讀取未收錄的舊活動詳情。這可減少無關請求與逾時風險。

空資料、欄位缺失、日期錯誤、來源量跌幅超過50%、政策或 robots 阻擋、瀏覽器缺失／失敗，均保留該來源最後成功完整快照，不以部分資料覆蓋。`data/venue-source-status.json`保存各來源最後嘗試、成功時間、數量及狀態；併入公開網站的同一資料快照。CI 仍發布保留資料與失敗提示，最後將工作標示失敗，不能稱該來源成功。

若華山首頁以外有新活動，可由獲授權的每日瀏覽器整理工作正常開啟官網、閱讀分頁、逐筆確認標題／展期／場地／票價，再把該活動實際無 query 詳情連結加入已核對資料。現有自動程式不讀禁止 query 分頁，不以隱藏 API 替代。若官網進一步禁止自動閱讀，保留資料及官方入口，回報父任務協調正常瀏覽器整理；不擅自新增排程。

驗證：`python -m unittest discover -s tests -v`；實跑可用 `python scripts/update_venue_sources.py --source huashan` 單來源驗證。Windows 開發環境可用 `--browser` 指定已安裝的Chrome／Chromium，絕不自動安裝瀏覽器。
