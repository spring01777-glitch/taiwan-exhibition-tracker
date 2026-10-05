# Source update diagnostics and pending sale-time review

Local-only repair branch: `fix/source-update-diagnostics`, based on public commit `645ef7d77d051b5ed58bcec0876d0113bb62d566`. The initial diagnostic repair did not rewrite snapshots. Its follow-up applies parent-supplied cloud official review to the manual source and rebuilds only comedy.json offline. No local source fetch, browser, push or schedule change is part of either repair.

## What the existing CI evidence establishes

Run `37379124688` fetched the Culture Ministry response through verified system curl before a `ValueError`. The old log does not identify the later validation condition. The saved local 302-row snapshot normalizes with zero rejected rows; it is an older response and cannot reproduce the failed run. No payload from that failed run is available locally. A precise causal claim therefore remains pending a cloud-side affected response or the new diagnostics.

Pier-2 failed with `URLError` before a completed detail check. The old checkedCount=12 was inherited from a previous success. The old exception loses the underlying network cause and preparation stage, so neither DNS nor TLS nor robots/policy fetch failure can be established from it.

## Diagnostics contract

Culture Ministry status now records `failureStage`, a sanitized `reasonCode`, and `attemptCounts`. Counts distinguish input rows, valid rows, rejected rows, and deduplicated event/venue records. One row can produce multiple venues; duplicate input rows can produce one event. `rejectedReasons` contains fixed reason categories only. `previousActiveCount` accompanies the loss guard. Null counts mean the current response has not been decoded/normalized, rather than a zero-event response. Existing top-level count/rejected and lastSuccess remain last-success values after failure.

The existing safeguards remain: empty/non-list/no-valid input fails; over 20% rejected rows fails; fewer than half of more than 20 previous active events fails. Source failures retain the previous Culture Ministry events. The verified curl fallback uses default TLS verification and ignores curl configuration files; it never disables certificate verification. Its final failure now preserves the actual decode/transport exception instead of replacing it with the first Python TLS exception.

Venue status records robots-fetch, robots-check, policy-fetch, policy-check, browser-start, list-fetch, list-parse, detail-cap, detail-fetch, detail-parse, or loss-guard. `checkedCount` counts successful current detail parses; `attemptedCount` counts current detail fetch attempts. `lastSuccessfulCheckedCount` is separate historical context, and `lastSuccess` stays unchanged after failure. Even a partial update failure retains the entire prior snapshot. Robots restrictions, reviewed policy hashes, verified TLS, request pacing, detail cap, and loss protection remain enforced.

Safe network classifications include TLS_CERTIFICATE_VERIFICATION, TLS_ERROR, DNS_FAILURE, TIMEOUT, CONNECTION_REFUSED, HTTP_n and NETWORK_ERROR. Raw exception messages, response content and credentials are not emitted. These codes classify evidence; they do not guess a cause where the old logs lack it.

## Historical five contradictory sale-time claims (resolved below)

Each following record has a saleAt value but the note says the general sale time is unpublished/not supplied. The copied saleAt in ticket entries and their checkedAt date are existing claims, not independent evidence proving that sale time. There is no captured official quote locally establishing these times. These were the pre-review claims. The parent cloud browser supplied official review on 2026-10-06; the outcome below supersedes them. The defensive frontend remains available for future contradictory claims.

### manual-taichung-live

- Title: 第一超棒臺中脫口秀
- Claimed saleAt: `2026-09-24T00:00:00+08:00`
- Existing note: 一般開賣時間未公布／來源未提供。
- Source: https://comedyclub.kktix.cc/events/taichungcomedylive1107
- Ticket claim: https://comedyclub.kktix.cc/events/taichungcomedylive1107; checkedAt=2026-10-06; saleAt=2026-09-24T00:00:00+08:00; sessions=[{"date": "2026-11-07", "time": "19:00"}]

### manual-taipei-live

- Title: TAIPEI COMEDY LIVE!!!
- Claimed saleAt: `2026-01-05T00:00:00+08:00`
- Existing note: 一般開賣時間未公布／來源未提供。
- Source: https://comedyclub.kktix.cc/events/taipeicomedylive1023
- Ticket claim: https://comedyclub.kktix.cc/events/taipeicomedylive1023; checkedAt=2026-10-06; saleAt=2026-01-05T00:00:00+08:00; sessions=[{"date": "2026-10-23", "time": "22:00"}]

