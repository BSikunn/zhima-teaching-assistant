import assert from 'node:assert/strict'
import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import { writeFile } from 'node:fs/promises'
const base=process.env.APP_URL||'http://127.0.0.1:8765'
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1204,height:900}})
const errors=[];page.on('pageerror',e=>errors.push(e.message))
try{
  await page.goto(base+'/login')
  await page.getByTestId('role-admin').click()
  await page.getByTestId('login-submit').click()
  await page.waitForURL('**/overview')
  await page.goto(base+'/admin')
  await page.locator('.service-card').first().waitFor()
  for(const name of ['Redis + Celery','MinIO / 文件存储','Judge0 代码沙箱']){
    const status=await page.locator('.service-card').filter({hasText:name}).locator('.tag').innerText()
    assert.equal(status,'运行中',name)
  }
  assert.equal(await page.locator('.service-card .tag').filter({hasText:'未配置'}).count(),0)
  await page.screenshot({path:'artifacts/live-services-admin.png',fullPage:true})
  await page.getByTestId('logout').click()
  await page.getByTestId('role-student').click()
  await page.getByTestId('login-submit').click()
  await page.waitForURL('**/overview')
  await page.getByLabel('选择课程').selectOption('2')
  await page.goto(base+'/assignments')
  await page.getByTestId('code-input').fill('print("zhima-browser-sandbox")')
  await page.locator('summary').filter({hasText:'代码试运行'}).click()
  await page.getByRole('button',{name:'运行代码',exact:true}).click()
  await page.waitForFunction(()=>document.querySelector('.execution-result pre')?.textContent.includes('zhima-browser-sandbox'),{},{timeout:60000})
  await page.screenshot({path:'artifacts/live-services-sandbox.png',fullPage:true})
  assert.deepEqual(errors,[])
  const result={admin:'three newly configured services active; no unconfigured labels',sandbox:'actual Python execution through browser/Judge0; no assignment submitted',errors}
  await writeFile('artifacts/browser-services.json',JSON.stringify(result,null,2))
  console.log('PASS live admin service statuses and actual browser Python sandbox')
}finally{await browser.close()}
