<script setup lang="ts">
import Icon from './Icon.vue'
withDefaults(defineProps<{ title?: string, description?: string, icon?: string }>(), { title: '这里还没有内容', description: '完成一次学习活动后，记录会出现在这里。', icon: 'folder' })
</script>
<template><div class="empty-state"><span class="empty-icon"><Icon :name="icon" :size="30" /></span><h3>{{ title }}</h3><p>{{ description }}</p><slot /></div></template>
