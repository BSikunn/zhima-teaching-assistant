<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '../stores/session'
import Icon from '../components/Icon.vue'
const router=useRouter(), session=useSession()
const role=ref('student'), username=ref('student'), password=ref('Demo12345!'), busy=ref(false)
function choose(value: string) { role.value=value; username.value=value }
async function login() { busy.value=true; try { await session.login(username.value,password.value); await router.push('/overview') } catch {} finally { busy.value=false } }
</script>
<template>
  <div class="login-page"><header class="login-header"><div class="brand"><span class="brand-mark"><Icon name="code" :size="27" /></span><b>智码助教<span class="brand-dot">.</span></b></div><span class="small muted">面向编程课程的教学智能体</span></header>
    <div class="login-body"><section class="login-story"><span class="story-eyebrow"><span class="status-dot"></span>YOUR LEARNING COPILOT</span><h1>从一个问题开始，<br>走向真正的<span>理解。</span></h1><p>有依据的回答，有方向的练习。<br>让编程学习的每一步，都有回应。</p><div class="login-code-card"><div class="code-window-bar"><i></i><i></i><i></i><span>learning.sql</span></div><pre><span class="code-purple">SELECT</span> understanding<br><span class="code-purple">FROM</span> every_question<br><span class="code-purple">WHERE</span> curiosity <span class="code-teal">IS NOT NULL</span>;</pre><div class="code-answer"><Icon name="sparkle" :size="18" /><span>保留好奇，让知识真正发生连接。</span><span class="tiny-badge">智码助教</span></div></div><div class="story-features"><span><Icon name="badge" :size="18" />课程依据可追溯</span><span><Icon name="bulb" :size="18" />启发式分步辅导</span><span><Icon name="chart" :size="18" />学习反馈成闭环</span></div></section>
    <section class="login-card"><span class="eyebrow">WELCOME BACK</span><h2>开启你的学习空间</h2><p class="muted">选择身份，进入课程教学与学习空间</p><div class="role-selector"><button v-for="r in [{id:'student',name:'学生',icon:'graduation'},{id:'teacher',name:'教师',icon:'book'},{id:'admin',name:'管理员',icon:'shield'}]" :key="r.id" :class="{selected:role===r.id}" :data-testid="'role-'+r.id" @click="choose(r.id)"><Icon :name="r.icon" :size="21" />{{ r.name }}</button></div><label v-if="role==='student'" class="student-select">学生身份<select v-model="username" aria-label="学生身份"><option value="student">张三 · student</option><option value="student2">李四 · student2</option><option value="student3">王五 · student3</option></select></label><form @submit.prevent="login"><label>登录账号<input v-model="username" autocomplete="username" placeholder="请输入账号" required /></label><label>登录密码<input v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" required /></label><div class="login-account-note"><span class="status-dot"></span>已填入所选身份的初始账号</div><button class="btn btn-primary login-submit" :disabled="busy" data-testid="login-submit"><span>{{ busy ? '正在进入…' : '进入工作台' }}</span><Icon name="arrow" :size="18" /></button></form><div class="login-demo-note"><Icon name="alert" :size="17" /><p>本机初始账号密码：<code>Demo12345!</code></p></div></section></div>
    <footer class="login-footer">智码助教 · 以课程为依据，让学习有回响<span>数据库 · Python · Java</span></footer>
  </div>
</template>
