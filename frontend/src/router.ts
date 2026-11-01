import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from './stores/session'

const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/login', component: () => import('./views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: '/overview' },
  { path: '/overview', component: () => import('./views/Overview.vue'), meta: { title: '概览' } },
  { path: '/chat', component: () => import('./views/Chat.vue'), meta: { title: '课程问答' } },
  { path: '/assignments', component: () => import('./views/Assignments.vue'), meta: { title: '作业中心' } },
  { path: '/practice', component: () => import('./views/Practice.vue'), meta: { title: '测验与面试', roles: ['student', 'teacher', 'admin'] } },
  { path: '/reports', component: () => import('./views/Reports.vue'), meta: { title: '学习报告', roles: ['student', 'teacher', 'admin'] } },
  { path: '/mistakes', component: () => import('./views/Mistakes.vue'), meta: { title: '我的错题本', roles: ['student'] } },
  { path: '/plans', component: () => import('./views/Plans.vue'), meta: { title: '学习计划', roles: ['student'] } },
  { path: '/knowledge', component: () => import('./views/Knowledge.vue'), meta: { title: '课程知识库', roles: ['teacher', 'admin'] } },
  { path: '/reviews', component: () => import('./views/Reviews.vue'), meta: { title: '批改复核', roles: ['teacher', 'admin'] } },
  { path: '/settings', component: () => import('./views/Settings.vue'), meta: { title: '智能体设置', roles: ['teacher', 'admin'] } },
  { path: '/admin', component: () => import('./views/Admin.vue'), meta: { title: '系统管理', roles: ['admin'] } },
  { path: '/:pathMatch(.*)*', redirect: '/overview' },
] })
router.beforeEach(to => {
  const session = useSession()
  if (!to.meta.public && !localStorage.getItem('zhima-token')) return '/login'
  const roles = to.meta.roles as string[] | undefined
  if (roles && !roles.includes(session.user?.role)) return '/overview'
})
export default router
