# Local integration handoff

Base: a0aa768 (original checkout unchanged). Apply the entire isolated branch
range a0aa768..HEAD in order: ee15e99, 8dd72be, 74dbe51, then the final workflow
and coverage follow-up. The original source-diagnostics and sale corrections
6ea44e5 / 63caf98 are already ancestors and must remain.

The remote workflow was read through the connected GitHub app on 2026-10-06,
blob dc9a8cf3be1c6ab46be2abda91f6b1d1d3a46fa8. Its only local difference is
adding data/live-sources/ to the persist step's git add. Schedules, permissions,
action SHAs, deployment and source-failure reporting remain identical. These
source snapshots are internal CI persistence, not added to the Pages artifact.

Coverage now records all 12 registered sources. Each available kind snapshot
lists real reviewed official detail URLs, date range, stored venue/session
counts, latest import decisions and review/import times. Missing snapshots,
catalog totals, unreviewed item counts and full exclusion matrices stay unknown.
Input batches are explicitly not platform catalog pages. The licensed MOC
endpoint remains the sole daily network adapter.

Two complete local offline rebuilds retained concerts 85 records / 122 sessions
and comedy 60 / 85; strict sale-time conflicts remain zero. The actual-batch
regression also imports and rebuilds across two simulated later days. Frontend
scope rendering and all four page contracts pass without opening a local browser.

Before publication: preserve any newer remote commits through normal merge,
run tests and public-data checks, obtain accepted publication approval and use
only the existing HI Git authentication. Never force push or bypass a rejection.
After publication: observe the exact deployed commit's Actions terminal state
and have parent cloud perform desktop/mobile browser QA. If data update fails
while retained-data Pages deployment succeeds, report both outcomes separately.

The private cloud preview ZIP contains only website assets, public data and the
linked public docs/CONCERTS.md page. It excludes Git, workflows, scripts, audit
packs, credentials and internal source snapshots. Saving it in Library is not
browser acceptance: consumer materialization/preview limitations still apply.
