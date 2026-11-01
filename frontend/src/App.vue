<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from './stores/session'
import { api, dateText } from './api'
import Icon from './components/Icon.vue'
const session = useSession(), route = useRoute(), router = useRouter()
const navOpen = ref(false), notifications = ref(false), events = ref<any[]>([]), mode = ref('unknown')
const links = computed(() => [
  { path: '/overview', title: session.isStudent ? '学习概览' : '教学概览', icon: 'dashboard', group: '工作空间' },
  { path: '/chat', title: '课程问答', icon: 'chat' },
  { path: '/assignments', title: session.isStudent ? '作业中心' : '作业管理', icon: 'assignment' },
  { path: '/practice', title: '测验与面试', icon: 'graduation' },
  { path: '/reports', title: session.isStudent ? '学习报告' : '教学报告', icon: 'file' },
  ...(session.isStudent ? [{ path: '/mistakes', title: '我的错题本', icon: 'mistakes', group: '学习成长' }, { path: '/plans', title: '学习计划', icon: 'plan' }] : [
    { path: '/knowledge', title: '课程知识库', icon: 'database', group: '教学管理' },
    { path: '/reviews', title: '批改复核', icon: 'review' },
    { path: '/settings', title: '智能体设置', icon: 'sliders' },
  ]),
  ...(session.isAdmin ? [{ path: '/admin', title: '系统管理', icon: 'shield', group: '管理' }] : []),
])
async function refresh() {
  if (!session.user) return
  await session.loadCourses()
  try { const health = await api.get('/health'); mode.value = health.mode } catch { mode.value = 'unknown' }
}
onMounted(refresh)
watch(() => session.user?.id, refresh)
watch(() => route.path, () => { navOpen.value = false })
async function showEvents() { notifications.value = true; events.value = []; const id = session.courseId; const data = await api.get(`/courses/${id}/overview`); if (session.courseId === id) events.value = data.events }
watch(() => session.courseId, () => { notifications.value = false; events.value = [] })
function logout() { session.logout(); router.push('/login') }
</script>
<template>
  <RouterView v-if="route.meta.public" />
  <div v-else class="app-shell">
    <div v-if="navOpen" class="nav-mask" @click="navOpen=false"></div>
    <aside class="sidebar" :class="{open: navOpen}">
      <RouterLink to="/overview" class="brand"><span class="brand-mark"><Icon name="code" :size="27" /></span><div><b>智码助教<span class="brand-dot">.</span></b><small>ZHIMA · LEARNING COPILOT</small></div></RouterLink>
      <div class="workspace-label"><span class="status-dot"></span>{{ session.roleName }}<span class="version">V1.0</span></div>
      <nav aria-label="主导航"><template v-for="link in links" :key="link.path"><div v-if="link.group" class="nav-group">{{ link.group }}</div><RouterLink :to="link.path" class="nav-link" active-class="active"><Icon :name="link.icon" :size="19" /><span>{{ link.title }}</span><span v-if="link.path==='/chat'" class="ai-chip">AI</span></RouterLink></template></nav>
      <div class="sidebar-bottom"><div class="sidebar-tip"><span class="tip-icon"><Icon name="sparkle" :size="19" /></span><h4>每个问题，都值得被理解</h4><p>立足课程资料<br>陪你走好每一步</p><RouterLink to="/chat">开始一次提问 <Icon name="arrow" :size="14" /></RouterLink></div><div class="sidebar-footer"><span class="status-dot"></span>教学与学习工作空间</div></div>
    </aside>
    <div class="workspace">
      <header class="topbar"><div class="topbar-left"><button class="icon-btn menu-toggle" aria-label="展开导航" @click="navOpen=!navOpen"><Icon name="menu" /></button><span class="breadcrumb">工作台</span><span class="breadcrumb-slash">/</span><strong>{{ route.path==='/overview' ? (session.isStudent ? '学习概览' : '教学概览') : route.meta.title }}</strong></div><div class="topbar-right"><span class="mode-pill"><span class="status-dot"></span>{{ mode==='demo' ? '演示模式' : mode==='deepseek' ? 'DeepSeek 模式' : '服务状态待确认' }}</span><button class="icon-btn notification-button" aria-label="学习动态" @click="showEvents"><Icon name="bell" :size="19" /><i></i></button><span class="topbar-divider"></span><span class="avatar">{{ session.user?.name?.slice(0,1) }}</span><div class="user-info"><b>{{ session.user?.name }}</b><small>{{ session.roleName }}</small></div><button class="icon-btn logout-button" aria-label="退出登录" data-testid="logout" @click="logout"><Icon name="logout" :size="17" /></button></div></header>
      <main class="main-content"><div class="course-strip"><span><Icon name="book" :size="16" />当前课程</span><select :value="session.courseId" aria-label="选择课程" @change="session.selectCourse(Number(($event.target as HTMLSelectElement).value))"><option v-for="c in session.courses" :key="c.id" :value="c.id">{{ c.title }}</option></select><span class="course-term">{{ session.course?.class_name }}<i></i>2026 秋季学期</span></div><RouterView :key="session.courseId + route.path" /></main>
      <footer class="page-footer"><span>智码助教 · 以课程为依据，让学习有回响</span><span>课程记录持续保存 <i>·</i> 历史样例单独标注</span></footer>
    </div>
    <el-drawer v-model="notifications" title="最近学习动态" size="380px"><div v-if="!events.length" class="muted">暂无活动记录</div><div v-for="event in events" :key="event.id" class="activity-item"><span class="activity-dot"></span><div><p>{{ event.text }}</p><small>{{ dateText(event.created_at,true) }}{{ event.is_seed ? ' · 演示样例' : '' }}</small></div></div></el-drawer>
  </div>
</template>
