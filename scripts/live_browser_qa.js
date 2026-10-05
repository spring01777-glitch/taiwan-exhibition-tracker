async page => {
  const report = [];
  for (const kind of ['concerts', 'comedy']) {
    await page.goto('http://127.0.0.1:8876/'+kind+'.html');
    await page.waitForSelector('.card');
    const {events:data} = await page.evaluate(async () => (await (await fetch(document.body.dataset.events || 'data/concerts.json')).json()));
    const today=await page.evaluate(()=>ConcertFilters.todayTW());
    const cities=[...new Set(data.map(e=>e.region))];
    let pairs=0;
    for (const city of cities) {
      await page.locator('#region').selectOption(city);
      const listed=await page.locator('#venue option').evaluateAll(os=>os.map(o=>o.value).filter(Boolean));
      const expected=[...new Set(data.filter(e=>e.region===city).map(e=>e.venue))];
      if(JSON.stringify([...listed].sort())!==JSON.stringify(expected.sort()))throw Error('missing venue '+city);
      for(const venue of listed){
        await page.locator('#venue').selectOption(venue);
        const count=data.filter(e=>e.region===city && e.venue===venue && e.status!=='cancelled' && e.sessions.some(s=>s.date>=today)).length;
        if(await page.locator('.card').count()!==count)throw Error('AND mismatch '+city+' '+venue);
        pairs++;
      }
    }
    await page.locator('button[type=reset]').click();
    const upcoming=data.filter(e=>e.status!=='cancelled'&&e.sessions.some(s=>s.date>=today)).length;
    await page.waitForFunction(n=>document.querySelectorAll('.card').length===n,upcoming);
    await page.locator('#view').selectOption('all');
    const sample=data[0];
    await page.locator('#query').fill(sample.title);
    await page.locator('#date').fill(sample.sessions[0].date);
    if(await page.locator('.card').count()<1)throw Error('date and query failure');
    await page.locator('#date').fill('1900-01-01');
    if(await page.locator('.card').count()!==0)throw Error('date AND failure');
    await page.locator('button[type=reset]').click();
    await page.waitForFunction(n=>document.querySelectorAll('.card').length===n,upcoming);
    const width=await page.evaluate(()=>({view:innerWidth,scroll:document.documentElement.scrollWidth}));
    if(width.scroll>width.view)throw Error('horizontal overflow');
    await page.locator('#filters').scrollIntoViewIfNeeded();
    await page.screenshot({path:'output/playwright/'+kind+'-mobile-filters.png'});
    report.push({kind,cities:cities.length,pairs,events:data.length,width,dateSearchReset:'pass'});
  }
  return report;
}
