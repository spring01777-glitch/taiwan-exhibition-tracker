# Live-event source pipeline

This isolated change starts at a0aa768bd03edda68eefec1dde561b7b09e53533,
including 6ea44e5 and 63caf98. It does not change the original checkout,
exhibition files, publication settings, or schedules. No platform web crawler
is enabled. The existing licensed MOC endpoint is the only network adapter.

## Registry and persistence

`data/live-source-registry.json` records source identity, kind, adapter, access
mode, permission state and scope. A visible official page does not establish
permission to automate it. Platform sources currently use `reviewed-json`,
imported from parent cloud research. The satire source URL remains unset until
the parent provides its verified catalog URL. No catalog coverage is guessed.

Each adapter owns `data/live-sources/{concerts|comedy}/{source-id}.json`.
That snapshot holds the source events, last successful time, current attempt
status and per-item decision ledger. Daily builds aggregate the manual source,
MOC and all registered independent snapshots. Unregistered previously published
sources are also retained instead of being silently washed out. Offline rebuilds
keep provider timestamps and never call a platform or MOC endpoint.

Import snapshots and the registry must be committed with the generated public
snapshot during later approved integration. The existing workflow explicitly
stages certain data files; it does not yet stage the new MOC snapshot paths.
Adding `data/live-sources/` to that staging step is a required integration step
before claiming CI persists MOC snapshot history. This task leaves the shared
workflow untouched to respect the instruction to edit only live-event files.
Reviewed platform snapshots are not modified by a daily MOC build; once committed
they are durably read on the next build even with that workflow unchanged.

## Cloud adapter input

The input is a JSON object with:

- `sourceId`: a registered source id, e.g. `tixcraft` or `comedyclub`.
- `kind`: `concerts` or `comedy`.
- `reviewedAt`: the Taiwan review date, preserved separately from the import attempt date (future dates fail).
- `traversal`: `{scope, expectedPageIds, complete}`. Scope describes the actual
  catalog/date/filter range. Page IDs must be unique. `complete:true` alone is
  insufficient: every expected page must have been supplied. Completeness means
  only the named scope, not the whole platform, country or future season.
- `pages`: an array of `{id, url, items}`. Include page two and subsequent pages,
  with real source URLs, rather than only selected interesting entries.
- Each item has `sourceUid`, `evidence`, `officialFactsReviewed` and, if included,
  `event`. Evidence can include title, format, categories, description, performers
  or the cloud-confirmed `reviewedKind`. Evidence/prose is used for classification
  only and does not enter the public event snapshot. Keep summaries independently
  short; never send posters or whole provider descriptions as public facts.
- Event facts: title, region, venue, sourceUrl, sessions (`date`, `time`, optional
  status), optional performers/address/price/saleAt/saleNote/status/summary and
  tickets. Each ticket requires HTTPS detail URL, platform label, checkedAt and
  explicitly matching sessions; price/saleAt are optional. Unknown but explicitly
  verified organizer platforms are allowed. Homepages, unsafe URLs, mismatched
  ticket sessions and unsupported public fields fail the import.

Use the CLI locally (no fetching occurs):

```
python scripts/update_live_events.py --reviewed-input <cloud-reviewed.json> --source-id comedyclub --kind comedy
```

All directory pages should appear in the manifest. Record irrelevant entries too:
classification stores excluded and pending items with fixed reasons. Entries
without sufficient type evidence, or without officially reviewed detail facts,
remain pending. An invalid included fact marks the attempt failed and preserves
the source's entire previous successful event set. Do not make up dates, venues,
ticket links or classification to fill the catalog.

## Counts, classification and reconciliation

`discovered`, `included`, `excluded`, `pending`, `failed` count this attempt's
catalog items (MOC uses provider rows). `reasons` and per-item records make the
decisions inspectable. `retainedEventCount` counts stored event/venue records,
including retained history. Multiple venues, duplicates and past records make
this different from included input items. Null counts mean not yet checked.
`pagesVisited`, `expectedPages`, `scope`, `coverageComplete` and `lastSuccess`
are separate from transport/parse success. A successful response with zero
matches can be reported as such; it never becomes a claim of national coverage.
The live UI exposes these distinctions and does not add a 90-day cutoff.

Classification inspects multiple fields, permits English stand-up evidence and
cloud-reviewed formats for unnamed specials, excludes classes/workshops,
musicals, fan meetings/upgrades and explicitly different comedy formats, and
keeps ambiguous entries pending. Category 11 alone is insufficient evidence.

