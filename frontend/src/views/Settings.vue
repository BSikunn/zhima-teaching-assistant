<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useSession } from '../stores/session'
import { api } from '../api'
import Icon from '../components/Icon.vue'
const session=useSession(), config=ref<any>(null), busy=ref(false), loading=ref(true)
onMounted(async()=>{try{config.value=await api.get(`/courses/${session.courseId}/config`)}finally{loading.value=false}})
async function save(){busy.value=true;try{await api.put(`/courses/${session.courseId}/config`,config.value);ElMessage.success('智能体设置已保存，将用于后续问答与批改')}finally{busy.value=false}}
</script>
<template>
  <div class="page-heading"><div><span class="eyebrow">YOUR COURSE · YOUR TEACHING APPROACH</span><h1>把你的教学方式，交给助教</h1><p>设定助教的角色与辅导尺度，让每次回应贴近这门课的目标。</p></div><span class="tag blue"><Icon name="book" :size="14" />仅作用于当前课程</span></div>
  <div v-loading="loading" class="settings-layout"><section class="panel settings-main"><form v-if="config" class="stack-form" @submit.prevent="save"><div class="settings-section-heading"><span class="topic-icon blue"><Icon name="bot" :size="23" /></span><div><h3>助教角色</h3><p>先定义如何陪伴学生学习</p></div></div><label>智能体人设<input v-model="config.persona" maxlength="200" required placeholder="例如：耐心、严谨的本课程助教" /></label><label>课程提示词<textarea v-model="config.prompt" rows="8" maxlength="6000" required></textarea><small>用于当前课程的问答、辅导和出题；历史结果保留原有生成方式。</small></label><div class="settings-section-heading bordered"><span class="topic-icon purple"><Icon name="bulb" :size="23" /></span><div><h3>启发式辅导</h3><p>给学生留出独立思考的空间</p></div></div><div class="switch-row"><div><b>优先提供思考线索</b><p>开启后，先给提示，再逐步展开解释。</p></div><el-switch v-model="config.hint_first" /></div><label>最大提示层级<select v-model.number="config.max_hint_level"><option :value="1">1 级 · 只提供初步线索</option><option :value="2">2 级 · 展开关键推理</option><option :value="3">3 级 · 提供完整提示</option></select></label><div class="dialog-actions"><span class="muted small">保存后仅影响新请求，历史结果保留。</span><button class="btn btn-primary" :disabled="busy"><Icon name="check" :size="16" />{{ busy?'保存中…':'保存课程设置' }}</button></div></form></section><aside class="settings-side"><section class="panel principle-panel"><span class="welcome-icon"><Icon name="graduation" :size="29" /></span><h3>助教的目标，<br>是让学生学会。</h3><p>答案有依据，提示有分寸，评价有教师把关。</p><ul><li><Icon name="badge" :size="17" />优先引用当前课程资料</li><li><Icon name="bulb" :size="17" />先提问、再引导、再解释</li><li><Icon name="review" :size="17" />关键评分由教师复核</li></ul></section><div class="settings-boundary"><Icon name="shield" :size="19" /><p>服务连接由管理员在部署环境中配置。此处仅管理课程教学方式。</p></div></aside></div>
</template>
