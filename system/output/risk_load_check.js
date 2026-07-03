async (page) => {
  await page.goto('http://127.0.0.1:5173/risk?preview=1', { waitUntil: 'networkidle' })
  await page.waitForTimeout(3000)
  const text = await page.locator('body').innerText()
  await page.screenshot({ path: 'G:/CISCN/CogGuard/system/output/risk-page-load-check.png', fullPage: true })
  return {
    url: page.url(),
    hasEmptyState: text.includes('暂无已加载的风险报告'),
    hasHistory: text.includes('历史报告'),
    hasReport: text.includes('综合风险') || text.includes('KT3 分层危害性刻画'),
    hasRunButton: text.includes('运行评估'),
    bodyHead: text.slice(0, 800),
  }
}
