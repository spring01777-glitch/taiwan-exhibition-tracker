/* A platform and date must match the same session. */
(function(root){
 'use strict';
 const todayTW=(now=new Date())=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
 const platformOf=u=>{try{const h=new URL(u).hostname;return (h.endsWith('.kktix.cc')||h==='kktix.com'||h==='www.kktix.com')?'KKTIX':({'tixcraft.com':'拓元 tixCraft','ticket.com.tw':'年代 ERA','kham.com.tw':'寬宏 KHAM','ticket.ibon.com.tw':'ibon','www.opentix.life':'OPENTIX','opentix.life':'OPENTIX'})[h]||'';}catch{return '';}};
 const tickets=e=>e.tickets||(e.ticketVerifiedAt&&platformOf(e.ticketUrl)?[{url:e.ticketUrl,platform:platformOf(e.ticketUrl),checkedAt:e.ticketVerifiedAt,sessions:e.sessions}]:[]);
 const sessionTickets=(e,s)=>tickets(e).filter(t=>t.checkedAt&&t.sessions?.some(q=>q.date===s.date&&(q.time||null)===(s.time||null)));
 const sessions=(e,f={},today=todayTW())=>e.sessions.filter(s=>(!f.date||s.date===f.date)&&(f.view==='all'||(e.status!=='cancelled'&&s.status!=='cancelled'&&s.date>=today))&&(!f.platform||(f.platform==='未核對'?sessionTickets(e,s).length===0:sessionTickets(e,s).some(t=>t.platform===f.platform))));
 const matches=(e,f={},today=todayTW())=>(!f.region||e.region===f.region)&&(!f.venue||e.venue===f.venue)&&(!f.query||(e.title+' '+(e.performers||'')+' '+e.venue).toLocaleLowerCase().includes(f.query.toLocaleLowerCase()))&&sessions(e,f,today).length>0;
 const venues=(events,region='')=>[...new Set(events.filter(e=>!region||e.region===region).map(e=>e.venue))].sort((a,b)=>a.localeCompare(b,'zh-Hant'));
 const platforms=events=>[...new Set(events.flatMap(e=>e.sessions.flatMap(s=>sessionTickets(e,s).length?sessionTickets(e,s).map(t=>t.platform):['未核對'])))].sort();
 const facets=(events,f,key,today=todayTW())=>{const relaxed={...f,[key]:''};if(key==='region')relaxed.venue='';const eligible=events.filter(e=>matches(e,relaxed,today));return key==='platform'?[...new Set(eligible.flatMap(e=>sessions(e,relaxed,today).flatMap(s=>sessionTickets(e,s).length?sessionTickets(e,s).map(t=>t.platform):['未核對'])))].sort():[...new Set(eligible.map(e=>e[key]))].sort((a,b)=>a.localeCompare(b,'zh-Hant'));};
 const hasSaleTimeConflict=e=>Boolean((e.saleAt||tickets(e).some(t=>t.saleAt))&&/一般開賣[^。；]*(?:未公布|未提供)/.test(e.saleNote||''));
 const saleTimeValue=(e,t)=>hasSaleTimeConflict(e)?'開賣資料矛盾，待官方確認':(t?.saleAt||e.saleAt||'');
 const api={todayTW,venues,matches,sessions,tickets,sessionTickets,platforms,facets,hasSaleTimeConflict,saleTimeValue};
 if(typeof module!=='undefined')module.exports=api;
 root.ConcertFilters=api;
 if(typeof document==='undefined')return;
 const $=id=>document.getElementById(id);
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const safe=u=>{try{const p=new URL(u);return p.protocol==='https:'&&!p.username&&!p.password?esc(p.href):'';}catch{return '';}};
 const link=(u,label)=>safe(u)?`<a href="${safe(u)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`:'';
 const labels={scheduled:'已公告',cancelled:'已取消',rescheduled:'已改期',changed:'來源日期或時間異動',unconfirmed:'來源未再列出・待確認'};
 const time=t=>t?esc(t.replace('T',' ').replace('+08:00',''))+(t.length>10?'（台灣）':''):'未公布／來源未提供';
 const saleTimeDisplay=(e,t)=>hasSaleTimeConflict(e)?esc(saleTimeValue(e,t)):time(saleTimeValue(e,t));
 const ids=['region','venue','platform','date','query','view'];
 let events=[];
 const filters=()=>Object.fromEntries(ids.map(k=>[k,$(k).value.trim()]));
 function options(id,values,first){const selected=$(id).value;const all=selected&&!values.includes(selected)?[selected,...values]:values;$(id).innerHTML=`<option value="">${first}</option>`+all.map(v=>`<option value="${esc(v)}">${esc(v)}${values.includes(v)?'':'（無符合場次）'}</option>`).join('');$(id).value=selected;}
 function render(){
  const f=filters();
  options('region',facets(events,f,'region'),'全台灣');options('venue',facets(events,f,'venue'),'所有場館');options('platform',facets(events,f,'platform'),'所有售票平台');
  const result=events.filter(e=>matches(e,f)).sort((a,b)=>{const s=e=>sessions(e,f).map(v=>v.date+' '+(v.time||'')).sort()[0];return s(a).localeCompare(s(b));});
  $('result-count').textContent=`${result.length} 個活動・${result.reduce((n,e)=>n+sessions(e,f).length,0)} 場次`;
  $('results').innerHTML=result.length?result.map(e=>{
   const shown=sessions(e,f);
   const sessionHtml=shown.map(s=>{const fact=e.sessionFacts?.find(q=>q.date===s.date&&(q.time||null)===(s.time||null));const lineup=fact&&(fact.performers||fact.host)?`<small>本場演出 ${esc(fact.performers||'未列')}；主持 ${esc(fact.host||'未列')}</small>`:'';const ts=sessionTickets(e,s).filter(t=>!f.platform||f.platform==='未核對'||t.platform===f.platform);return `<li><strong>${esc(s.date)} ${esc(s.time||'時間未公布／待確認')}</strong>${s.status?'・'+esc(labels[s.status]||s.status):''}${lineup}<div class="session-links">${ts.length?ts.map(t=>`<div>${link(t.url,t.platform+' 官方活動頁'+(e.cloudReviewPending?'（待雲端複核）':''))}<small>票價 ${esc(t.price||e.price||'未公布／來源未提供')}；開賣 ${saleTimeDisplay(e,t)}；核對 ${esc(t.checkedAt)}</small></div>`).join(''):'<small>本場次售票入口尚未核對</small>'}</div></li>`;}).join('');
   return `<article class="card" data-event-id="${esc(e.id)}"><div class="card-top"><span>${esc(e.region)}</span><span class="status">${esc(labels[e.status]||'待確認')}</span></div><h3>${esc(e.title)}</h3><p class="event-date">${esc(shown[0].date)} ${esc(shown[0].time||'')}<small>${shown.length>1?shown.length+' 個符合場次':'台灣時間'}</small></p><p class="event-venue">${esc(e.venue)}</p><dl><dt>演出者：</dt><dd>${esc(e.performers||'未公布／來源未提供')}</dd><dt>票價：</dt><dd>${esc(e.price||'未公布／來源未提供')}</dd><dt>售票狀態：</dt><dd>${esc(e.ticketStatus||'未公布／來源未提供')}</dd><dt>一般開賣：</dt><dd>${saleTimeDisplay(e)}</dd></dl>${e.saleNote?`<p class="note">${esc(e.saleNote)}</p>`:''}<details class="session-details" ${shown.length===1?'open':''}><summary>查看 ${shown.length} 個場次與售票入口</summary><ul class="sessions" aria-label="演出場次">${sessionHtml}</ul></details><p class="summary">${esc(e.summary)}</p>${e.status!=='scheduled'?`<p class="concert-warning">${esc(e.statusNote||'請至官方來源確認最新異動。')}</p>`:''}${e.revisions?.length?`<details><summary>日期或狀態異動紀錄</summary>${e.revisions.map(r=>`<p class="note">${esc(r.at)}：${esc(r.note)}</p>`).join('')}</details>`:''}<div class="links">${link(e.sourceUrl,(e.sourceUrl||'').includes('data.gov.tw/dataset/')?'資料集來源（非活動詳情）':'官方來源')}</div>${(e.sourceUrl||'').includes('data.gov.tw/dataset/')?`<p class="note">尚未取得可核對的活動詳情或售票頁；上方為資料集來源。資料 UID：${esc(e.sourceUid||'未提供')}</p>`:''}<small>${e.source==='manual'?'人工核對':'文化部公開資料'}・最近確認 ${esc(e.verifiedAt||'尚未確認')}；餘票請見官方。</small></article>`;
  }).join(''):`<p class="empty">沒有符合條件的${document.body.dataset.events?.includes('comedy')?'單口喜劇':'演唱會'}。可清除篩選或查看所有紀錄。</p>`;
 }
 $('filters').addEventListener('submit',e=>e.preventDefault());
 $('filters').addEventListener('input',e=>{if(e.target.id==='region'&&!venues(events,$('region').value).includes($('venue').value))$('venue').value='';render();});
 $('filters').addEventListener('reset',()=>setTimeout(render,0));
 fetch(document.body.dataset.events||'data/concerts.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json();}).then(data=>{
  events=data.events;$('active-count').textContent=events.filter(e=>matches(e,{view:'upcoming'})).length;
  $('updated').textContent='最近產出 '+time(data.updatedAt)+'；非即時票況，人工來源未每日重查';
  const coverageText=s=>s.discovered!==undefined?`<p>本次發現 ${esc(s.discovered??'未核對')}；納入 ${esc(s.included??'未核對')}；排除 ${esc(s.excluded??'未核對')}；待確認 ${esc(s.pending??'未核對')}；失敗 ${esc(s.failed??'未核對')}</p><p>盤點日期 ${esc(s.reviewedAt||'未提供')}；${esc(s.scope||'範圍尚未核對')}；頁面 ${esc(s.pagesVisited??0)}／${esc(s.expectedPages??'未知')}；${s.coverageComplete?'所述範圍分頁完成':'涵蓋尚未完成／未核實'}</p>`:'';
  const stateText=s=>s.status==='ok'?'本次處理完成':s.status==='manual'?'人工維護':s.status==='pending'?'尚待來源核對':'更新失敗／保留舊資料';
  $('source-status').innerHTML=data.sources.map(s=>`<div class="source-row"><div><strong>${esc(s.name)}</strong><p>${esc(s.message)}</p>${coverageText(s)}${s.platform?`<p>已收錄 ${s.eventCount||0} 個活動・${s.sessionCount||0} 場次</p>`:''}<small>${s.status==='manual'?'最近人工查看：'+time(s.checkedAt):'最後成功：'+time(s.lastSuccess)+'；最後嘗試：'+time(s.checkedAt)}</small></div><span class="state ${s.status==='error'?'error':''}">${esc(stateText(s))}</span>${link(s.url,'來源／授權參考')}</div>`).join('');render();
 }).catch(()=>{$('updated').textContent='資料讀取失敗，請稍後重新整理。';$('results').textContent=`無法讀取${document.body.dataset.events?.includes('comedy')?'脫口秀':'演唱會'}資料，請稍後重試。`;});
})(typeof globalThis!=='undefined'?globalThis:this);
