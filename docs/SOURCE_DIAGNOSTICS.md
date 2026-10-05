# Source update diagnostics and pending sale-time review

Local-only repair branch: `fix/source-update-diagnostics`, based on public commit `645ef7d77d051b5ed58bcec0876d0113bb62d566`. No source fetch, browser, push, schedule change, or generated snapshot rewrite is part of this repair.

## What the existing CI evidence establishes

Run `37379124688` fetched the Culture Ministry response through verified system curl before a `ValueError`. The old log does not identify the later validation condition. The saved local 302-row snapshot normalizes with zero rejected rows; it is an older response and cannot reproduce the failed run. No payload from that failed run is available locally. A precise causal claim therefore remains pending a cloud-side affected response or the new diagnostics.

Pier-2 failed with `URLError` before a completed detail check. The old checkedCount=12 was inherited from a previous success. The old exception loses the underlying network cause and preparation stage, so neither DNS nor TLS nor robots/policy fetch failure can be established from it.

## Diagnostics contract

Culture Ministry status now records `failureStage`, a sanitized `reasonCode`, and `attemptCounts`. Counts distinguish input rows, valid rows, rejected rows, and deduplicated event/venue records. One row can produce multiple venues; duplicate input rows can produce one event. `rejectedReasons` contains fixed reason categories only. `previousActiveCount` accompanies the loss guard. Null counts mean the current response has not been decoded/normalized, rather than a zero-event response. Existing top-level count/rejected and lastSuccess remain last-success values after failure.

The existing safeguards remain: empty/non-list/no-valid input fails; over 20% rejected rows fails; fewer than half of more than 20 previous active events fails. Source failures retain the previous Culture Ministry events. The verified curl fallback uses default TLS verification and ignores curl configuration files; it never disables certificate verification. Its final failure now preserves the actual decode/transport exception instead of replacing it with the first Python TLS exception.

Venue status records robots-fetch, robots-check, policy-fetch, policy-check, browser-start, list-fetch, list-parse, detail-cap, detail-fetch, detail-parse, or loss-guard. `checkedCount` counts successful current detail parses; `attemptedCount` counts current detail fetch attempts. `lastSuccessfulCheckedCount` is separate historical context, and `lastSuccess` stays unchanged after failure. Even a partial update failure retains the entire prior snapshot. Robots restrictions, reviewed policy hashes, verified TLS, request pacing, detail cap, and loss protection remain enforced.

Safe network classifications include TLS_CERTIFICATE_VERIFICATION, TLS_ERROR, DNS_FAILURE, TIMEOUT, CONNECTION_REFUSED, HTTP_n and NETWORK_ERROR. Raw exception messages, response content and credentials are not emitted. These codes classify evidence; they do not guess a cause where the old logs lack it.

## Five contradictory sale-time claims requiring cloud official review

Each following record has a saleAt value but the note says the general sale time is unpublished/not supplied. The copied saleAt in ticket entries and their checkedAt date are existing claims, not independent evidence proving that sale time. There is no captured official quote locally establishing these times. Preserve the raw fields until the parent cloud browser checks the official pages. The frontend marks both event-level and session ticket sale times as awaiting confirmation.

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
`python scripts/validate_live_events.py --strict-sale-times` intentionally fails while contradictory records remain. Run after cloud review and correction to require zero conflicts.
`node scripts/render_contracts.cjs` executes the actual cards without a browser and verifies both sale-time defenses and retained notes.
`node scripts/live_filter_regression.js` and `python scripts/validate_site_structure.py` cover filters and page structure.

Cloud browser QA and fresh source verification remain with the parent; this local task does not claim mobile browser coverage.
