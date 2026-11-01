<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useSession } from '../stores/session'
import { api, dateText } from '../api'
import Icon from '../components/Icon.vue'
import EmptyState from '../components/EmptyState.vue'
import { useCourseScope } from '../useCourseScope'
const scope=useCourseScope()
const session=useSession(), plans=ref<any[]>([]), chosen=ref<number|null>(null), loading=ref(true), busy=ref(false), updating=ref<number|null>(null)
const plan=computed(()=>plans.value.find(p=>p.id===chosen.value)||plans.value[0]), done=computed(()=>plan.value?.items.filter((i:any)=>i.done).length||0), duration=computed(()=>plan.value?.items.reduce((s:number,i:any)=>s+i.duration,0)||0)
onMounted(async()=>{try{const rows=await api.get(`/courses/${scope.courseId}/plans`);if(scope.active())plans.value=rows}finally{if(scope.active())loading.value=false}})
async function generate(){busy.value=true;try{const p=await api.post(`/courses/${scope.courseId}/plans`,{});if(!scope.active())return;plans.value.unshift(p);chosen.value=p.id;ElMessage.success('复习计划已生成并保存')}finally{if(scope.active())busy.value=false}}
async function toggle(item:any){updating.value=item.id;try{const result=await api.patch(`/plan-items/${item.id}`,{done:!item.done});item.done=result.done}finally{updating.value=null}}
</script>
<template>
  <div class="page-heading"><div><span class="eyebrow">SMALL STEPS · REAL PROGRESS</span><h1>把下一步，变得具体</h1><p>依据你的错题记录，安排一份可以慢慢完成的复习计划。</p></div><button class="btn btn-primary" data-testid="generate-plan" :disabled="busy" @click="generate"><Icon :name="busy?'refresh':'sparkle'" :size="17" />{{ busy?'正在整理…':'生成我的复习计划' }}</button></div>
  <div class="plan-intro"><span><Icon name="bulb" :size="24" /></span><div><b>不追求一次学完，先完成一个小目标。</b><p>回顾课程 → 解释错误 → 独立练习 → 再次验证，让知识真正属于自己。</p></div><Icon name="layers" :size="55" /></div>
  <section v-loading="loading" class="panel"><template v-if="plan"><div class="section-heading"><div><span class="eyebrow">YOUR PERSONAL PLAN</span><h2>{{ plan.title }}</h2><p class="small muted">{{ dateText(plan.created_at,true) }} 创建</p></div><select v-if="plans.length>1" v-model="chosen" aria-label="历史复习计划" class="compact-select"><option v-for="p in plans" :key="p.id" :value="p.id">{{ dateText(p.created_at,true) }} · #{{ p.id }}</option></select><span v-else class="tag purple">专属复习路径</span></div><p class="plan-basis"><Icon name="file" :size="16" />{{ plan.basis }}</p><div class="plan-progress"><div><span>已完成 {{ done }} / {{ plan.items.length }} 项</span><span>建议投入 {{ duration }} 分钟</span></div><div class="progress-track"><i :style="{width:(done/plan.items.length*100)+'%'}"></i></div></div><div class="plan-timeline"><article v-for="(item,i) in plan.items" :key="item.id" :class="['plan-task',{done:item.done}]"><span class="plan-task-index">{{ String(Number(i)+1).padStart(2,'0') }}</span><div class="flex-one"><span class="tag gray"><Icon name="clock" :size="12" />{{ item.duration }} 分钟</span><h3>{{ item.title }}</h3><p>{{ item.description }}</p><RouterLink to="/chat" class="text-link">带着问题向助教提问<Icon name="arrowUp" :size="14" /></RouterLink></div><button class="task-check" :class="{checked:item.done}" :disabled="updating===item.id" data-testid="plan-item" :aria-label="item.done?'标记未完成':'标记已完成'" @click="toggle(item)"><Icon v-if="item.done" name="check" :size="18" /></button></article></div><div v-if="done===plan.items.length" class="plan-complete"><Icon name="success" :size="24" /><div><b>这份计划已完成，给坚持一个回应。</b><p>试着独立完成一道相似题，看看自己是否真正理解了。</p></div></div></template><EmptyState v-else-if="!loading" title="你的复习路径，即将开始" description="点击右上角生成计划，系统会整理当前错题；没有错题时会提供基础练习建议。" icon="plan" /></section>
</template>
