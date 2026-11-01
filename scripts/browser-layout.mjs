import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import { writeFile } from 'node:fs/promises'
const browser=await chromium.launch({channel:'msedge',headless:true})
const result=[]
try{
  const page=await browser.newPage()
  const base=process.env.APP_URL||'http://127.0.0.1:8765'
  await page.goto(base+'/login')
  await page.getByTestId('role-student').click()
  await page.getByTestId('login-submit').click()
  await page.waitForURL('**/overview')
  await page.getByTestId('overview-ready').waitFor()
  for(const width of [1440,1280,960,390]){
    await page.setViewportSize({width,height:900})
    // ECharts' ResizeObserver resizes its canvas on the next render frame.
    await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth+2)
    console.log('PASS layout '+width)
    result.push({width,overflow:false})
  }
  await page.screenshot({path:'artifacts/mobile-overview.png',fullPage:true})
  await writeFile('artifacts/layout-report.json',JSON.stringify(result,null,2))
}finally{await browser.close()}
