<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, TreeChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import { runLoss, runDecomposition, analysisStore } from '../stores'
import * as api from '../api'
import type { CausalGraph } from '../types'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, BarChart, TreeChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const loading = ref(false)

const barOption = computed(() => {
  const items = analysisStore.loss?.items ?? []
  if (items.length === 0) return {}
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['当前值', '设计值'], top: 0 },
    grid: { left: 100, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'value', name: '损失值' },
    yAxis: { type: 'category', data: items.map(i => i.name), axisLabel: { fontSize: 11 } },
    series: [
      { name: '当前值', type: 'bar', data: items.map(i => i.value), itemStyle: { color: '#409eff' }, barMaxWidth: 20 },
      { name: '设计值', type: 'bar', data: items.map(i => i.design), itemStyle: { color: '#e6a23c' }, barMaxWidth: 20 },
    ],
  }
})

const waterfallOption = computed(() => {
  const decomp = analysisStore.decomposition
  if (!decomp) return {}
  const subsystems = decomp.subsystems
  const names = Object.keys(subsystems)
  const values = names.map(n => subsystems[n].contribution)
  let cumulative = 0
  const helperData: number[] = []
  const positiveData: (number | null)[] = []
  const negativeData: (number | null)[] = []
  for (const v of values) {
    if (v >= 0) { helperData.push(cumulative); positiveData.push(v); negativeData.push(null); cumulative += v }
    else { cumulative += v; helperData.push(cumulative); positiveData.push(null); negativeData.push(Math.abs(v)) }
  }
  names.push('总损失'); helperData.push(0); positiveData.push(null); negativeData.push(null)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['增加', '减少', '合计'], top: 0 },
    grid: { left: 30, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: names, axisLabel: { fontSize: 10, rotate: names.length > 6 ? 30 : 0 } },
    yAxis: { type: 'value', name: '贡献值' },
    series: [
      { name: '辅助', type: 'bar', stack: 'waterfall', data: helperData, itemStyle: { color: 'transparent' }, tooltip: { show: false }, barMaxWidth: 30 },
      { name: '增加', type: 'bar', stack: 'waterfall', data: positiveData, itemStyle: { color: '#f56c6c' }, barMaxWidth: 30 },
      { name: '减少', type: 'bar', stack: 'waterfall', data: negativeData, itemStyle: { color: '#67c23a' }, barMaxWidth: 30 },
    ],
  }
})

const lossTableData = computed(() => {
  return (analysisStore.loss?.items ?? []).map(item => ({
    name: item.name,
    value: item.value.toFixed(4),
    design: item.design.toFixed(4),
    delta: (item.value - item.design).toFixed(4),
    deltaPct: item.design !== 0 ? (((item.value - item.design) / item.design) * 100).toFixed(2) + '%' : '-',
  }))
})

async function handleRunAnalysis() {
  loading.value = true
  await Promise.all([runLoss(), runDecomposition()])
  loading.value = false
  if (analysisStore.loss) ElMessage.success('耗差分析完成')
  else if (analysisStore.error) ElMessage.error(analysisStore.error)
}

onMounted(() => { handleRunAnalysis() })
</script>

<template>
  <div class="page-loss">
    <!-- Top: Trigger -->
    <div class="page-header">
      <el-button type="primary" :loading="loading" @click="handleRunAnalysis">执行耗差分析</el-button>
      <span v-if="analysisStore.loss" class="total-loss">
        总损失: <strong>{{ analysisStore.loss.total_loss.toFixed(4) }}</strong>
        (设计: {{ analysisStore.loss.total_design_loss.toFixed(4) }})
      </span>
    </div>

    <!-- Charts Row -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span style="font-weight:600">各损失项当前值 vs 设计值</span></template>
          <VChart v-if="analysisStore.loss" :option="barOption" style="height:320px;width:100%;" autoresize />
          <el-empty v-else description="请先执行耗差分析" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span style="font-weight:600">子系统损失分解（瀑布图）</span></template>
          <VChart v-if="analysisStore.decomposition" :option="waterfallOption" style="height:320px;width:100%;" autoresize />
          <el-empty v-else description="请先执行耗差分析" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Detail Table — full display, no inner scroll -->
    <el-card shadow="never" class="table-card">
      <template #header><span style="font-weight:600">损失项明细</span></template>
      <el-table :data="lossTableData" stripe size="small">
        <el-table-column prop="name" label="损失项" min-width="180" />
        <el-table-column prop="value" label="当前值" width="120" align="center" />
        <el-table-column prop="design" label="设计值" width="120" align="center" />
        <el-table-column prop="delta" label="偏差" width="120" align="center">
          <template #default="{ row }">
            <span :style="{ color: parseFloat(row.delta) > 0 ? '#f56c6c' : '#67c23a' }">{{ row.delta }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="deltaPct" label="偏差率" width="100" align="center" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.page-loss {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}
.page-header { display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
.total-loss { font-size: 14px; color: #606266; }
.chart-card, .table-card { border-radius: 8px; }
</style>
