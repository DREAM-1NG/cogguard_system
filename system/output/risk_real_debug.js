(async (page) => {
  const logs = [];
  const responses = [];
  page.on('console', msg => logs.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', err => logs.push({ type: 'pageerror', text: err.message }));
  page.on('response', async res => {
    const url = res.url();
    if (url.includes('/api/v1/risk')) {
      let body = '';
      try { body = (await res.text()).slice(0, 1000); } catch (error) { body = String(error); }
      responses.push({ url, status: res.status(), body });
    }
  });
  await page.goto('http://127.0.0.1:5173/risk', { waitUntil: 'networkidle' });
  const beforeText = await page.locator('body').innerText();
  await page.getByRole('button', { name: '运行评估' }).click();
  await page.waitForTimeout(8000);
  const afterText = await page.locator('body').innerText();
  const screenshot = 'G:/CISCN/CogGuard/system/output/risk-page-real-debug.png';
  await page.screenshot({ path: screenshot, fullPage: true });
  return {
    beforeHasReport: beforeText.includes('综合风险') || beforeText.includes('KT3 分层危害性刻画'),
    afterHasReport: afterText.includes('综合风险') || afterText.includes('KT3 分层危害性刻画'),
    bodyHead: afterText.slice(0, 800),
    responses,
    logs,
    screenshot,
  };
})(page)