Reconciliation normalizes 台/臺, Unicode width, punctuation and whitespace before
comparing region and venue. Stable source UID plus place preserves source identity;
cross-source records require matching title or a corroborating official URL and
an overlapping actual session. It unions those sessions/ticket links and preserves
sourceRefs. Same titles at different cities or unrelated dates do not merge.
Session ordering alone does not create a duplicate. Manual records take priority.
Missing entries remain stored; complete scope disappearance marks them unconfirmed,
not cancelled. Failed/partial imports do not delete successful old records.

## Verification and outstanding work

Offline tests cover second-page scope, multi-field and English classification,
unnamed specials, unknown verified platforms, unsafe URLs, source errors,
second rebuild, legacy sources, multi-city additions, session ordering, overlap
deduplication and cross-year dates. Existing sale-time corrections remain tested.

The parent still needs to supply full-catalog coverage/exclusion manifests,
confirm automation permission and scope, and assess included/pending counts
against that inventory. Selected verified batches are imported below; they
do not establish nationwide completeness. Culture Ministry exhibition ValueError and Pier-2 URLError
are separate existing failures and are not fixed by this live-event work.
Cloud browser QA, integration against newer main, and any publication remain
with the parent under the existing approval restrictions.

## Data transfer blocker for the three supplied audits

On 2026-10-06 the formal Library consumer materialization was attempted for
both primary audit ZIPs and the supplementary concert ZIP, each with one retry.
All failed because the current Windows Python runtime lacks os.setxattr; the
required metadata could not be applied/verified. The official helper was not
modified and no fallback download URL or metadata-free artifact was used.
None of those archives was safely materialized, unpacked or imported here.
At that point the supplied aggregate counts were unverified locally. The later
canonical text handoff below resolved the fact import without claiming Library
ZIP materialization.

## Parent text handoff follow-up

The parent subsequently supplied canonical facts directly in task text. This
is a separate evidence handoff and does not change the failed Library byte
materialization history. `--canonical-input FILE --kind concerts --batch-id ID`
adapts a complete JSON batch, groups by reviewed official source host and
imports the persistent snapshots. Counts supplied in the batch must match.
Unknowns stay null; HTML entities in fact text and URLs are decoded. Evidence
URLs, original record IDs, unknown fields and ticket-type facts remain in the
source decision ledger. Actual session scopes/sale times stay on tickets.
Repeated rows of one source detail page union their sessions, with individual
performers/hosts retained in sessionFacts and shown in the session details.

The complete supplementary concert text (15 groups, 23 sessions) is stored in
`data/live-audits/concerts-supplement-20261006.json` and imported into ibon,
ERA and OPENTIX source snapshots. Public concert output is now 39 groups and
51 sessions (previous 24/28 plus 15/23); the comedy output remains 29/39.
Two offline rebuilds/reimports retain the supplement idempotently and keep
review dates at 2026-10-06. tripleS remains scheduled with Xinyu's absence
noted; autumn festival times and all unverified general sale times stay null.

The initial main concert/comedy text contained actual truncation markers and
was not imported. A subsequent complete ten-part handoff for each kind resolved
this blocker, as recorded below. No further ZIP materialization is requested.
The supplied full-catalog coverage/exclusion matrices have also not arrived as
complete text; imported source states therefore explicitly say selected verified
missing items, coverage incomplete, and manual reviewed import, not daily scanning.

## Complete ten-part handoff verified locally

All ten concert parts and ten comedy parts are saved under
`data/live-audits/{concerts|comedy}-primary-parts/`, with validated aggregate
JSON files alongside the supplement. Concert primary contains 46 groups / 71
actual sessions; supplement contains 15 / 23. Together they add 61 / 94 to the
baseline 24 / 28, producing **85 venue records / 122 sessions**. Comedy primary
contains 46 newly verified sessions. Its baseline 29 records / 39 sessions now
produces **60 venue records / 85 sessions** after same-program/place merging.

The explicitly reviewed 藍恩《All Around You》 and 涵冷娜《喊卡之後》 programs
can union disjoint added dates at the same place. The Red House bilingual
second-floor venue name is a narrow verified alias. Different cities/rooms
remain separate. Eight 二三嚴選 sessions share one source detail page/card and
retain each session's performers and host. Individual ticket sale times remain
scoped; early-bird/presale information stays distinct from general sale time.
Cancelled baseline events remain cancelled and unknown conflicting times stay
null. No interpolated BTS date or superseded Charlie Puth venue/date was added.

All 71 Python tests pass, including actual complete-batch imports followed by
two simulated daily MOC rebuilds and a per-session official-URL/place/date match.
224,056 frontend filter combinations pass; real render contracts produce 85
concert and 60 comedy cards; four-page static contracts pass. Strict public
schema/sale-time checks pass with zero sale-time conflicts. Browser/source
research is reserved for the parent cloud environment; no local browser was
opened. This is a local-only delivery with no remote push or publication.
