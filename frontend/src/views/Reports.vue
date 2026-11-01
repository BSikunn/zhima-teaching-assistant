<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, dateText, statusText } from '../api'
import { useSession } from '../stores/session'
import { useCourseScope } from '../useCourseScope'
import Icon from '../components/Icon.vue'
import EmptyState from '../components/EmptyState.vue'
const session=useSession(), scope=useCourseScope(), rows=ref<any[]>([]), selected=ref<any>(null), busy=ref(false), loading=ref(true), error=ref(false)
const working=(r:any)=>['pending','generating','processing'].includes(r?.status)
async function load(){scope.stop();error.value=false;try{const data=await api.get(`/courses/${scope.courseId}/reports`);if(!scope.active())return;rows.value=data;if(selected.value){const id=selected.value.id;const current=await api.get(`/reports/${id}`);if(!scope.active())return;if(selected.value?.id===id)selected.value=current}if(data.some(working))scope.schedule(load)}catch{if(scope.active())error.value=true}finally{if(scope.active())loading.value=false}}
async function choose(row:any){const version=++selectionVersion;const data=await api.get(`/reports/${row.id}`);if(scope.active()&&version===selectionVersion)selected.value=data}
async function generate(){busy.value=true;try{const data=await api.post(`/courses/${scope.courseId}/reports`,{});if(!scope.active())return;selected.value=data;await load()}finally{if(scope.active())busy.value=false}}
async function retry(){busy.value=true;try{const data=await api.post(`/reports/${selected.value.id}/retry`);if(!scope.active())return;selected.value=data;await load()}finally{if(scope.active())busy.value=false}}
let selectionVersion=0
onMounted(load)
</script>
<template>
  <div class="page-heading"><div><span class="eyebrow">LEARNING WITH PERSPECTIVE</span><h1>{{ session.isStudent?'让成长，有一份清楚的记录':'从学情出发，安排下一步教学' }}</h1><p>{{ session.isStudent?'整合当前课程的学习记录、薄弱点与改进方向。':'汇总当前课程的真实学习记录，形成教学观察与建议。' }}</p></div><button class="btn btn-primary" data-testid="report-generate" :disabled="busy" @click="generate"><Icon name="sparkle" :size="16" />{{ busy?'正在保存…':session.isStudent?'生成学习报告':'生成教学报告' }}</button></div>
  <div class="review-note"><Icon name="chart" :size="23" /><div><b>{{ session.course?.title }} · {{ session.isStudent?'个人学习报告':'课程教学报告' }}</b><p>统计来自已保存的课程记录。报告中的模型建议应结合实际表现核对。</p></div></div>
  <div v-if="error" class="error-box">报告加载失败，请点击刷新记录重试。</div>
  <div v-loading="loading" class="task-layout"><aside class="panel task-history"><div class="section-heading"><h3>报告记录</h3><button class="icon-btn" aria-label="刷新报告记录" @click="load"><Icon name="refresh" :size="17" /></button></div><button v-for="row in rows" :key="row.id" class="task-history-item" :class="{selected:selected?.id===row.id}" @click="choose(row)"><div><b>{{ row.title || '课程报告 #'+row.id }}</b><span class="tag" :class="row.status==='failed'?'orange':working(row)?'blue':'green'">{{ statusText[row.status]||row.status }}</span></div><small>{{ dateText(row.created_at,true) }}</small></button><EmptyState v-if="!loading&&!rows.length" title="还没有报告" description="生成报告后可随时回看与下载。" /></aside><section class="panel task-detail"><template v-if="selected"><div class="section-heading"><div><span class="eyebrow">COURSE LEARNING REPORT</span><h2>{{ selected.title || '课程报告' }}</h2><p class="small muted">{{ dateText(selected.created_at,true) }} · {{ statusText[selected.status]||selected.status }}</p></div><button v-if="['ready','completed'].includes(selected.status)" class="btn btn-outline btn-sm" data-testid="report-download" @click="api.downloadReport(selected.id,(selected.title||'学习报告')+'.md')"><Icon name="download" :size="16" />下载报告</button></div><div v-if="working(selected)" class="task-progress"><Icon name="clock" :size="23" /><div><b>正在整理统计与学习建议</b><p>任务已保存，页面将自动刷新。也可以稍后回来查看。</p></div></div><div v-if="selected.status==='failed'" class="error-box"><Icon name="alert" :size="20" /><div><b>报告生成未完成</b><p>{{ selected.error || '服务暂时不可用，请稍后重试。' }}</p><button class="btn btn-outline btn-sm" :disabled="busy" @click="retry">重新生成</button></div></div><div v-if="selected.content" class="report-text" data-testid="report-content">{{ selected.content }}</div></template><EmptyState v-else title="把学习足迹，连成一份报告" description="选择历史报告，或生成一份当前课程的报告。" icon="file" /></section></div>
</template>
