<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSession } from '../stores/session'
import { api, dateText } from '../api'
import Icon from '../components/Icon.vue'
const session=useSession(), users=ref<any[]>([]), status=ref<any>(null), loading=ref(true)
async function load(){loading.value=true;try{[users.value,status.value]=await Promise.all([api.get('/admin/users'),api.get('/admin/status')])}finally{loading.value=false}}
onMounted(load)
const serviceLabels:Record<string,string>={active:'运行中',local:'本地模式',demo:'演示模式',configured:'已配置',unavailable:'连接异常',error:'连接异常',unconfigured:'未配置'}
const roleName:Record<string,string>={student:'学生',teacher:'教师',admin:'管理员'}
</script>
<template>
  <div class="page-heading"><div><span class="eyebrow">SYSTEM OVERVIEW</span><h1>每项能力，状态清楚</h1><p>查看课程账号与实际服务状态，了解各项能力的可用情况。</p></div><button class="btn btn-outline" :disabled="loading" @click="load"><Icon name="refresh" :size="17" />刷新状态</button></div>
  <div v-if="status" class="admin-summary"><div class="panel"><span class="stat-icon blue"><Icon name="users" :size="24" /></span><div><b>{{ users.length }}<small>个</small></b><span>系统账号</span></div></div><div class="panel"><span class="stat-icon teal"><Icon name="code" :size="24" /></span><div><b>{{ status.python }}</b><span>Python 解释器</span></div></div><div class="panel"><span class="stat-icon purple"><Icon name="database" :size="24" /></span><div><b>{{ session.courses.length }}<small>门</small></b><span>课程</span></div></div></div>
  <section v-loading="loading" class="panel"><div class="section-heading"><div><h3>服务连接状态</h3><p class="muted small">“已配置”仅说明存在配置，不能等同于已通过真实连通测试。</p></div><span class="tag blue">{{ status?.mode==='demo'?'本机演示模式':status?.mode==='deepseek'?'DeepSeek 生成模式':'状态待确认' }}</span></div><p v-if="status?.checked_at" class="small muted">探测时间：{{ dateText(status.checked_at,true) }}</p><div v-if="status" class="service-grid"><article v-for="service in status.services" :key="service.name" class="service-card"><span :class="['service-dot',service.status==='active'?'green':service.status==='configured'||service.status==='error'||service.status==='unavailable'?'orange':'gray']"></span><div><h4>{{ service.name }}</h4><p>{{ service.detail }}</p></div><span :class="['tag',service.status==='active'?'green':service.status==='configured'||service.status==='error'||service.status==='unavailable'?'orange':'gray']">{{ serviceLabels[service.status]||'状态未知' }}</span></article></div></section>
  <section class="panel mt24"><div class="section-heading"><div><h3>系统用户</h3><p class="small muted">学生、教师与管理员按角色访问课程记录。</p></div><span class="tag gray">数据权限由后端校验</span></div><div class="table-scroll"><table class="data-table"><thead><tr><th>用户</th><th>登录账号</th><th>角色</th><th>范围说明</th></tr></thead><tbody><tr v-for="u in users" :key="u.id"><td><div class="file-cell"><span class="avatar avatar-sm">{{ u.name.slice(0,1) }}</span><b>{{ u.name }}</b></div></td><td><code>{{ u.username }}</code></td><td><span :class="['tag',u.role==='admin'?'purple':u.role==='teacher'?'blue':'green']">{{ roleName[u.role] }}</span></td><td class="muted small">{{ u.role==='student'?'个人对话、作业、测验、错题、计划与报告':u.role==='teacher'?'所属课程资料、作业与学情':'用户列表、课程与系统状态' }}</td></tr></tbody></table></div></section>
</template>
