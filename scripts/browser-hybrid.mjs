import assert from 'node:assert/strict'
import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import { writeFile } from 'node:fs/promises'
const base=process.env.APP_URL||'http://127.0.0.1:8769'
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1440,height:1050}}),checks=[],errors=[]
page.on('pageerror',e=>errors.push(e.message))
let captured,answer={id:100,role:'assistant',content:'法国的首都是巴黎。',citations:[],mode:'deepseek',hint_level:1,answer_basis:'model',web_search:{status:'disabled'}}
await page.route('**/api/courses/*/chat',async route=>{
  captured=route.request().postDataJSON()
  await route.fulfill({json:{conversation_id:999,answer}})
})
try{
  await page.goto(base+'/login')
  await page.getByTestId('login-submit').click()
  await page.waitForURL('**/overview')
  await page.goto(base+'/chat')
  await page.getByTestId('chat-input').fill('法国的首都是哪里？')
  await page.getByTestId('chat-send').click()
  await page.getByText('法国的首都是巴黎。',{exact:true}).waitFor()
  await page.getByText('模型知识回答',{exact:true}).waitFor()
  assert.equal(await page.getByText('当前课程资料中没有找到足够依据。',{exact:false}).count(),0)
  checks.push('课程外问题正常显示模型回答')
  answer={...answer,id:101,content:'课程说明与官方网页都支持这个结论 [1][2]。',answer_basis:'course+web',
    citations:[{number:1,source_type:'course',material_id:1,filename:'课程讲义.md',location:'第1段',text:'课程来源快照'},
      {number:2,source_type:'web',title:'导览 - 故宫博物院',url:'https://www.dpm.org.cn/Visit.html',text:'网页搜索摘要快照',retrieved_at:'2026-10-31T16:00:00+08:00'}],
    web_search:{status:'success',detail:'已获取网页搜索摘要'}}
  await page.getByLabel('联网补充',{exact:true}).check()
  await page.getByTestId('chat-input').fill('结合课程资料和网页说明')
  await page.getByTestId('chat-send').click()
  await page.getByText('课程资料＋网页补充',{exact:true}).waitFor()
  assert.equal(captured.web_search,true)
  await page.getByTestId('citation').filter({hasText:'故宫博物院'}).click()
  await page.getByText('网页搜索摘要快照',{exact:true}).waitFor()
  const link=page.getByRole('link',{name:'打开来源网页'})
  assert.equal(await link.getAttribute('href'),'https://www.dpm.org.cn/Visit.html')
  assert.match(await link.getAttribute('rel'),/noopener/)
  await page.keyboard.press('Escape')
  checks.push('课程与网页引用分开、网页快照及原链接可查看')
  await page.screenshot({path:'artifacts/hybrid-chat-desktop.png',fullPage:true})
  answer={...answer,id:102,content:'联网暂时失败也会继续正常回答。',answer_basis:'model',citations:[],web_search:{status:'failed'}}
  await page.getByTestId('chat-input').fill('继续回答一个一般问题')
  await page.getByTestId('chat-send').click()
  await page.getByText('联网暂时失败也会继续正常回答。',{exact:true}).waitFor()
  await page.getByText('联网暂不可用，已继续回答',{exact:true}).waitFor()
  checks.push('联网失败状态明确且保留模型答案')
  await page.setViewportSize({width:390,height:900})
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth+2)
  await page.screenshot({path:'artifacts/hybrid-chat-mobile.png',fullPage:true})
  checks.push('390像素聊天界面无横向溢出')
  assert.deepEqual(errors,[])
  console.log(checks.map(x=>'PASS '+x).join('\n'))
  await writeFile('artifacts/browser-hybrid.json',JSON.stringify({checks,errors,boundary:'browser API response fixtures; real network/model verified separately'},null,2))
}finally{await browser.close()}
