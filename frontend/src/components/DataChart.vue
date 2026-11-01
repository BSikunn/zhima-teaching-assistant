<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([BarChart, LineChart, PieChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])
const props = withDefaults(defineProps<{ data: any[], type?: 'line' | 'pie', height?: number }>(), { type: 'line', height: 220 })
const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | undefined, observer: ResizeObserver | undefined
function render() {
  if (!chart) return
  const palette = ['#4263ed', '#f2b35c', '#6fc9c1', '#9a8ad4', '#9eb3f0']
  chart.setOption(props.type === 'pie' ? {
    color: palette, tooltip: { trigger: 'item' },
    legend: { bottom: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { color: '#7c849b', fontSize: 11 } },
    series: [{ type: 'pie', radius: ['55%', '76%'], center: ['50%', '42%'], avoidLabelOverlap: true, label: { show: false }, itemStyle: { borderColor: '#fff', borderWidth: 5, borderRadius: 7 }, data: props.data }],
  } : {
    color: palette, tooltip: { trigger: 'axis' }, grid: { top: 14, right: 20, bottom: 26, left: 30 },
    xAxis: { type: 'category', boundaryGap: false, data: props.data.map(d => d.date), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#949bb0', margin: 16, fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#949bb0', fontSize: 11 }, splitLine: { lineStyle: { color: '#f0f2f7', type: 'dashed' } } },
    series: [{ type: 'line', smooth: true, symbol: 'circle', symbolSize: 7, data: props.data.map(d => d.count), lineStyle: { width: 3 }, itemStyle: { borderWidth: 3, borderColor: '#fff' }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(66,99,237,.16)' }, { offset: 1, color: 'rgba(66,99,237,0)' }]) } }],
  }, true)
}
onMounted(() => { chart = echarts.init(el.value!); render(); observer = new ResizeObserver(() => chart?.resize()); observer.observe(el.value!) })
watch(() => props.data, render, { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>
<template><div ref="el" :style="{height: height+'px', width: '100%'}" /></template>
