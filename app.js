'use strict';
const today = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const $ = id => document.getElementById(id);
let data, view = 'all', limit = 24;
const escapeHTML = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const days = d => Math.round((Date.parse(d+'T00:00:00+08:00')-Date.parse(today+'T00:00:00+08:00'))/86400000);
const localTime = t => t ? new Date(t).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}) : '尚無成功更新';
const northRank = e => e.region === '臺北市' ? 0 : e.region === '新北市' ? 1 : 2;
const names = {moc:'文化部',songshan:'松山文創園區',huashan:'華山1914'};
const links = {moc:'https://data.gov.tw/dataset/6012',songshan:'https://www.songshanculturalpark.org/exhibition',huashan:'https://www.huashan1914.com/exhibition'};
const notes = {all:'顯示尚未結束的展期；不代表今日一定開館。',new:'依本站首次收錄日期（台灣時間）顯示，首批匯入會一併列為新增。',recommended:'展期與未來30天重疊、資料來源仍提供的展覽，優先台北／新北與較近開展日；非人氣排名。',ending:'目前展期內，且未來14天內結束。',history:'已結束的展覽持續保留；歷史從本站開始收錄累積。'};
function render(){
  limit = Math.max(limit,24);
  const region=$('region').value, date=$('date').value, park=$('park').value, query=$('query').value.trim().toLowerCase();
  let events=data.events.filter(e => {
    if(region==='north' && northRank(e)>1 || region && region!=='north' && e.region!==region) return false;
    if(park && e.park!==park || date && (e.start>date || e.end<date)) return false;
    if(query && !`${e.title} ${e.venue} ${e.address} ${e.category}`.toLowerCase().includes(query)) return false;
    if(view==='history') return e.end<today;
    if(e.end<today) return false;
    if(view==='new') return e.firstSeen?.slice(0,10)===today;
    if(view==='ending') return e.start<=today && days(e.end)<=14;
    if(view==='recommended') return days(e.start)<=30 && !e.missingFromSource;
    return true;
  });
  events.sort((a,b)=>view==='history' ? b.end.localeCompare(a.end) : view==='ending' ? a.end.localeCompare(b.end)||northRank(a)-northRank(b) : northRank(a)-northRank(b)||a.start.localeCompare(b.start)||a.title.localeCompare(b.title,'zh-TW'));
  $('view-note').textContent=notes[view];
  $('result-count').textContent=`找到 ${events.length} 場展覽${events.length>limit ? `，目前顯示 ${limit} 場` : ''}`;
  $('results').innerHTML=events.slice(0,limit).map(e=>{
    const badge = e.end<today ? '已結束' : e.start>today ? '即將開展' : days(e.end)<=14 ? '即將結束' : '展期內';
    const url = /^https?:\/\//i.test(e.url) ? e.url : links[e.source];
    return `<article class="card"><div class="card-top"><span>${escapeHTML(e.region)} · ${escapeHTML(e.category)}</span><span class="badge">${badge}</span></div><h3>${escapeHTML(e.title)}</h3><dl><dt>日期　</dt><dd>${escapeHTML(e.start)} — ${escapeHTML(e.end)}</dd><dt>地點　</dt><dd>${escapeHTML(e.venue || e.address)}</dd><dt>票價　</dt><dd>${escapeHTML(e.price)}</dd></dl><p class="summary">${escapeHTML(e.summary)}</p><a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">${e.source==='moc' ? '活動來源／文化部紀錄' : '官方展覽資訊'} ↗</a><small>來源：${names[e.source]}${e.sourceVersion ? ' · v'+escapeHTML(e.sourceVersion) : ' · 人工核對'}<br>最後收錄：${escapeHTML(localTime(e.lastSeen))}${e.missingFromSource ? '<br>⚠ 來源本次未提供，出發前請向主辦方確認' : ''}</small></article>`;
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
    $('active-count').textContent=data.events.filter(e=>e.end>=today).length;
    $('new-count').textContent=data.events.filter(e=>e.firstSeen?.slice(0,10)===today && e.end>=today).length;
    const source=data.sources.moc, stale=source.lastSuccess && Date.now()-Date.parse(source.lastSuccess)>36*3600000;
    $('updated').textContent=`文化部最後成功更新（台灣時間）：${localTime(source.lastSuccess)}${source.state==='error' ? ' · 更新失敗，使用保留資料' : stale ? ' · 資料已超過36小時，請確認官方公告' : ''}`;
    $('source-status').innerHTML=Object.entries(data.sources).map(([key,s])=>`<div class="source-row"><a href="${links[key]}" target="_blank" rel="noopener noreferrer">${names[key]} ↗</a><span class="state ${s.state==='error'?'error':''}">${s.state==='ok'?'自動更新':s.state==='error'?'更新失敗':'人工核對'}</span><div>${escapeHTML(s.message)}<small>最後成功／核對：${escapeHTML(localTime(s.lastSuccess))}</small></div></div>`).join('');
    render();
  } catch(error){$('updated').textContent='目前無法讀取資料';$('results').innerHTML='<div class="empty">展覽資料載入失敗，請重新整理或查看官方入口。</div>';console.error(error);}
}
$('filters').addEventListener('input',()=>{limit=24;if(data)render()});
$('filters').addEventListener('submit',e=>e.preventDefault());
$('filters').addEventListener('reset',()=>setTimeout(()=>{limit=24;if(data)render()},0));
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{view=button.dataset.view;limit=24;document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));if(data)render()}));
$('more').addEventListener('click',()=>{limit+=24;render()});
init();
