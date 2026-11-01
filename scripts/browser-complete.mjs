import assert from 'node:assert/strict'
import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const base=process.env.APP_URL||'http://127.0.0.1:8766'
const artifact=path.join(root,'artifacts'), checks=[], errors=[]
await mkdir(artifact,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1440,height:1080}})
page.on('pageerror',e=>errors.push(e.message))
async function step(name,run){await run(); checks.push(name);console.log('PASS',name)}
async function login(account){
  await page.goto(base+'/login')
  await page.getByTestId('role-student').click()
  await page.getByLabel('学生身份',{exact:true}).selectOption(account)
  await page.getByTestId('login-submit').click()
  await page.waitForURL('**/overview')
  await page.getByTestId('overview-ready').waitFor()
}
try{
  await step('三位学生可登录并加入三门课程',async()=>{
    for(const account of ['student','student2','student3']){
      await login(account)
      assert.equal(await page.getByLabel('选择课程').locator('option').count(),3)
      await page.getByTestId('logout').click()
    }
    await login('student')
  })
  await step('三课程作业代码与内容随课程切换',async()=>{
    await page.goto(base+'/assignments')
    for(const [id,label] of [['1','SQL'],['2','Python'],['3','Java']]){
      await page.getByLabel('选择课程').selectOption(id)
      await page.getByLabel(label+' 代码',{exact:true}).waitFor()
      assert.ok(await page.locator('.assignment-card').count()>=3)
    }
    await page.screenshot({path:path.join(artifact,'complete-java-assignments.png'),fullPage:true})
  })
  await step('Python测验生成、作答、反馈持久化',async()=>{
    await page.getByLabel('选择课程').selectOption('2')
    await page.goto(base+'/practice')
    await page.getByLabel('题目数量').selectOption('1')
    await page.getByTestId('practice-generate').click()
    await page.getByLabel('第1题回答',{exact:true}).fill('列表按顺序保存元素，字典通过键查找值；遍历与访问应符合数据结构。')
    assert.equal(await page.getByText('参考思路：',{exact:false}).count(),0)
    await page.getByTestId('practice-submit').click()
    await page.getByTestId('practice-feedback').waitFor()
    await page.screenshot({path:path.join(artifact,'complete-python-quiz.png'),fullPage:true})
    await page.reload()
    await page.locator('.task-history-item').first().click()
    await page.getByTestId('practice-feedback').waitFor()
  })
  await step('Java模拟面试逐轮展示与提交',async()=>{
    await page.getByLabel('选择课程').selectOption('3')
    await page.getByLabel('练习模式').selectOption('interview')
    await page.getByLabel('题目数量').selectOption('2')
    await page.getByTestId('practice-generate').click()
    await page.getByLabel('第1题回答',{exact:true}).fill('Java 的类定义状态和行为，对象是类的实例，封装通过访问控制保护状态。')
    assert.equal(await page.getByLabel('第2题回答',{exact:true}).count(),0)
    await page.getByTestId('practice-submit').click()
    await page.getByLabel('第2题回答',{exact:true}).fill('先检查边界条件，再使用集合保存数据，异常应在合适层处理。')
    assert.equal(await page.getByLabel('第1题回答',{exact:true}).count(),0)
    await page.getByTestId('practice-submit').click()
    await page.getByTestId('practice-feedback').waitFor()
    await page.getByText('本次练习反馈',{exact:true}).waitFor()
    await page.screenshot({path:path.join(artifact,'complete-java-interview.png'),fullPage:true})
  })
  await step('个人报告生成与受保护下载',async()=>{
    await page.goto(base+'/reports')
    await page.getByTestId('report-generate').click()
    await page.getByTestId('report-content').waitFor()
    const downloaded=page.waitForEvent('download')
    await page.getByTestId('report-download').click()
    await (await downloaded).saveAs(path.join(artifact,'browser-learning-report.md'))
    await page.screenshot({path:path.join(artifact,'complete-learning-report.png'),fullPage:true})
  })
  await step('未配置沙箱时给出明确提示',async()=>{
    await page.goto(base+'/assignments')
    await page.locator('summary').filter({hasText:'代码试运行'}).click()
    await page.getByRole('button',{name:'运行代码',exact:true}).click()
    await page.getByText('当前未启用 Judge0 代码执行服务。可继续提交作业获得代码评阅。',{exact:true}).waitFor()
  })
  assert.deepEqual(errors,[])
  await writeFile(path.join(artifact,'browser-complete.json'),JSON.stringify({checks,errors},null,2))
}finally{await browser.close()}
