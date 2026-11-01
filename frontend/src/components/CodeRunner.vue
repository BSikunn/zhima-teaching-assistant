<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api'
import { useCourseScope } from '../useCourseScope'
import Icon from './Icon.vue'
const props=defineProps<{code:string;language:string}>(), scope=useCourseScope(), stdin=ref(''), result=ref<any>(null), busy=ref(false), error=ref('')
const output=computed(()=>result.value?.result || result.value || {})
const working=(r:any)=>['pending','queued','running','processing'].includes(String(r?.status).toLowerCase())
async function poll(){try{const data=await api.get(`/executions/${result.value.id}`);if(!scope.active())return;result.value=data;if(working(data))scope.schedule(poll);else busy.value=false}catch{if(scope.active()){busy.value=false;error.value='执行状态查询失败，请刷新状态重试。'}}}
async function run(){scope.stop();busy.value=true;error.value='';result.value=null;try{const data=await api.post(`/courses/${scope.courseId}/execute`,{language:props.language,code:props.code,stdin:stdin.value});if(!scope.active())return;result.value=data;if(working(data))scope.schedule(poll);else busy.value=false}catch(e:any){if(scope.active()){error.value=e.response?.status===503?'当前未启用 Judge0 代码执行服务。可继续提交作业获得代码评阅。':typeof e.response?.data?.detail==='string'?e.response.data.detail:'执行请求失败，请稍后重试。';busy.value=false}}}
</script>
<template>
  <details class="code-runner"><summary><Icon name="play" :size="15" />代码试运行</summary><p class="small muted">试运行会将本次代码和标准输入发送至 Judge0 远程沙箱，结果与作业评分分别保存。运行版本与数据库方言由实际沙箱实例决定。</p><label class="small muted">标准输入<textarea v-model="stdin" rows="2" maxlength="12000" aria-label="标准输入" placeholder="按题目需要填写标准输入"></textarea></label><div class="editor-actions"><span class="small muted">{{ language.toUpperCase() }} · 运行环境由服务端限制</span><button type="button" class="btn btn-outline btn-sm" :disabled="busy||!code.trim()" @click="run"><Icon name="play" :size="14" />{{ busy?'执行中…':'运行代码' }}</button></div><div v-if="error" class="error-box">{{ error }}<button v-if="result?.id" class="text-link" @click="poll">刷新执行状态</button></div><div v-if="result" class="execution-result"><span class="tag blue">{{ output.status_label || output.status_description || result.status }}</span><p v-if="output.time!=null" class="small muted">耗时 {{ output.time }} 秒 <template v-if="output.memory!=null"> · 内存 {{ output.memory }} KB</template></p><pre>{{ output.stdout || output.output || output.compile_output || output.stderr || result.error || (busy?'等待运行结果…':'程序无标准输出') }}</pre></div></details>
</template>
