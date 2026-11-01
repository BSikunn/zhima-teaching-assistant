import assert from 'node:assert/strict'
import { chromium } from '../frontend/node_modules/playwright/index.mjs'

const base=process.env.APP_URL||'http://127.0.0.1:8765'
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1440,height:1080}})
let failures=0
async function delayed(pattern, action, check){
  let release,arrived,completed
  const gate=new Promise(r=>release=r),seen=new Promise(r=>arrived=r)
  const handled=new Promise(r=>completed=r)
  await page.route(pattern,async route=>{arrived();await gate;try{await route.continue()}finally{completed()}})
  try{await action();await seen;await check()}
  finally{release();await handled;await page.unroute(pattern)}
}
try{
  await page.goto(base+'/login');await page.getByTestId('role-student').click();await page.getByTestId('login-submit').click();await page.waitForURL('**/overview');await page.getByTestId('overview-ready').waitFor()
  try{
    await page.goto(base+'/chat')
    await page.getByTestId('chat-input').fill('最左前缀原则')
    await delayed('**/api/courses/1/chat',()=>page.getByTestId('chat-send').click(),async()=>{
      assert.equal(await page.getByRole('button',{name:'开启新对话'}).isDisabled(),true,'pending chat must prevent conversation switching')
      for(const button of await page.locator('.history-item').all())assert.equal(await button.isDisabled(),true)
    })
    console.log('PASS pending chat cannot switch conversations')
  }catch(e){failures++;console.error('FAIL',e.message)}
  try{
    await page.goto(base+'/assignments');await page.getByTestId('assignment-1').click()
    await page.getByTestId('code-input').fill('SELECT * FROM students WHERE email = NULL;')
    await delayed('**/api/assignments/1/submissions',()=>page.getByTestId('submit-code').click(),async()=>{
      assert.equal(await page.getByTestId('assignment-2').isDisabled(),true,'pending submission must prevent assignment switching')
    })
    console.log('PASS pending submission cannot switch assignments')
  }catch(e){failures++;console.error('FAIL',e.message)}
}finally{await browser.close()}
process.exitCode=failures?1:0
