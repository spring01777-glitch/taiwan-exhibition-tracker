'use strict';
const todayTW = (now=new Date()) => new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
let today = todayTW();
const $ = id => document.getElementById(id);
let data, view = 'all', limit = 24;
const escapeHTML = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const hasDate = d => typeof d==='string' && /^\d{4}-\d{2}-\d{2}$/.test(d);
const days = (d, day=today) => hasDate(d) ? Math.round((Date.parse(d+'T00:00:00+08:00')-Date.parse(day+'T00:00:00+08:00'))/86400000) : NaN;
const isEnded = (event, day=today) => hasDate(event.end) && event.end<day;
const matchesDates = (event, selectedView='all', day=today, selectedDate='') => {
  if(selectedDate && (!hasDate(event.start) || !hasDate(event.end) || event.start>selectedDate || event.end<selectedDate)) return false;
  if(selectedView==='history') return isEnded(event,day);
  if(isEnded(event,day)) return false;
  if(selectedView==='new') return event.firstSeen?.slice(0,10)===day;
  if(selectedView==='ending') return hasDate(event.start) && hasDate(event.end) && event.start<=day && days(event.end,day)<=14;
  if(selectedView==='recommended') return hasDate(event.start) && hasDate(event.end) && days(event.start,day)<=30 && !event.missingFromSource && !event.verificationNote;
  return true;
};
const dateLabel = event => `${hasDate(event.start) ? event.start : '開始日期待確認'} — ${hasDate(event.end) ? event.end : '結束日期待確認'}`;
const nextTaiwanDayDelay = (now=new Date()) => Date.parse(todayTW(now)+'T00:00:00+08:00')+86400000-now.getTime()+50;
const localTime = t => t ? new Date(t).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}) : '尚無成功更新';
const northRank = e => e.region === '臺北市' ? 0 : e.region === '新北市' ? 1 : 2;
const compareEvents = (a,b,selectedView='all') => selectedView==='history' ? String(b.end || '').localeCompare(String(a.end || '')) : selectedView==='ending' ? String(a.end || '9999-12-31').localeCompare(String(b.end || '9999-12-31'))||northRank(a)-northRank(b) : northRank(a)-northRank(b)||String(a.start || '9999-12-31').localeCompare(String(b.start || '9999-12-31'))||String(a.title || '').localeCompare(String(b.title || ''),'zh-TW');
const eventBadge = (event, day=today) => event.verificationNote ? '狀態待確認' : isEnded(event,day) ? '已結束' : !hasDate(event.start) || !hasDate(event.end) ? '展期待確認' : event.start>day ? '即將開展' : days(event.end,day)<=14 ? '即將結束' : '展期內';
const names = {moc:'文化部',songshan:'松山文創園區',huashan:'華山1914',pier2:'駁二藝術特區'};
const links = {moc:'https://data.gov.tw/dataset/6012',songshan:'https://www.songshanculturalpark.org/exhibition',huashan:'https://www.huashan1914.com/exhibition',pier2:'https://pier2.org/exhibition/'};
const matchesRegion = (event, region) => !region || (region==='north' ? northRank(event)<=1 : event.region===region);
function syncParkOptions(region){
  const select=$('park'), previous=select.value;
  const locations=data.events.filter(e=>matchesRegion(e,region)).flatMap(e=>e.locations || []);
  const available=new Map(locations.map(location=>[location.id,location]));
  const all=document.createElement('option');
  all.value='';all.textContent='所有場館';all.defaultSelected=true;
  select.replaceChildren(all);
  [...available.values()].sort((a,b)=>a.name.localeCompare(b.name,'zh-TW') || a.region.localeCompare(b.region,'zh-TW')).forEach(location=>{
    const option=document.createElement('option');
    option.value=location.id;option.textContent=`${location.name}（${location.region}）`;
    select.append(option);
  });
  select.value=available.has(previous) ? previous : '';
  return Boolean(previous && !available.has(previous));
}
const notes = {all:'顯示尚未結束或結束日期待確認的活動；不代表今日一定開館。',new:'依本站首次收錄日期（台灣時間）顯示，首批匯入會一併列為新增。',recommended:'展期與未來30天重疊、資料來源仍提供的展覽，優先台北／新北與較近開展日；非人氣排名。',ending:'目前展期內，且未來14天內結束。',history:'已結束的展覽持續保留；歷史從本站開始收錄累積。'};
function render(){
  today=todayTW();
  $('active-count').textContent=data.events.filter(e=>!isEnded(e) && !e.verificationNote).length;
  $('new-count').textContent=data.events.filter(e=>matchesDates(e,'new')).length;
  limit = Math.max(limit,24);
  const region=$('region').value, clearedPark=syncParkOptions(region);
  const date=$('date').value, park=$('park').value, query=$('query').value.trim().toLowerCase();
  let events=data.events.filter(e => {
    if(!matchesRegion(e,region)) return false;
    if(park && !e.locations?.some(location=>location.id===park)) return false;
    if(!matchesDates(e,view,today,date)) return false;
    if(query && !`${e.title} ${e.venue} ${e.address} ${e.category}`.toLowerCase().includes(query)) return false;
    return true;
  });
  events.sort((a,b)=>compareEvents(a,b,view));
  $('view-note').textContent=notes[view];
  $('result-count').textContent=`找到 ${events.length} 場展覽${events.length>limit ? `，目前顯示 ${limit} 場` : ''}${clearedPark ? '；已清除不相容的場館篩選' : ''}`;
  $('results').innerHTML=events.slice(0,limit).map(e=>{
    const badge = eventBadge(e);
    const url = /^https?:\/\//i.test(e.url) ? e.url : links[e.source];
    return `<article class="card"><div class="card-top"><span>${escapeHTML(e.region)} · ${escapeHTML(e.category)}</span><span class="badge">${badge}</span></div><h3>${escapeHTML(e.title)}</h3><p class="event-date">${escapeHTML(dateLabel(e))}</p><dl><dt>地點　</dt><dd>${escapeHTML(e.venueName || e.venue || e.address)}${e.venue && e.venue!==e.venueName ? `<br><small>${escapeHTML(e.venue)}</small>` : ''}${e.venueStatus==='uncertain' || e.venueStatus==='missing' ? '<br><small>來源未提供確切場館，請向主辦方確認</small>' : ''}</dd><dt>票價　</dt><dd>${escapeHTML(e.price)}</dd></dl><p class="summary">${escapeHTML(e.summary)}</p>${e.verificationNote ? `<p class="verification">⚠ ${escapeHTML(e.verificationNote)}</p>` : ''}${e.source==='moc' && !['verified','source-provided'].includes(e.sourceLinkState) ? `<p class="note">尚未找到可核對的活動頁。</p><a href="https://www.google.com/search?q=${escapeHTML(encodeURIComponent(e.title+' '+(e.venueName || e.venue || '')))}" target="_blank" rel="noopener noreferrer">搜尋此活動（Google） ↗</a><p class="note">搜尋結果需自行核對主辦方。<br>資料來源：<a href="${escapeHTML(links.moc)}" target="_blank" rel="noopener noreferrer">文化部資料集（非活動頁） ↗</a><br>資料UID：${escapeHTML(e.sourceUid)}</p>` : `<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">${e.source==='moc' ? (e.sourceLinkState==='source-provided' ? '文化部提供的相關網站' : '活動資訊／來源網站') : '官方展覽資訊'} ↗</a>${e.sourceLinkState==='source-provided' ? '<p class="note">文化部原始資料提供的網址；可能是活動頁、主辦首頁或列表。</p>' : ''}`}<small>來源：${names[e.source]}${e.source==='moc' && e.sourceVersion ? ' · v'+escapeHTML(e.sourceVersion) : e.sourceVersion==='official-public-incremental' ? ' · 官網增量收錄' : e.sourceVersion==='official-public-daily' ? ' · 官網收錄（既有資料）' : ' · 人工核對'}<br>最後收錄：${escapeHTML(localTime(e.lastSeen))}${e.missingFromSource ? '<br>⚠ 來源本次未提供，出發前請向主辦方確認' : ''}</small></article>`;
  }).join('') || '<div class="empty"><h3>這組條件尚無展覽</h3><p>試著放寬地區或日期，也可以查看松菸、華山官方入口。</p></div>';
  $('more').hidden=events.length<=limit;
}
async function init(){
  try {
    const response=await fetch('./data/exhibitions.json',{cache:'no-cache'});
    if(!response.ok) throw new Error('資料檔讀取失敗');
    data=await response.json();
    if(data.schemaVersion!==1 || !Array.isArray(data.events)) throw new Error('資料版本不符');
    [...new Set(data.events.map(e=>e.region))].sort((a,b)=>northRank({region:a})-northRank({region:b})||a.localeCompare(b,'zh-TW')).forEach(r=>{const o=document.createElement('option');o.value=r;o.textContent=r;$('region').append(o)});
    const source=data.sources.moc, stale=source.lastSuccess && Date.now()-Date.parse(source.lastSuccess)>36*3600000;
    $('updated').textContent=`文化部最後成功更新（台灣時間）：${localTime(source.lastSuccess)}${source.state==='error' ? ' · 更新失敗，使用保留資料' : stale ? ' · 資料已超過36小時，請確認官方公告' : ''}`;
    const failedVenues=Object.entries(data.sources).filter(([key,s])=>key!=='moc' && s.state==='error').map(([key])=>names[key]);
    if(failedVenues.length) $('updated').textContent+=` · 場館更新失敗，使用保留資料：${failedVenues.join('、')}`;
    $('source-status').innerHTML=Object.entries(data.sources).map(([key,s])=>`<div class="source-row"><a href="${links[key]}" target="_blank" rel="noopener noreferrer">${names[key]} ↗</a><span class="state ${s.state==='error'?'error':''}">${s.state==='ok'?'自動更新':s.state==='error'?'更新失敗':'人工核對'}</span><div>${escapeHTML(s.message)}<small>最後成功／核對：${escapeHTML(localTime(s.lastSuccess))}${s.lastAttempt ? `<br>最後嘗試：${escapeHTML(localTime(s.lastAttempt))}` : ''}</small></div></div>`).join('');
    render();
  } catch(error){$('updated').textContent='目前無法讀取資料';$('results').innerHTML='<div class="empty">展覽資料載入失敗，請重新整理或查看官方入口。</div>';console.error(error);}
}
if(typeof module!=='undefined') module.exports={todayTW,hasDate,isEnded,matchesDates,compareEvents,eventBadge,dateLabel,nextTaiwanDayDelay};
if(typeof document!=='undefined'){
$('filters').addEventListener('input',()=>{limit=24;if(data)render()});
$('filters').addEventListener('submit',e=>e.preventDefault());
$('filters').addEventListener('reset',()=>setTimeout(()=>{limit=24;if(data)render()},0));
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{view=button.dataset.view;limit=24;document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));if(data)render()}));
$('more').addEventListener('click',()=>{limit+=24;render()});
function refreshDay(){
  const current=todayTW();
  if(current!==today){today=current;if(data)render();}
}
function scheduleDayRefresh(){
  setTimeout(()=>{refreshDay();scheduleDayRefresh();},nextTaiwanDayDelay());
}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshDay();});
scheduleDayRefresh();
init();
}
