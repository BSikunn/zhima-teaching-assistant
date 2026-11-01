import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const base = process.env.APP_URL || 'http://127.0.0.1:8765'
const artifactDir = path.join(root, 'artifacts')
await mkdir(artifactDir, { recursive: true })
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1080 }, deviceScaleFactor: 1 })
const errors = []
page.on('pageerror', e => errors.push(e.message))
const report = []
async function step(name, fn) { await fn(); report.push(name); console.log('PASS', name) }
async function signIn(role) {
  await page.goto(base + '/login')
  await page.getByTestId('role-' + role).click()
  await page.getByTestId('login-submit').click()
  await page.waitForURL('**/overview')
  await page.getByTestId('overview-ready').waitFor()
}
try {
  await step('学生登录与学习概览', async () => {
    await signIn('student')
    await page.screenshot({ path: path.join(artifactDir, 'student-overview.png'), fullPage: true })
  })
  await step('课程问答返回可追溯引用', async () => {
    await page.goto(base + '/chat')
    await page.getByTestId('chat-input').fill('什么是最左前缀原则？')
    await page.getByTestId('chat-send').click()
    await page.getByTestId('citation').first().waitFor()
    await page.screenshot({ path: path.join(artifactDir, 'student-chat.png'), fullPage: true })
    await page.getByTestId('citation').first().click()
    await page.getByText('来源原文', { exact: true }).waitFor()
    await page.waitForFunction(() => { const drawer=document.querySelector('.el-drawer'); return drawer&&drawer.getBoundingClientRect().right<=window.innerWidth+1 })
    await page.screenshot({ path: path.join(artifactDir, 'student-source.png'), fullPage: true })
    await page.keyboard.press('Escape')
  })
  await step('错误 SQL 提交与批改', async () => {
    await page.goto(base + '/assignments')
    await page.getByTestId('assignment-1').click()
    await page.getByTestId('code-input').fill('SELECT * FROM students WHERE email = NULL;')
    await page.getByTestId('submit-code').click()
    await page.getByTestId('grade-result').waitFor()
    await page.getByText('NULL 判断', { exact: true }).first().waitFor()
    await page.screenshot({ path: path.join(artifactDir, 'student-grading.png'), fullPage: true })
  })
  await step('错题本与可完成复习计划', async () => {
    await page.goto(base + '/mistakes')
    await page.getByText('NULL 判断', { exact: true }).first().waitFor()
    await page.goto(base + '/plans')
    await page.getByTestId('generate-plan').click()
    await page.getByTestId('plan-item').first().waitFor()
    await page.getByTestId('plan-item').first().click()
    await page.screenshot({ path: path.join(artifactDir, 'student-plan.png'), fullPage: true })
  })
  await step('教师看板与批改复核', async () => {
    await page.getByTestId('logout').click()
    await signIn('teacher')
    await page.screenshot({ path: path.join(artifactDir, 'teacher-overview.png'), fullPage: true })
    await page.goto(base + '/reviews')
    await page.getByTestId('review-open').first().click()
    await page.getByTestId('review-save').click()
    await page.getByText('复核已保存', { exact: true }).waitFor()
  })
  await step('教师上传真实资料并查看片段', async () => {
    await page.goto(base + '/knowledge')
    await page.getByTestId('material-upload').setInputFiles({ name: '浏览器测试资料.txt', mimeType: 'text/plain', buffer: Buffer.from('数据库浏览器验证：事务通过原子性保证一组操作全部成功或全部失败。') })
    await page.getByText('浏览器测试资料.txt', { exact: true }).first().waitFor()
    await page.getByTestId('material-preview').first().click()
    await page.getByRole('heading', { name: '知识片段', exact: true }).waitFor()
    await page.keyboard.press('Escape')
  })
  await step('窄屏布局与管理员连接状态', async () => {
    await page.setViewportSize({ width: 960, height: 900 })
    await page.goto(base + '/overview')
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2)
    if (overflow) throw new Error('窄屏页面横向溢出')
    await page.getByTestId('logout').click()
    await page.setViewportSize({ width: 1440, height: 1080 })
    await signIn('admin')
    await page.goto(base + '/admin')
    await page.getByText('服务连接状态', { exact: true }).waitFor()
    await page.screenshot({ path: path.join(artifactDir, 'admin-status.png'), fullPage: true })
  })
  if (errors.length) throw new Error(errors.join('\n'))
  await writeFile(path.join(artifactDir, 'browser-report.json'), JSON.stringify({ steps: report, pageErrors: errors, checkedAt: new Date().toISOString() }, null, 2))
} finally { await browser.close() }
