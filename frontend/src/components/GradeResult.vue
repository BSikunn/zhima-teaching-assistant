<script setup lang="ts">
import { ref, watch } from 'vue'
import Icon from './Icon.vue'
defineProps<{ submission: any }>()
const shown = ref(1)
</script>
<template>
  <div v-if="submission.grade" class="grade-result" data-testid="grade-result">
    <div class="grade-head"><div><span class="eyebrow">LEARNING FEEDBACK</span><h3>{{ submission.grade.reviewed ? '教师已复核' : submission.grade.supported ? '已完成本次批改' : '等待教师评阅' }}</h3><span class="muted small">{{ submission.grade.mode==='demo' ? '规则演示反馈' : 'AI 建议反馈' }} · 未执行学生代码</span></div><div class="grade-score"><strong>{{ submission.grade.score ?? '—' }}</strong><span>分</span></div></div>
    <div class="grade-dimensions"><div v-for="d in submission.grade.dimensions" :key="d.name"><span>{{ d.name }}</span><b>{{ d.score ?? '待评' }}<small> / {{ d.max_score }}</small></b></div></div>
    <div class="feedback-box"><Icon name="bulb" :size="20" /><div><b>{{ submission.grade.error_type || '本次反馈' }}</b><p>{{ submission.grade.feedback }}</p></div></div>
    <div v-if="submission.grade.hints?.length" class="hint-list"><div class="section-heading"><h4>一步一步，自己找到答案</h4><span class="muted small">{{ shown }} / {{ submission.grade.hints.length }}</span></div><p v-for="(hint,i) in submission.grade.hints.slice(0,shown)" :key="i"><span class="step-number">{{ Number(i)+1 }}</span>{{ hint }}</p><button v-if="shown<submission.grade.hints.length" class="btn btn-soft btn-sm" @click="shown++"><Icon name="sparkle" :size="15" />进一步提示</button></div>
    <p v-if="!submission.grade.reviewed" class="small muted mt16">最终评价由教师复核。本次结果已保存到提交记录。</p>
  </div>
</template>
