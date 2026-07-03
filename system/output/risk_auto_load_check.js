async (page) => {
  const responses = []
  const errors = []
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()) })
  page.on('response', async res => {
    if (res.url().includes('/api/v1/risk')) {
      let body = ''
      try { body = (await res.text()).slice(0, 400) } catch {}
      responses.push({ url: res.url(), status: res.status(), body })
    }
  })
  await page.goto('http://127.0.0.1:5173/risk?preview=1', { waitUntil: 'networkidle' })
  await page.waitForTimeout(10000)
  const text = await page.locator('body').innerText()
  await page.screenshot({ path: 'G:/CISCN/CogGuard/system/output/risk-page-auto-load-check.png', fullPage: true })
  return {
    hasReport: text.includes('综合风险') || text.includes('KT3 分层危害性刻画'),
    hasEmptyState: text.includes('暂无已加载的风险报告'),
    hasSpinnerText: text.includes('正在加载风险研判结果'),
    hasRunButton: text.includes('运行评估'),
    responses,
    errors,
    bodyHead: text.slice(0, 800),
  }
}
