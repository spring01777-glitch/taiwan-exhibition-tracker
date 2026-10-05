# 演唱會與脫口秀維護／整合說明

本次在獨立 `concerts-section` 分支實作，基底 `1b0827bd916d5f49f77804023bb395ec23b9d727`。checkout內未找到AGENTS.md、.agents或專案skills額外規範。不更動展覽頁、展覽更新器、現有 workflow、共用 style.css；沒有推送或部署。

## 資料範圍與來源

- 演唱會：文化部 [演唱會資料集 6013](https://data.gov.tw/dataset/6013)，category=17，2026-10-06 台灣時間單次取得12筆來源列，排除3筆粉絲見面會／VIP加購後為12個活動與場館組合、13場；加上人工核對2個活動3場，公開共14組、16場。包含沈文程、Novelbright、謝雷、Jason Mraz、蔡義德、翁倩玉、林淑容、Paul Gilbert、AxMxP、F✦FOREVER、Blue。不是全台完整名單。
- 脫口秀：文化部 [綜藝資料集 6009](https://data.gov.tw/dataset/6009)，category=11，只收名稱含單口喜劇／站立喜劇／脫口秀／stand-up，排除課程、研討會、工作坊。本次回傳沒有符合名稱者，不能宣稱涵蓋所有喜劇演出，也不能以綜藝資料集取代喜劇俱樂部資訊。
- 人工核對脫口秀：卡米地官方 KKTIX 與薩泰爾官方 KKTIX 共6場，城市臺北／臺中／高雄／新竹，場館 Comedy Plus、Laugh House（群島園區）、洛克、Star美學館、福華文教會館。保留演員、日期時間、票價、開賣時間基本事實；未核對者明示未公布／來源未提供。
- [卡米地官方網站](https://comedy.com.tw/)與[官方售票目錄](https://comedyclub.kktix.cc/)確認主辦身份；[薩泰爾官方目錄](https://strnetwork.kktix.cc/)確認主辦身份。未含所有主要喜劇俱樂部；其他俱樂部需取得可用且允許的公開來源再納入。漫才、即興劇、研討會、課程及一般音樂演出未混入脫口秀名單。
- 政府資料依政府資料開放授權條款第1版使用，每日每分類一次請求，不取圖片或簡介長文。來源連结核對保存在 `data/live-event-links.json`，活動 UID 與標題一致才套用；新活動未核對購票網址會隱藏購票按鈕，提供資料集來源。Novelbright、謝雷、蔡義德的售票頁本次未能開啟確認，因此沒有宣稱已核對，也沒有猜網址。
- [拓元 robots](https://tixcraft.com/robots.txt)允許公開活動詳細頁但禁止購票流程路徑；[使用條款](https://tixcraft.com/terms-of-use)另有內容使用與自動程式限制。只有少量人工確認基本事實，不每日爬取拓元。KKTIX條款頁及robots本次無法可靠讀取，沒有允許自動抓取的充分依據，故KKTIX也僅人工確認。無登入、付費、訂購、API金鑰或安全設定變更。
- 人工場次的最近確認日固定，日更不會刷新此日；每日排程只更新文化部。官方活動頁連結本次已實際打開、活動名稱／城市／場次吻合；不表示仍有票。Ellery頁首場館寫群島藝術園區，內文寫 Laugh House Comedy，地址一致，將兩名並列。

## 更新與資料模型

執行 `python scripts/update_live_events.py`。標準函式庫、兩個依序請求，每次30秒逾時、8MB上限，不重試。`data/concerts.json`與`data/comedy.json`各自原子寫入，來源失敗仍寫錯誤狀態及保留前次文化部資料。任一失敗 exit 1，另一分類仍可成功更新。

人工資料放在 `*-manual.json`。明確取消或改期公告可修改人工事件 `status` 為 `cancelled`／`rescheduled`、加入 `statusNote`、`revisions` 與來源連結。文化部時間變動僅標記 `changed`（日期／時間異動），不推論正式改期；來源消失標記 `unconfirmed`，不推論取消。過期記錄保留於所有紀錄。

事件以UID＋場馆穩定識別、場次以日期＋時間去重，日期不能用連續区間取代實際場次。多場館巡演拆成每場館一組。人工資料優先；標題＋城市＋場館＋場次完全一致的文化部重複會排除。來源使用不同標題／場館名時可能需人工合併；不做可能誤合併的模糊匹配。

前端以Asia/Taipei計算今天，場館選單由所有資料動態產生，城市連動並清除不再合法的場館；城市、場館、演出日期、文字及顯示範圍全部AND。取消活動預設隱藏，可在所有紀錄查看。

## 由單一整合者發布

1. 將本分支 commit cherry-pick 到整合者分支（只有新增檔案）。
2. 檢閱 `integration/live-events.patch`，在最新首頁加入演唱會與脫口秀導覽，將更新步驟整合到同一個每日 workflow，不能另起互相 push main 的排程。因展覽任務正在修改 workflow，patch 僅供參考，需由整合者套用／重寫。
3. 在既有驗證步驟加入 `python -m unittest discover -s tests -p test_live_events.py -v`、`node --check concerts.js`、`node scripts/live_filter_regression.js`。
4. 日更失敗也先持久化兩個公開JSON並部署保留資料／錯誤狀態，之後將workflow標記失敗。将新增JSON加入現有git add；將 `concerts.html comedy.html concerts.js concerts.css` 與兩個公開JSON加入 Pages artifact；不用公開人工資料、link map、原始回應或測試。
5. 如保留頁面中維護說明連結，複製 `docs/CONCERTS.md` 到 `site/docs/`。檢查公開 `/concerts.html`及`/comedy.html`後再統一回報。

## 驗證

6項Python測試涵蓋：多場次／重複、缺票價與開賣、日期異動、場館新增／來源消失、取消資料保留、失敗保留與最後成功日、空／壞資料、安全URL、分類與課程排除。Node遍歷114種所有城市×所有場館組合（含不可能組合），驗證AND、每場日期、搜尋、取消與台灣跨午夜。

手機實際瀏覽器證據將另記錄於 `docs/LIVE_EVENTS_QA.md`，截圖位於 `output/playwright/`。只有人工核對的官方連結提供購票按鈕，不自動測購票流程。
