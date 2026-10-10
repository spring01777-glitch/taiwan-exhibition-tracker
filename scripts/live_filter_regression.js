const assert = require('node:assert/strict');
const fs = require('node:fs');
const {todayTW, venues, matches, sessions, sessionTickets, platforms, facets} = require('../concerts.js');
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
  for(const region of ['',...new Set(events.map(e=>e.region))])for(const venue of ['',...venues(events)])for(const platform of ['',...platforms(events)])for(const date of ['',...new Set(events.flatMap(e=>e.sessions.map(s=>s.date)))]){
    const expected=events.filter(e=>(!region||e.region===region)&&(!venue||e.venue===venue)&&e.sessions.some(s=>(!date||s.date===date)&&(!platform||(platform==='未核對'?!(e.tickets||[]).some(t=>t.sessions.some(q=>q.date===s.date&&(q.time||null)===(s.time||null))):(e.tickets||[]).some(t=>t.platform===platform&&t.sessions.some(q=>q.date===s.date&&(q.time||null)===(s.time||null)))))));
    assert.deepEqual(events.filter(e=>matches(e,{region,venue,platform,date,view:'all'},'2026-10-06')),expected);
    combinations++;
  }
  for(const e of events)for(const s of e.sessions)for(const t of sessionTickets(e,s)){
    assert(t.checkedAt);assert(new URL(t.url).pathname!=='/');assert(!t.url.includes('data.gov.tw'));
    assert(t.sessions.some(q=>q.date===s.date&&(q.time||null)===(s.time||null)));
  }
}
const cancelled={status:'cancelled',region:'X',venue:'Y',title:'test',sessions:[{date:'2030-01-01'}]};
assert(!matches(cancelled,{view:'upcoming'},'2026-10-06'));
assert(matches(cancelled,{view:'all'},'2026-10-06'));
assert(!matches({...cancelled,status:'scheduled'},{region:'X',venue:'Y',query:'test',date:'2030-01-02',view:'all'},'2026-10-06'));
console.log(`PASS ${combinations} region/venue AND combinations, Taiwan midnight, dates, query, cancellation`);

assert(!matches({...cancelled,status:'scheduled',sessions:[{date:'2030-01-01',status:'cancelled'}]},{view:'upcoming'},'2026-10-06'));
const split={status:'scheduled',region:'X',venue:'Y',title:'split',sessions:[{date:'2030-01-01',time:'16:00'},{date:'2030-01-01',time:'19:00'},{date:'2030-01-02',time:'19:00'}],tickets:[{platform:'A',url:'https://a.test/event/1',checkedAt:'2026-10-06',sessions:[{date:'2030-01-01',time:'16:00'}]},{platform:'B',url:'https://b.test/event/1',checkedAt:'2026-10-06',sessions:[{date:'2030-01-01',time:'19:00'}]},{platform:'C',url:'https://c.test/event/1',checkedAt:'2026-10-06',sessions:[{date:'2030-01-01',time:'19:00'}]}]};
assert(!matches(split,{platform:'A',date:'2030-01-02',view:'all'}));
assert.equal(sessions(split,{platform:'B',view:'all'}).length,1);
assert.equal(sessionTickets(split,split.sessions[1]).length,2);
assert.deepEqual(facets([split],{date:'2030-01-02',view:'all'},'platform'),['未核對']);
assert(!matches({...split,sessions:[{date:'2020-01-01'},{date:'2030-01-01'}]},{date:'2020-01-01',view:'upcoming'},'2026-10-06'));
console.log('PASS same-day time scopes, multiple platforms, impossible date/platform, past dates, facets');
const genreEvents=[{status:'scheduled',region:'X',venue:'Y',title:'a',genre:'爵士',sessions:[{date:'2030-01-01',time:null}]},{status:'scheduled',region:'X',venue:'Y',title:'b',genre:'流行／搖滾演唱會',sessions:[{date:'2030-01-01',time:null}]}];
assert.deepEqual(genreEvents.filter(e=>matches(e,{genre:'爵士',view:'all'})).map(e=>e.title),['a']);
assert.deepEqual(require('../concerts.js').sortGenres(facets(genreEvents,{view:'all'},'genre')),['流行／搖滾演唱會','爵士']);
console.log('PASS genre filter and facet order');
