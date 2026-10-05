# 資料來源查證 · 2026-10-05

## 文化部：自動更新（已實際成功）

- 資料集：https://data.gov.tw/dataset/6012
- JSON：https://cloud.culture.tw/frontsite/trans/SearchShowAction.do?method=doFindTypeJ&category=6
- API 文件：https://cloud.culture.tw/frontsite/trans/SearchShowAction.do?method=doFindTypeJOpenApi&category=6
- 來源文化部；資料集標示免費、每1日更新、政府資料開放授權條款第1版：https://data.gov.tw/license 。網站 footer 區顯名與標示修改；資料欄位保留原始 version。
- 本機實測 HTTP 200，302 筆，約496KB，欄位 showInfo/time/endTime/locationName/price 等。未使用 hitRate 推斷熱門度。
- 單次來源抓取、三次上限重試；不逐筆抓詳情，減少負載。週期建議每日一次。

## 松山文創園區：固定來源，人工事實核對

https://www.songshanculturalpark.org/exhibition

官網 footer 為 All Rights Reserved，未找到明確開放資料授權或官方公開 API。這不是確認禁止所有事實整理，也不應被當成再利用文案或海報的授權。本次整理16筆活動名稱、日期、地點、價格等事實，摘要自行撰写並連回詳情。後續若需要全量每日抓取，先確認服務条款、robots、官方資料介面或取得授權，再增加獨立 adapter，做頁面結構契約測試與失敗保留，不以未確認的隱藏 API 為依賴。

重要：首頁行事曆和 exhibition 列表有不同日期，核對各展演詳情頁的日期；MVP 不以首頁的擴展顯示區間取代展期。

## 華山1914：固定來源，人工事實核對

https://www.huashan1914.com/exhibition

官網 footer 同樣版權保留，未找到明確開放資料授權或公開 API。MVP 含核對過的玩具創作大展與光華攝影展基本事實、本站摘要、官網詳情連結。價格未公佈數值時不推測。全量自動更新的前置條件同松菸。

## 避免誤導

場館狀態標「人工核對」，不偽裝每日自動抓取。文化部 API 可能另外收錄場館活動，但無法保證完整。來源失敗保存最後成功資料；來源暫時消失的條目標示「來源本次未提供」，已結束活動移入前端歷史視圖。名稱、展期或票價改動保存於每筆 revisions，維持原首次收錄日。沒有人氣排序、海報代理、AI API 或付費抓取平台。


## 2026-10-05本次官網核對增補

本次已逐筆閱讀松菸16筆、華山18筆、駁二12筆官方詳情，完整事實與自寫摘要見[核對清單](VENUE_REVIEW.md)。華山8筆日期與歷史分類矛盾，均明示待確認。先前4筆MVP人工資料已被本次清單取代。文化部仍每日更新，場館核對時間不隨文化部更新而變更。

駁二官方入口：https://pier2.org/exhibition/ ，條款：https://pier2.org/privacy/ 。實際近期清單透過正常瀏覽器公開頁面讀取，不另呼叫內部API；12筆詳情日期與票價已核對。駁二保留版權，沒有推定海報或全文開放授權。本次只使用基本事實與本站自寫摘要。

松菸robots允許公開頁面；華山robots限制query路徑與API。本次人工閱讀列表，僅以無query官方詳情頁核對，不實作每日query抓取。駁二robots讀取回404，未據此推定API或大量抓取授權。每日場館爬蟲未實作，遵照這輪優先單次整理的要求。
