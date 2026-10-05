async page => {
 const report=[];
 await page.setViewportSize({width:390,height:844});
 for(const kind of ['concerts','comedy']){
  await page.goto('http://127.0.0.1:8876/'+kind+'.html');await page.waitForSelector('.card');
  const data=await page.evaluate(async()=> (await (await fetch(document.body.dataset.events||'data/concerts.json')).json()).events);
  const today=await page.evaluate(()=>ConcertFilters.todayTW());
  const available=data.filter(e=>e.status!=='cancelled'&&e.sessions.some(s=>s.status!=='cancelled'&&s.date>=today));
  const pairs=[...new Set(available.map(e=>JSON.stringify([e.region,e.venue])))].map(JSON.parse);
  const reset=async()=>{await page.locator('button[type=reset]').click();await page.waitForFunction(n=>document.querySelectorAll('.card').length===n,available.length);};
  let platformDates=0;
  for(const [city,venue] of pairs){
   await reset();await page.locator('#region').selectOption(city);
   const listed=await page.locator('#venue option').evaluateAll(os=>os.map(o=>o.value).filter(Boolean));
   const expected=[...new Set(available.filter(e=>e.region===city).map(e=>e.venue))];
   if(JSON.stringify([...listed].sort())!==JSON.stringify(expected.sort()))throw Error('missing venue '+city);
   await page.locator('#venue').selectOption(venue);
   const inVenue=available.filter(e=>e.region===city&&e.venue===venue);
   if(await page.locator('.card').count()!==inVenue.length)throw Error('city/venue AND');
   const tuples=[...new Set(inVenue.flatMap(e=>e.sessions.filter(s=>s.date>=today&&s.status!=='cancelled').flatMap(s=>{const links=e.tickets.filter(t=>t.sessions.some(q=>q.date===s.date&&(q.time||null)===(s.time||null)));return (links.length?links.map(t=>t.platform):['未核對']).map(p=>JSON.stringify([p,s.date]));})))].map(JSON.parse);
   for(const [platform,date] of tuples){
    await reset();await page.locator('#region').selectOption(city);await page.locator('#venue').selectOption(venue);await page.locator('#platform').selectOption(platform);await page.locator('#date').fill(date);
    const expectedEvents=inVenue.filter(e=>e.sessions.some(s=>s.date===date&&s.status!=='cancelled'&&(platform==='未核對'?!e.tickets.some(t=>t.sessions.some(q=>q.date===s.date&&(q.time||null)===(s.time||null))):e.tickets.some(t=>t.platform===platform&&t.sessions.some(q=>q.date===s.date&&(q.time||null)===(s.time||null))))));
    if(await page.locator('.card').count()!==expectedEvents.length)throw Error('platform/date AND '+city+' '+venue+' '+date);
    platformDates++;
   }
  }
  await reset();await page.locator('#view').selectOption('all');await page.locator('#query').fill(data[0].title);await page.locator('#date').fill(data[0].sessions[0].date);
  if(await page.locator('.card').count()<1)throw Error('query/date');await page.locator('#date').fill('1900-01-01');if(await page.locator('.card').count()!==0)throw Error('impossible date');await reset();
  const width=await page.evaluate(()=>({view:innerWidth,scroll:document.documentElement.scrollWidth}));if(width.scroll>width.view)throw Error('overflow');
  await page.locator('#filters').scrollIntoViewIfNeeded();await page.screenshot({path:'output/playwright/'+kind+'-mobile-filters.png'});
  report.push({kind,events:data.length,sessions:data.reduce((n,e)=>n+e.sessions.length,0),cities:new Set(data.map(e=>e.region)).size,pairs:pairs.length,platformDates,width,queryDateReset:'pass'});
 }
 return report;
}
