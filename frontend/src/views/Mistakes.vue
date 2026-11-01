<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useSession } from '../stores/session'
import { api, dateText } from '../api'
import Icon from '../components/Icon.vue'
import EmptyState from '../components/EmptyState.vue'
import GradeResult from '../components/GradeResult.vue'
const session=useSession(), router=useRouter(), rows=ref<any[]>([]), filter=ref('all'), search=ref(''), loading=ref(true), selected=ref<any>(null), detail=ref(false), updating=ref<number|null>(null)
async function load(){loading.value=true;try{rows.value=await api.get(`/courses/${session.courseId}/mistakes`)}finally{loading.value=false}}
onMounted(load)
const visible=computed(()=>rows.value.filter(r=>(filter.value==='all'||r.status===filter.value)&&(!search.value||r.topic.includes(search.value)||r.detail.includes(search.value))))
const pending=computed(()=>rows.value.filter(r=>r.status==='pending').length)
async function toggle(row:any){updating.value=row.id;try{await api.patch(`/mistakes/${row.id}`,{status:row.status==='pending'?'mastered':'pending'});await load();ElMessage.success('复习状态已更新')}finally{updating.value=null}}
</script>
<template>
  <div class="page-heading"><div><span class="eyebrow">TURN MISTAKES INTO PROGRESS</span><h1>每一次卡住，都是下一次进步</h1><p>把错误留下来，把理解带走。回顾之后，再独立做一次。</p></div><button class="btn btn-primary" @click="router.push('/plans')"><Icon name="plan" :size="17" />安排复习计划</button></div>
  <div class="summary-banner"><span class="summary-symbol"><Icon name="mistakes" :size="29" /></span><div><h3>你的专属错题档案</h3><p>共 {{ rows.length }} 条记录，{{ pending }} 条待复习。历史演示记录保留原有标记。</p></div><div class="summary-number"><strong>{{ rows.length-pending }}</strong><span>已标记复习</span></div></div>
  <section class="panel"><div class="toolbar"><div class="tabs"><button v-for="f in [{id:'all',name:'全部错题'},{id:'pending',name:'待复习'},{id:'mastered',name:'已复习'}]" :key="f.id" :class="{active:filter===f.id}" @click="filter=f.id">{{ f.name }}<span v-if="f.id==='pending'">{{ pending }}</span></button></div><div class="search-box"><Icon name="search" :size="17" /><input v-model="search" placeholder="搜索知识点或反馈" aria-label="搜索错题" /></div></div>
    <div v-loading="loading" class="mistake-grid"><article v-for="(m,i) in visible" :key="m.id" class="mistake-card"><div class="section-heading"><span :class="['topic-icon', ['blue','orange','purple'][i%3]]"><Icon name="code" :size="21" /></span><span :class="['tag',m.status==='pending'?'orange':'green']">{{ m.status==='pending'?'待复习':'已复习' }}</span></div><h3>{{ m.topic }}</h3><p class="mistake-feedback">{{ m.detail }}</p><pre>{{ m.code }}</pre><div class="mistake-meta"><span>{{ dateText(m.created_at) }}</span><span v-if="m.is_seed" class="seed-inline">演示样例</span></div><div class="mistake-actions"><button class="text-link" @click="selected=m;detail=true">查看批改反馈<Icon name="chevron" :size="14" /></button><button class="btn btn-outline btn-sm" :disabled="updating===m.id" @click="toggle(m)"><Icon :name="m.status==='pending'?'check':'refresh'" :size="14" />{{ m.status==='pending'?'标记已复习':'重新复习' }}</button></div></article></div><EmptyState v-if="!loading&&!visible.length" title="没有匹配的错题" description="完成作业后，有待复习的问题会自动整理到这里。" /><p class="small muted mt24">复习标记是你的自我记录，不代表系统已验证知识掌握程度。</p></section>
  <el-dialog v-model="detail" title="错题与批改反馈" width="700px"><template v-if="selected"><h3>{{ selected.assignment_title }}</h3><pre class="detail-code">{{ selected.code }}</pre><GradeResult :submission="{grade:selected.grade}" /></template></el-dialog>
</template>
