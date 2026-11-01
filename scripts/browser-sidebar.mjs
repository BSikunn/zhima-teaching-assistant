import assert from 'node:assert/strict'
import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import { writeFile } from 'node:fs/promises'
const base=process.env.APP_URL||'http://127.0.0.1:8765'
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1191,height:668}}),results=[]
try{
  await page.goto(base+'/login')
  await page.getByTestId('role-admin').click()
  await page.getByTestId('login-submit').click()
  await page.waitForURL('**/overview')
  await page.getByTestId('overview-ready').waitFor()
  for(const height of [668,500]){
    await page.setViewportSize({width:1191,height})
    await page.evaluate(()=>{window.scrollTo(0,0);document.querySelector('.sidebar nav').scrollTop=0})
    const nav=page.getByRole('navigation',{name:'主导航'})
    await nav.hover()
    await page.mouse.wheel(0,1200)
    await page.waitForFunction(()=>document.querySelector('.sidebar nav').scrollTop>0,{},{timeout:2500})
    const state=await page.evaluate(()=>{
      const nav=document.querySelector('.sidebar nav'),last=nav.querySelector('a[href="/admin"]'),r=last.getBoundingClientRect()
      return {height:innerHeight,scrollTop:nav.scrollTop,lastTop:r.top,lastBottom:r.bottom,pageScroll:scrollY}
    })
    results.push(state)
    assert.ok(state.lastTop>=0&&state.lastBottom<=height,JSON.stringify(state))
    assert.equal(state.pageScroll,0,'侧栏滚动应独立于内容页')
    await lastVisibleLink(page).click()
    await page.waitForURL('**/admin')
    await page.goto(base+'/overview')
    await page.getByTestId('overview-ready').waitFor()
  }
  const token=await page.evaluate(()=>localStorage.getItem('zhima-token'))
  const courses=await (await page.request.get(base+'/api/courses',{headers:{Authorization:'Bearer '+token}})).json()
  assert.equal(courses.length,3)
  assert.ok(courses.every(c=>c.class_name==='高级软件产品管理1班'),JSON.stringify(courses))
  await page.setViewportSize({width:1191,height:668})
  await page.getByText('高级软件产品管理1班',{exact:false}).first().waitFor()
  await page.screenshot({path:'artifacts/sidebar-1191x668.png',fullPage:false})
  await page.setViewportSize({width:390,height:668})
  await page.getByRole('button',{name:'展开导航'}).click()
  await page.getByRole('navigation',{name:'主导航'}).hover()
  await page.mouse.wheel(0,1200)
  await lastVisibleLink(page).click()
  await page.waitForURL('**/admin')
  assert.equal(await page.locator('.sidebar.open').count(),0,'点击菜单后应关闭移动端抽屉')
  console.log('PASS sidebar scroll1191x668 and1191x500, independent page scroll, mobile navigation, three-course class name')
  await writeFile('artifacts/sidebar-verification.json',JSON.stringify({results,class_name:'高级软件产品管理1班'},null,2))
}finally{await browser.close()}
function lastVisibleLink(page){return page.getByRole('navigation',{name:'主导航'}).getByRole('link',{name:'系统管理',exact:true})}
