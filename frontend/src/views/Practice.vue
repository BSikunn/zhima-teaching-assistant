<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api, dateText, statusText } from '../api'
import { useSession } from '../stores/session'
import { useCourseScope } from '../useCourseScope'
import Icon from '../components/Icon.vue'
import EmptyState from '../components/EmptyState.vue'
const session = useSession(), scope = useCourseScope()
const rows = ref<any[]>([]), selected = ref<any>(null), answers = ref<string[]>([]), mode = ref('quiz'), count = ref(3), busy = ref(false), loading = ref(true), error = ref(false)
const working = (s: any) => ['pending', 'generating', 'pending_grade', 'grading'].includes(s?.status)
const finished = computed(() => ['graded', 'completed'].includes(selected.value?.status))
const feedbackText = computed(() => typeof selected.value?.feedback === 'string' ? selected.value.feedback : selected.value?.feedback?.feedback || selected.value?.feedback?.summary || '')
const feedbackItems = computed(() => Array.isArray(selected.value?.feedback) ? selected.value.feedback : selected.value?.feedback?.items || selected.value?.feedback?.questions || selected.value?.feedback?.results || [])
let selectionVersion = 0
function restoreAnswers(data: any) {
  answers.value = (data.questions || []).map((_: any, i: number) => data.answers?.[i] || '')
}
async function load() {
  scope.stop(); error.value = false
  try {
    const data = await api.get(`/courses/${scope.courseId}/practice-sessions`)
    if (!scope.active()) return
    rows.value = data
    if (selected.value) { const id = selected.value.id; const current = await api.get(`/practice-sessions/${id}`); if (!scope.active()) return; if (selected.value?.id === id) { selected.value = current; if (current.status === 'ready' && answers.value.length !== current.questions?.length) restoreAnswers(current) } }
    if (data.some(working)) scope.schedule(load)
  } catch { if (scope.active()) error.value = true } finally { if (scope.active()) loading.value = false }
}
async function choose(row: any) {
  const version = ++selectionVersion
  const data = await api.get(`/practice-sessions/${row.id}`)
  if (!scope.active() || version !== selectionVersion) return
  selected.value = data; restoreAnswers(data)
}
async function generate() {
  busy.value = true
  try { const data = await api.post(`/courses/${scope.courseId}/practice-sessions`, { mode: mode.value, count: count.value }); if (!scope.active()) return; ++selectionVersion; selected.value = data; restoreAnswers(data); await load() }
  finally { if (scope.active()) busy.value = false }
}
async function submit() {
  if (!selected.value || answers.value.length !== selected.value.questions.length || answers.value.some(a => !a?.trim())) return
  busy.value = true
  try { const data = await api.post(`/practice-sessions/${selected.value.id}/answers`, { answers: answers.value, request_id: crypto.randomUUID() }); if (!scope.active()) return; selected.value = data; restoreAnswers(data); await load() }
  finally { if (scope.active()) busy.value = false }
}
async function retry() {
  busy.value = true
  try { const data = await api.post(`/practice-sessions/${selected.value.id}/retry`); if (!scope.active()) return; selected.value = data; await load() }
  finally { if (scope.active()) busy.value = false }
}
onMounted(load)
</script>
<template>
  <div class="page-heading"><div><span class="eyebrow">THINK · PRACTICE · REFLECT</span><h1>{{ session.isStudent ? '用一次练习，检验真正的理解' : '看见学生的思考过程' }}</h1><p>{{ session.isStudent ? '基于当前课程生成题目，独立作答后查看评阅与改进建议。' : '查看本课程学生的测验与面试记录，了解薄弱知识点。' }}</p></div><button class="btn btn-outline" :disabled="busy" @click="load"><Icon name="refresh" :size="16" />刷新记录</button></div>
  <section v-if="session.isStudent" class="panel practice-create"><div><h3>开始一次课程练习</h3><p class="small muted">{{ session.course?.title }} · 参考答案在提交后开放</p></div><label>练习模式<select v-model="mode" aria-label="练习模式"><option value="quiz">课程测验</option><option value="interview">模拟面试</option></select></label><label>题目数量<select v-model.number="count" aria-label="题目数量"><option v-for="n in 5" :key="n" :value="n">{{ n }} 题</option></select></label><button class="btn btn-primary" data-testid="practice-generate" :disabled="busy" @click="generate"><Icon name="sparkle" :size="16" />{{ busy ? '正在保存…' : '生成练习' }}</button></section>
  <div v-if="error" class="error-box">练习记录加载失败，可点击刷新重新加载。</div>
  <div v-loading="loading" class="task-layout"><aside class="panel task-history"><div class="section-heading"><h3>{{ session.isStudent ? '我的练习' : '课程练习记录' }}</h3><span class="count-badge">{{ rows.length }}</span></div><button v-for="row in rows" :key="row.id" class="task-history-item" :class="{selected:selected?.id===row.id}" @click="choose(row)"><div><b>{{ row.mode==='interview'?'模拟面试':'课程测验' }} #{{ row.id }}</b><span class="tag" :class="row.status==='failed'?'orange':working(row)?'blue':'green'">{{ statusText[row.status] || row.status }}</span></div><p v-if="row.student_name || row.user_name">{{ row.student_name || row.user_name }}</p><small>{{ dateText(row.created_at,true) }}</small></button><EmptyState v-if="!loading&&!rows.length" title="还没有练习记录" :description="session.isStudent?'生成一次练习，从独立思考开始。':'学生生成练习后，记录会显示在这里。'" /></aside>
    <section class="panel task-detail"><template v-if="selected"><div class="section-heading"><div><span class="eyebrow">{{ selected.mode==='interview'?'MOCK INTERVIEW':'COURSE QUIZ' }}</span><h2>{{ selected.mode==='interview'?'模拟面试':'课程测验' }} #{{ selected.id }}</h2></div><span class="tag blue">{{ statusText[selected.status] || selected.status }}</span></div>
      <div v-if="working(selected)" class="task-progress"><Icon name="clock" :size="22" /><div><b>{{ ['grading','pending_grade'].includes(selected.status)?'正在评阅你的回答':'正在准备课程题目' }}</b><p>任务已保存，将自动刷新；离开后可从历史记录继续查看。</p></div></div>
      <div v-if="selected.status==='failed'" class="error-box"><Icon name="alert" :size="20" /><div><b>本次处理未完成</b><p>{{ selected.error || '服务暂时不可用，请稍后重试。' }}</p><button v-if="session.isStudent" class="btn btn-outline btn-sm" :disabled="busy" @click="retry">重试任务</button></div></div>
      <form v-if="selected.questions?.length" class="stack-form" @submit.prevent="submit"><article v-for="(question,i) in selected.questions" :key="i" class="practice-question"><div><span class="step-number">{{ Number(i)+1 }}</span><span class="tag gray">{{ question.topic }}</span></div><h3>{{ question.prompt }}</h3><label v-if="session.isStudent&&selected.status==='ready'&&(selected.mode!=='interview'||Number(i)===(selected.answered_count||0))">{{ selected.mode==='interview'?'说说你的思路':'你的回答' }}<textarea v-model="answers[Number(i)]" rows="5" required maxlength="12000" :aria-label="'第'+(Number(i)+1)+'题回答'"></textarea></label></article><button v-if="session.isStudent&&selected.status==='ready'" class="btn btn-primary" data-testid="practice-submit" :disabled="busy||answers.length!==selected.questions.length||answers.some(a=>!a?.trim())"><Icon name="send" :size="16" />{{ selected.mode==='interview'?'提交本轮回答':'提交全部回答' }}</button></form>
      <p v-if="!session.isStudent&&!finished" class="small muted mt24">教师查看课程练习记录；作答由学生在个人学习空间完成。</p>
      <div v-if="selected.feedback" class="practice-feedback" data-testid="practice-feedback"><div class="section-heading"><h3>{{ finished?'本次练习反馈':'已完成轮次反馈' }}</h3><span v-if="selected.feedback?.score!=null" class="tag green">{{ selected.feedback.score }} 分</span></div><p v-if="feedbackText" class="report-text">{{ feedbackText }}</p><article v-for="(item,i) in feedbackItems" :key="i" class="feedback-box"><Icon name="bulb" :size="20" /><div><b>第 {{ Number(i)+1 }} 题 <span v-if="item.score!=null">· {{ item.score }} 分</span></b><p v-if="item.answer || item.student_answer">你的回答：{{ item.answer || item.student_answer }}</p><p>{{ item.feedback || item.explanation || item.comment }}</p><p v-if="item.reference_answer || item.reference">参考思路：{{ item.reference_answer || item.reference }}</p></div></article><p v-if="!feedbackText&&!feedbackItems.length" class="report-text">{{ JSON.stringify(selected.feedback,null,2) }}</p><p class="small muted mt16">模型评阅用于辅助学习，关键结论请结合课程资料与教师反馈核对。</p></div>
    </template><EmptyState v-else title="选择一次练习，看看自己的思考" description="生成中的任务和已完成的反馈都会保存在左侧。" icon="assignment" /></section></div>
</template>
