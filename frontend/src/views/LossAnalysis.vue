<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent,
} from 'echarts/components'
import { runLoss, runDecomposition, analysisStore } from '../stores'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const loading = ref(false)
const aggregation = ref('raw')  // raw / 1d / 1w
const lossMode = ref<'coal' | 'optimal'>('coal')

const modeLabel = computed(() => (lossMode.value === 'optimal' ? '对标最优' : '对标基准'))

// ────── 因素耗差明细（基于当前评估模式的 main_value） ──────

interface FactorRow {
  name: string
  subsystem: string
  value: number | null
  referValue: number | null
  main_value: number | null
}

const factorRows = computed<FactorRow[]>(() => {
  const loss = analysisStore.loss as any
  if (!loss) return []
  // 优先用 factor_ranking（扁平，含归属子系统，已按 |main_value| 排序）
  const ranking = loss.factor_ranking
  if (Array.isArray(ranking) && ranking.length) {
    return ranking.map((f: any) => ({
      name: f.name || '',
      subsystem: f.subsystem || '',
      value: f.value ?? null,
      referValue: f.referValue ?? null,
      main_value: f.main_value ?? null,
    }))
  }
  // 回退：从 subsystems[].factors 扁平展开
  const rows: FactorRow[] = []
  for (const s of loss.subsystems || []) {
    for (const f of s.factors || []) {
      rows.push({
        name: f.name || '',
        subsystem: s.name || '',
        value: f.value ?? null,
        referValue: f.referValue ?? null,
        main_value: f.main_value ?? null,
      })
    }
  }
  return rows
})

const totalMain = computed(() => (analysisStore.loss as any)?.total?.main_value ?? null)

// ────── 图表 ──────

const barOption = computed(() => {
  const data = factorRows.value
    .filter(r => r.main_value != null)
    .sort((a, b) => Math.abs(b.main_value!) - Math.abs(a.main_value!))
  if (data.length === 0) return {}
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 120, right: 40, top: 20, bottom: 30 },
    xAxis: { type: 'value', name: 'g/kWh' },
    yAxis: { type: 'category', data: data.map(d => d.name), axisLabel: { fontSize: 11 } },
    series: [
      {
        name: modeLabel.value, type: 'bar',
        data: data.map(d => d.main_value),
        itemStyle: { color: '#409eff' }, barMaxWidth: 18,
        label: { show: true, position: 'right', fontSize: 10 },
      },
    ],
  }
})

const waterfallOption = computed(() => {
  const decomp = analysisStore.decomposition as any
  if (!decomp) return {}
  const subs = (decomp.subsystems || []).filter((s: any) => s.main_value != null)
  if (subs.length === 0) return {}

  const names: string[] = subs.map((s: any) => s.name)
  const values: number[] = subs.map((s: any) => s.main_value)

  // 瀑布：子系统 main_value 逐级累加，最后一根柱为总量
  let cumulative = 0
  const helperData: number[] = []
  const positiveData: (number | null)[] = []
  const negativeData: (number | null)[] = []
  for (const v of values) {
    if (v >= 0) { helperData.push(cumulative); positiveData.push(v); negativeData.push(null); cumulative += v }
    else { cumulative += v; helperData.push(cumulative); positiveData.push(null); negativeData.push(Math.abs(v)) }
  }
  const totalLabel = decomp.total?.name || '能耗偏差'
  const totalValue = decomp.total?.main_value ?? cumulative
  names.push(totalLabel)
  helperData.push(0); positiveData.push(null); negativeData.push(null)
  const totalSeries: (number | null)[] = names.map(() => null)
  totalSeries[totalSeries.length - 1] = totalValue

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['增加', '减少', '总量'], top: 0 },
    grid: { left: 30, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: names, axisLabel: { fontSize: 10, rotate: names.length > 6 ? 30 : 0 } },
    yAxis: { type: 'value', name: 'g/kWh' },
    series: [
      { name: '辅助', type: 'bar', stack: 'waterfall', data: helperData, itemStyle: { color: 'transparent' }, tooltip: { show: false }, barMaxWidth: 30 },
      { name: '增加', type: 'bar', stack: 'waterfall', data: positiveData, itemStyle: { color: '#f56c6c' }, barMaxWidth: 30 },
      { name: '减少', type: 'bar', stack: 'waterfall', data: negativeData, itemStyle: { color: '#67c23a' }, barMaxWidth: 30 },
      { name: '总量', type: 'bar', data: totalSeries, itemStyle: { color: '#909399' }, barMaxWidth: 30 },
    ],
  }
})

// ────── 执行分析 ──────

async function handleRunAnalysis() {
  loading.value = true
  await Promise.all([
    runLoss(aggregation.value, lossMode.value),
    runDecomposition(lossMode.value, aggregation.value),
  ])
  loading.value = false
  if (analysisStore.loss) ElMessage.success('耗差分析完成')
  else if (analysisStore.error) ElMessage.error(analysisStore.error)
}

watch([aggregation, lossMode], () => handleRunAnalysis())

onMounted(() => handleRunAnalysis())
</script>

<template>
  <div class="page-loss">
    <!-- Top: Trigger + 聚合 + 评估模式 -->
    <div class="page-header">
      <el-button type="primary" :loading="loading" @click="handleRunAnalysis">执行耗差分析</el-button>
      <el-select v-model="aggregation" style="width: 120px;">
        <el-option value="raw" label="实时值" />
        <el-option value="1d" label="按天均值" />
        <el-option value="1w" label="按周均值" />
      </el-select>
      <el-radio-group v-model="lossMode" size="small">
        <el-radio-button value="coal">对标基准</el-radio-button>
        <el-radio-button value="optimal">对标最优</el-radio-button>
      </el-radio-group>
      <span v-if="totalMain != null" class="total-loss">
        综合能耗偏差（{{ modeLabel }}）:
        <strong :style="{ color: totalMain > 0 ? '#f56c6c' : '#67c23a' }">{{ totalMain }}</strong> g/kWh
      </span>
    </div>

    <!-- Charts Row -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span style="font-weight:600">因素耗差对比（{{ modeLabel }}，按影响权重排序）</span></template>
          <VChart v-if="factorRows.length > 0" :option="barOption" style="height:320px;width:100%;" autoresize />
          <el-empty v-else description="暂无耗差数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span style="font-weight:600">子系统偏差分解（{{ modeLabel }}，瀑布图）</span></template>
          <VChart v-if="analysisStore.decomposition" :option="waterfallOption" style="height:320px;width:100%;" autoresize />
          <el-empty v-else description="请先执行耗差分析" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Detail Table -->
    <el-card shadow="never" class="table-card">
      <template #header><span style="font-weight:600">因素耗差明细（{{ modeLabel }}）</span></template>
      <el-table :data="factorRows" stripe size="small">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="name" label="因素" min-width="160" />
        <el-table-column prop="subsystem" label="归属子系统" width="130" />
        <el-table-column label="运行值" width="110" align="center">
          <template #default="{ row }">{{ row.value ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="基准值" width="110" align="center">
          <template #default="{ row }">{{ row.referValue ?? '-' }}</template>
        </el-table-column>
        <el-table-column :label="modeLabel + ' (g/kWh)'" width="160" align="center">
          <template #default="{ row }">
            <span :style="{ color: (row.main_value ?? 0) > 0 ? '#f56c6c' : '#67c23a' }">{{ row.main_value ?? '-' }}</span>
          </template>
        </el-table-column>
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
.page-header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; flex-shrink: 0; }
.total-loss { font-size: 14px; color: #606266; }
.chart-card, .table-card { border-radius: 8px; }
</style>
