'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {todayTW,isEnded,matchesDates,compareEvents,eventBadge,dateLabel,nextTaiwanDayDelay}=require('../app.js');
const day='2026-11-17';
assert.equal(todayTW(new Date('2026-11-16T15:59:59Z')),'2026-11-16');
assert.equal(todayTW(new Date('2026-11-16T16:00:00Z')),day);
assert.equal(nextTaiwanDayDelay(new Date('2026-11-16T15:59:59Z')),1050);
const base={region:'臺北市',title:'活動',start:'2026-11-01',end:'2026-11-17',firstSeen:'2026-11-17T07:00:00+08:00'};
assert(matchesDates(base,'all',day));
assert(matchesDates(base,'ending',day));
assert(!matchesDates(base,'history',day));
assert(!matchesDates(base,'all','2026-11-18'));
assert(matchesDates(base,'history','2026-11-18'));
assert(isEnded(base,'2026-11-18'));
for(const unknown of [{...base,end:null},{...base,start:null,end:null},{...base,start:null}]){
  assert(matchesDates(unknown,'all',day));
  assert(matchesDates(unknown,'new',day));
  assert(!matchesDates(unknown,'history',day));
  assert(!matchesDates(unknown,'ending',day));
  assert(!matchesDates(unknown,'recommended',day));
  assert(!matchesDates(unknown,'all',day,day)); // Cannot assert an exact visit date.
  assert.equal(eventBadge(unknown,day),'展期待確認');
  assert(dateLabel(unknown).includes('日期待確認'));
}
assert(!matchesDates({...base,start:null,end:'2026-11-16'},'all',day));
assert(matchesDates({...base,start:null,end:'2026-11-16'},'history',day));
const events=[{...base,title:'未知',start:null,end:null},{...base,title:'晚開',start:'2026-11-10'},{...base,title:'早開',start:'2026-11-01'}];
assert.deepEqual(events.slice().sort((a,b)=>compareEvents(a,b)).map(e=>e.title),['早開','晚開','未知']);
for(const view of ['all','history','ending']) assert.doesNotThrow(()=>events.slice().sort((a,b)=>compareEvents(a,b,view)));

// Exercise the real renderer and midnight callback, not just duplicate filter logic.
let now='2026-11-16T15:59:59Z';
class ClockDate extends Date{constructor(...args){super(...(args.length?args:[now]));} static now(){return new Date(now).getTime();}}
const nodes=new Map(), timers=[], listeners={};
function node(){return {value:'',textContent:'',innerHTML:'',hidden:false,append(){},replaceChildren(){},addEventListener(){}};}
const document={getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node,querySelectorAll:()=>[],addEventListener(type,handler){listeners[type]=handler;},hidden:false};
const context=vm.createContext({Date:ClockDate,Intl,console,document,setTimeout:(handler,delay)=>{timers.push({handler,delay});},fetch:()=>new Promise(()=>{})});
vm.runInContext(fs.readFileSync(require.resolve('../app.js'),'utf8'),context);
const fixture={events:[
  {...base,title:'午夜下架',end:'2026-11-16',source:'songshan',sourceVersion:'official-public-incremental',url:'https://www.songshanculturalpark.org/exhibition/activity/test'},
  {...base,title:'未知結束',start:null,end:null,source:'huashan',sourceVersion:'official-public-incremental',url:'https://www.huashan1914.com/exhibition/test'},
]};
context.fixture=fixture;
vm.runInContext('data=fixture;render();',context);
assert(nodes.get('results').innerHTML.includes('午夜下架'));
assert(nodes.get('results').innerHTML.includes('未知結束'));
assert(nodes.get('results').innerHTML.includes('結束日期待確認'));
assert(nodes.get('results').innerHTML.includes('官網增量收錄'));
assert.equal(timers[0].delay,1050);
now='2026-11-16T16:00:00.050Z';
timers.shift().handler();
assert(!nodes.get('results').innerHTML.includes('午夜下架'));
assert(nodes.get('results').innerHTML.includes('未知結束'));
assert.equal(nodes.get('active-count').textContent,1);
assert.equal(fixture.events.length,2); // Hidden, never deleted.
vm.runInContext("view='history';render();",context);
assert(nodes.get('results').innerHTML.includes('午夜下架'));
assert(!nodes.get('results').innerHTML.includes('未知結束'));
now='2026-11-17T16:00:00Z';
listeners.visibilitychange(); // Suspended tab resumes after another midnight.
assert.equal(vm.runInContext('today',context),'2026-11-18');
console.log('PASS exhibition Taiwan midnight, expiry/history, unknown dates, sorting, renderer and resumed-tab refresh');
