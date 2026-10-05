# 演唱會／脫口秀驗證證據

2026-10-06 台灣時間，本任務獨立 checkout 驗證；尚未部署公開站。

- `python -m unittest discover -s tests -p test_live_events.py -v`：6/6通過。Windows沙盒下Python tempfile子目錄ACL曾失敗；同一測試在允許的本任務執行環境重跑通過，未改安全設定。Linux workflow 可正常使用標準tempfile。
- `node --check concerts.js`、`node --check scripts/live_browser_qa.js`、Python py_compile：通過。
- `node scripts/live_filter_regression.js`：114個城市×場館組合（包含全台／全部及不可能組合）AND、日期、搜尋、取消、單場取消、台灣跨午夜通過。
- `python scripts/update_live_events.py`：實際網路讀取成功。演唱會最後成功 `2026-10-06T00:40:47+08:00`；綜藝最後成功 `2026-10-06T00:40:48+08:00`。文化部演唱會12個活動／場館組合13場，加人工2組3場後共14組16場；綜藝0個符合名稱的脫口秀，自訂人工6組6場。
- 演唱會11/14組有核對的官方活動購票頁；脫口秀6/6有核對的官方活動購票頁。另3組（Novelbright／謝雷／蔡義德）本次官方售票頁无法開啟確認，沒有公開猜造連結，只提供文化部來源與「購票入口未核對」。所有核對是本次人工確認，非即時票況。
- Playwright Chromium實際手機視窗390×844，`scripts/live_browser_qa.js`遍歷全部有效城市／場館，逐一比對卡片與JSON，同時測日期＋搜尋、空結果、reset。結果：

```json
[
  {"kind":"concerts","cities":6,"pairs":11,"events":14,"width":{"view":390,"scroll":375},"dateSearchReset":"pass"},
  {"kind":"comedy","cities":4,"pairs":5,"events":6,"width":{"view":390,"scroll":375},"dateSearchReset":"pass"}
]
```

無水平溢出；每個input/button與購票入口至少44px。手機截圖已保留在此checkout（output為既有gitignore）：`output/playwright/concerts-mobile.png`、`comedy-mobile.png`、`concerts-mobile-filters.png`、`comedy-mobile-filters.png`。沒有登入或操作購票表單。初始favicon 404已用本頁data favicon修正。

重現：在checkout啟動 `python -m http.server 8876 --bind 127.0.0.1`，用Playwright CLI開頁並`resize 390 844`，Windows以以下命令執行：

```powershell
$qaCode = (Get-Content -Raw -Encoding utf8 scripts/live_browser_qa.js) -replace '\r?\n',' '
npx --yes @playwright/cli -s=liveqa run-code $qaCode
```

本機瀏覽器驗證在新增專區範圍；未重跑其他展覽模組測試、未改現有workflow，也沒有建立第二個部署排程。整合後由整合者跑整站驗證與確認正式網址。


## 主專案整合驗證（2026-10-06）

已合併到展覽專案；同一個每日工作更新文化部演唱會／明確脫口秀資料，並一起部署。主專案38個Python測試通過（含其他展覽與來源恢復測試），Node 114組AND篩選通過。1440px及390px實際瀏覽器核對演唱會11組、脫口秀5組地區場館組合，日期＋搜尋＋reset、首頁導覽及無水平溢位通過。未核對的三組演唱會明示資料集入口與UID，不顯示售票按鈕。

實際點擊：Paul Gilbert主辦KKTIX頁、藍恩卡米地KKTIX頁皆回200且活動名稱相符。拓元F✦FOREVER頁在自動瀏覽器驗收回403；未繞過、登入或操作購票，停止對該平台的重試。此前人工核對的官方連結保留，不能宣稱所有售票頁在所有瀏覽器皆可開啟。演唱會與脫口秀只更新授權文化部資料，售票頁與主辦公告仍為人工核對、非即時票況。