### manual-john

- Title: 黃豪平單口喜劇專場：只是喜劇演員
- Claimed saleAt: `2026-10-04T12:30:00+08:00`
- Existing note: 一般開賣時間未公布／來源未提供。
- Source: https://comedyclub.kktix.cc/events/smaljohncomedy20261127
- Ticket claim: https://comedyclub.kktix.cc/events/smaljohncomedy20261127; checkedAt=2026-10-06; saleAt=2026-10-04T12:30:00+08:00; sessions=[{"date": "2026-11-27", "time": "19:30"}]
- Ticket claim: https://comedyclub.kktix.cc/events/smaljohncomedy20261129; checkedAt=2026-10-06; saleAt=2026-10-04T12:30:00+08:00; sessions=[{"date": "2026-11-29", "time": "19:30"}]

### manual-coldn

- Title: 涵冷娜脫口秀專場《喊卡之後》封箱巡迴
- Claimed saleAt: `2026-10-04T12:30:00+08:00`
- Existing note: 一般開賣時間未公布／來源未提供。
- Source: https://comedyclub.kktix.cc/events/coldn20261126
- Ticket claim: https://comedyclub.kktix.cc/events/coldn20261126; checkedAt=2026-10-06; saleAt=2026-10-04T12:30:00+08:00; sessions=[{"date": "2026-11-26", "time": "19:30"}]

### manual-creepy

- Title: 2026 台北喜劇節：怪奇誤語
- Claimed saleAt: `2026-10-01T00:00:00+08:00`
- Existing note: 一般開賣時間未公布／來源未提供。
- Source: https://comedyclub.kktix.cc/events/creepy1127
- Ticket claim: https://comedyclub.kktix.cc/events/creepy1127; checkedAt=2026-10-06; saleAt=2026-10-01T00:00:00+08:00; sessions=[{"date": "2026-11-27", "time": "20:00"}]

## Verification commands

`python -m unittest discover -s tests -v` (offline; Windows tempfile tests may require the formal execution permission path).
`python scripts/validate_live_events.py` checks public schema and explicitly reports conflict IDs. Schema validity does not establish factual correctness.
`python scripts/validate_live_events.py --strict-sale-times` requires zero conflicts; after the cloud-reviewed source correction it passes. It intentionally fails if contradictory claims recur.
`node scripts/render_contracts.cjs` executes the actual cards without a browser and verifies both sale-time defenses and retained notes.
`node scripts/live_filter_regression.js` and `python scripts/validate_site_structure.py` cover filters and page structure.

Official sale-time verification was performed by the parent cloud browser and supplied to this local task; no additional local browser/source verification occurred. Cloud browser QA remains with the parent; this local task does not claim mobile browser coverage. Culture Ministry and Pier-2 source errors are not resolved by the sale-note correction.

## Cloud official review applied on 2026-10-06

The parent supplied these findings from the official KKTIX pages listed above. Existing verifiedAt and ticket checkedAt dates remain 2026-10-06. The source manual and the generated comedy snapshot now agree:

- manual-taipei-live: general NT$350 tickets start 2026/01/05 00:00 Taiwan time. Preserve event and ticket saleAt; replace the unpublished note with the confirmed general-sale fact.
- manual-coldn: regular NT$800, sponsor NT$1,200 and VIP NT$5,000 tickets all start 2026/10/04 12:30 Taiwan time. Preserve event and ticket saleAt; clarify all three categories in the note.
- manual-creepy: general NT$450 tickets start 2026/10/01 00:00 Taiwan time. Preserve event and ticket saleAt; replace the unpublished note.
- manual-taichung-live: 2026/09/24 00:00 Taiwan time is the early-bird sale, not an established general sale. Set event and all ticket saleAt to null, retain that early-bird start in the note, state general-sale time not supplied, and relabel NT$450 as early bird (onsite NT$500).
- manual-john: both Nov 27 and Nov 29 pages confirm added-show early bird from 2026/10/04 12:30 to 2026/10/30 12:30 Taiwan time. Set event and both ticket saleAt to null and preserve the early-bird window in the note. General full-price sale start remains unconfirmed; do not infer it from early-bird closing time.

These corrections address sale classification and contradictory notes only. They do not establish live inventory or repair the Culture Ministry/Pier-2 network/validation failures.
