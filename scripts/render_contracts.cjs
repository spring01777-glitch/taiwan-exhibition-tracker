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
 for(const e of data.events){assert.ok(html.includes(e.id));}
 console.log(`${kind}: real renderer produced ${data.events.length} cards, date/venue hierarchy and accessible session details passed.`);
}
(async()=>{await check('concerts');await check('comedy');})().catch(error=>{console.error(error);process.exitCode=1;});
