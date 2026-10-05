const assert = require('node:assert/strict');
const fs = require('node:fs');
const {todayTW, venues, matches} = require('../concerts.js');
assert.equal(todayTW(new Date('2026-10-05T16:30:00Z')),'2026-10-06');
let combinations=0;
for (const kind of ['concerts','comedy']) {
  const {events} = JSON.parse(fs.readFileSync(`data/${kind}.json`,'utf8'));
  assert.equal(new Set(events.map(e=>e.id)).size,events.length);
  for (const region of ['', ...new Set(events.map(e=>e.region))]) {
    const allVenues=venues(events,region);
    assert.deepEqual(new Set(allVenues),new Set(events.filter(e=>!region||region===e.region).map(e=>e.venue)));
    for (const venue of ['',...venues(events)]) {
      const result=events.filter(e=>matches(e,{region,venue,view:'all'},'2026-10-06'));
      assert.deepEqual(result,events.filter(e=>(!region||region===e.region)&&(!venue||venue===e.venue)));
      combinations++;
    }
  }
  for (const e of events) {
    for (const s of e.sessions) assert(matches(e,{date:s.date,view:'all'},'2026-10-06'));
    assert(!matches(e,{date:'1900-01-01',view:'all'},'2026-10-06'));
    assert(matches(e,{query:e.title.slice(0,4),view:'all'},'2026-10-06'));
    assert(!matches(e,{query:'does-not-exist-xyz',view:'all'},'2026-10-06'));
  }
}
const cancelled={status:'cancelled',region:'X',venue:'Y',title:'test',sessions:[{date:'2030-01-01'}]};
assert(!matches(cancelled,{view:'upcoming'},'2026-10-06'));
assert(matches(cancelled,{view:'all'},'2026-10-06'));
assert(!matches({...cancelled,status:'scheduled'},{region:'X',venue:'Y',query:'test',date:'2030-01-02',view:'all'},'2026-10-06'));
console.log(`PASS ${combinations} region/venue AND combinations, Taiwan midnight, dates, query, cancellation`);

assert(!matches({...cancelled,status:'scheduled',sessions:[{date:'2030-01-01',status:'cancelled'}]},{view:'upcoming'},'2026-10-06'));
