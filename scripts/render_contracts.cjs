/* Execute real card renderers without a browser; check interaction markup. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
async function check(kind){
 const data=JSON.parse(fs.readFileSync(path.join(root,'data',kind+'.json'),'utf8'));
 const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{value:id==='view'?'all':'',innerHTML:'',textContent:'',addEventListener(){}});return elements.get(id);};
 const sandbox={document:{body:{dataset:{events:'data/'+kind+'.json'}},getElementById:element},fetch:async()=>({ok:true,json:async()=>data}),URL,Intl,Date,console,setTimeout};
 vm.runInNewContext(fs.readFileSync(path.join(root,'concerts.js'),'utf8'),sandbox);
 await new Promise(resolve=>setImmediate(resolve));
 const html=element('results').innerHTML;
 assert.equal((html.match(/data-event-id=/g)||[]).length,data.events.length);
 assert.equal((html.match(/class="event-date"/g)||[]).length,data.events.length);
 assert.equal((html.match(/class="event-venue"/g)||[]).length,data.events.length);
 assert.equal((html.match(/class="session-details"/g)||[]).length,data.events.length);
 assert.ok(!html.includes('undefined'));
 const api=sandbox.ConcertFilters;
 for(const e of data.events){
  assert.ok(html.includes(e.id));
  if(kind==='comedy'&&['manual-taipei-live','manual-coldn','manual-creepy','manual-taichung-live','manual-john'].includes(e.id)){
   const card=html.split(`data-event-id="${e.id}"`)[1].split('</article>')[0];
   assert.equal(api.hasSaleTimeConflict(e),false);
   assert.ok(!card.includes('開賣資料矛盾，待官方確認'));
   assert.ok(card.includes(e.saleNote));
   if(e.saleAt)assert.ok(card.includes(e.saleAt.replace('T',' ').replace('+08:00','')));
   else{
    assert.ok(card.includes('早鳥'));
    assert.ok(card.includes(e.id==='manual-taichung-live'?'2026/09/24 00:00':'2026/10/30 12:30'));
    assert.equal(e.saleAt,null);
    assert.ok(api.tickets(e).every(t=>t.saleAt===null));
   }
  }
  if(api.hasSaleTimeConflict(e)){
   const card=html.split(`data-event-id="${e.id}"`)[1].split('</article>')[0];
   assert.ok(card.includes('開賣資料矛盾，待官方確認'));
   assert.ok(card.includes(e.saleNote));
   for(const value of [e.saleAt,...api.tickets(e).map(t=>t.saleAt)].filter(Boolean)){
    assert.ok(!card.includes(value.replace('T',' ').replace('+08:00','')));
   }
  }
 }
 const claim={saleAt:'2026-10-04T12:30:00+08:00',saleNote:'一般開賣時間未公布／來源未提供。',tickets:[]};
 assert.equal(api.hasSaleTimeConflict(claim),true);
 assert.equal(api.saleTimeValue(claim),'開賣資料矛盾，待官方確認');
 assert.equal(api.hasSaleTimeConflict({...claim,saleNote:''}),false);
 assert.equal(api.saleTimeValue({...claim,saleNote:''}),claim.saleAt);
 assert.equal(api.hasSaleTimeConflict({...claim,saleAt:null,tickets:[{saleAt:claim.saleAt}]}),true);
 console.log(`${kind}: real renderer produced ${data.events.length} cards, date/venue hierarchy and accessible session details passed.`);
}
(async()=>{await check('concerts');await check('comedy');})().catch(error=>{console.error(error);process.exitCode=1;});
