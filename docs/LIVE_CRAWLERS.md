# 演唱會／脫口秀自動擷取來源

`scripts/crawl_live_sources.py` 每日台灣09:00由同一 workflow 執行，之後 `update_live_events.py` 重建 `data/concerts.json`、`data/comedy.json`。只納入沒有 API、但有公開結構化資料或公開頁面、且 robots.txt 允許的低風險來源。

| 來源 | 讀取內容 | 類別 | 限制 |
| --- | --- | --- | --- |
| 卡米地 `comedyclub.kktix.cc` | 主辦公開 `events.json`（最新100筆） | 脫口秀 | 多日總覽頁排除；標題／簡介沒有明確單口、脫口秀字樣者列待分類，不發布 |
| 薩泰爾 `strnetwork.kktix.cc` | 主辦公開 `events.json` | 脫口秀 | 同上；地址沒有縣市的英文場地列待分類 |
| 臺北小巨蛋 `arena.taipei` | 「已公開(售票/派票)活動」政府開放資料 JSON | 演唱會 | 場次取開演時間，不取入場／結束時間；售票系統只記名稱 |
| 北流 `tmc.taipei` | 「最近活動」公開頁＋各活動頁 | 演唱會 | 只讀標記為演唱會／中心自辦／合辦的卡片；超過兩天的日期區間不推定場次 |
| OPENTIX `opentix.life` | 公開 sitemap＋活動頁 schema.org Event（每場一筆） | 演唱會、脫口秀 | 只抓新增：sitemap 中第一次出現的活動頁才讀取（新上架優先），已讀過的不重抓，場次全部過去的活動不收錄也不再讀（sitemap 的 lastmod 幾乎每天變動，不用來判斷異動）。代價：已收錄活動之後若改期或加場，OPENTIX 部分不會自動更新；每日最多100頁；快取存在 `data/live-sources/crawl-state.json`，不存簡介文字 |

不自動化：拓元、ibon、年代、寬宏（條款或防機器人機制限制）、KKTIX 總站（Cloudflare 阻擋）。這些來源仍用人工核對匯入（`--reviewed-input`／`--canonical-input`）。

## 安全與資料規則

- 只發 HTTPS GET 到登記的固定主機；拒絕跨主機轉址、帳密網址；單次回應上限5MB。
- 每個來源先讀 robots.txt（404 視為無限制），不允許的網址不讀。每次請求間隔1.2秒。
- 分類沿用 `live_sources.classify`；課程、音樂劇、歌劇（含歌仔戲團名）、相聲、即興等排除，證據不足列「待分類」，不發布。
- 已過期場次不新增。來源本次沒列出的舊資料保留，不推定取消。
- 與既有人工核對紀錄同一活動（相同ID，或標題正規化相同且日期重疊）時，只更新標題外的場次與網址；人工核對的票價、開賣時間、備註、購票連結保留。
- 單一來源失敗、無效紀錄超過20%、或納入數比上次自動更新少一半以上（上次至少6筆）時，該來源保留最後成功快照並標示錯誤；其他來源照常更新。workflow 仍部署保留資料，最後以失敗結束提醒。

## 場館展覽（松菸、華山、駁二）

`update_venue_sources.py` 同時修正：官網只給單一日期時視為單日活動；單筆官網頁資訊不完整（例如沒有地點）時跳過該筆並記入 `skipped`，不再讓整個來源失敗，跳過超過20%才視為來源失敗。

## 本機執行

```bash
python scripts/crawl_live_sources.py                 # 全部來源
python scripts/crawl_live_sources.py --source tmc    # 單一來源
python scripts/update_live_events.py                 # 重建公開 JSON
python -m unittest tests.test_live_crawl -v          # 離線測試，不連網
```
