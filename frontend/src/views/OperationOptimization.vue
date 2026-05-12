<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, RadarChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  RadarComponent,
} from 'echarts/components'
import { runEfficiency, runBenchmark, analysisStore } from '../stores'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, BarChart, RadarChart, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, RadarComponent])

const loading = ref(false)
const activeTab = ref('benchmark')

// ---- Benchmark: grouped bar chart ----
const benchmarkBarOption = computed(() => {
  const benchmark = analysisStore.benchmark
  if (!benchmark) return {}

  const gaps = [...benchmark.gaps]
  const indicators = gaps.map(g => g.indicator)
  const thisUnit = gaps.map(g => g.this_unit)
  const peerAvg = gaps.map(g => g.peer_avg)

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['本机组', '同类均值'], top: 0 },
    grid: { left: 120, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: indicators,
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        name: '本机组',
        type: 'bar',
        data: thisUnit,
        itemStyle: { color: '#409eff' },
        barMaxWidth: 18,
      },
      {
        name: '同类均值',
        type: 'bar',
        data: peerAvg,
        itemStyle: { color: '#67c23a' },
        barMaxWidth: 18,
      },
    ],
  }
})

// ---- Benchmark: radar chart ----
const benchmarkRadarOption = computed(() => {
  const benchmark = analysisStore.benchmark
  if (!benchmark) return {}

  const gaps = [...benchmark.gaps]
  const indicators = gaps.map(g => ({
    name: g.indicator,
    max: Math.max(g.this_unit, g.peer_avg) * 1.3,
  }))

  return {
    tooltip: {},
    legend: { data: ['本机组', '同类均值'], top: 0 },
    radar: {
      indicator: indicators,
      radius: '65%',
      name: { textStyle: { fontSize: 11 } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: gaps.map(g => g.this_unit),
            name: '本机组',
            itemStyle: { color: '#409eff' },
            areaStyle: { color: 'rgba(64,158,255,0.15)' },
          },
          {
            value: gaps.map(g => g.peer_avg),
            name: '同类均值',
            itemStyle: { color: '#67c23a' },
            areaStyle: { color: 'rgba(103,194,58,0.15)' },
          },
        ],
      },
    ],
  }
})

// ---- Benchmark: gap deviation bar chart ----
const gapDeviationOption = computed(() => {
  const benchmark = analysisStore.benchmark
  if (!benchmark) return {}

  const sorted = [...benchmark.gaps].sort((a, b) => b.gap - a.gap)
  const indicators = sorted.map(g => g.indicator)
  const gaps = sorted.map(g => round2(g.gap))

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 120, right: 30, top: 20, bottom: 30 },
    xAxis: { type: 'value', name: '差距' },
    yAxis: {
      type: 'category',
      data: indicators,
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: gaps.map(v => ({
          value: v,
          itemStyle: { color: v >= 0 ? '#f56c6c' : '#67c23a' },
        })),
        barMaxWidth: 18,
        label: {
          show: true,
          position: 'right',
          formatter: ({ value }: { value: number }) => (value >= 0 ? '+' : '') + value,
          fontSize: 11,
        },
      },
    ],
  }
})

// ---- Benchmark: table ----
const gapTableData = computed(() => {
  const benchmark = analysisStore.benchmark
  if (!benchmark) return []
  return benchmark.gaps.map(g => ({
    indicator: g.indicator,
    thisUnit: round2(g.this_unit),
    peerAvg: round2(g.peer_avg),
    gap: round2(g.gap),
    unit: g.unit,
    status: g.gap > 0 ? '落后' : g.gap < 0 ? '领先' : '持平',
  }))
})

// ---- Benchmark: strengths / weaknesses ----
const strengths = computed(() => analysisStore.benchmark?.strengths ?? [])
const weaknesses = computed(() => analysisStore.benchmark?.weaknesses ?? [])

// ---- Efficiency suggestions ----
const suggestions = computed(() => analysisStore.efficiency?.suggestions ?? [])

// ---- Efficiency indicators summary ----
const efficiencyIndicators = computed(() => {
  const eff = analysisStore.efficiency
  if (!eff) return []
  return Object.entries(eff.indicators).map(([name, ind]) => ({
    name,
    value: round2(ind.value),
    design: round2(ind.design),
    best: round2(ind.best),
    unit: ind.unit,
    deviation: round2(ind.value - ind.design),
  }))
})

// ---- Efficiency indicator bar chart ----
const efficiencyBarOption = computed(() => {
  const eff = analysisStore.efficiency
  if (!eff) return {}

  const names = Object.keys(eff.indicators)
  const values = names.map(n => round2(eff.indicators[n].value))
  const designs = names.map(n => round2(eff.indicators[n].design))

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['实际值', '设计值'], top: 0 },
    grid: { left: 120, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        name: '实际值',
        type: 'bar',
        data: values,
        itemStyle: { color: '#409eff' },
        barMaxWidth: 18,
      },
      {
        name: '设计值',
        type: 'bar',
        data: designs,
        itemStyle: { color: '#e6a23c' },
        barMaxWidth: 18,
      },
    ],
  }
})

function round2(n: number) {
  return Math.round(n * 100) / 100
}

async function handleRunBoth() {
  loading.value = true
  await Promise.all([runEfficiency(), runBenchmark()])
  loading.value = false
  if (analysisStore.benchmark || analysisStore.efficiency) {
    ElMessage.success('分析完成')
  } else if (analysisStore.error) {
    ElMessage.error(analysisStore.error)
  }
}

async function handleRunEfficiency() {
  loading.value = true
  await runEfficiency()
  loading.value = false
  if (analysisStore.efficiency) ElMessage.success('能效分析完成')
}

async function handleRunBenchmark() {
  loading.value = true
  await runBenchmark()
  loading.value = false
  if (analysisStore.benchmark) ElMessage.success('对标分析完成')
}

function statusType(status: string) {
  if (status === '领先') return 'success'
  if (status === '落后') return 'danger'
  return 'info'
}

function deviationColor(dev: number) {
  if (dev > 0) return '#f56c6c'
  if (dev < 0) return '#67c23a'
  return '#909399'
}

onMounted(() => {
  handleRunBoth()
})
</script>

<template>
  <div class="page-optimization">
    <!-- Top: Triggers -->
    <div class="page-header">
      <el-button type="primary" :loading="loading" @click="handleRunEfficiency">
        执行能效分析
      </el-button>
      <el-button type="success" :loading="loading" @click="handleRunBenchmark">
        执行对标分析
      </el-button>
      <el-button :loading="loading" @click="handleRunBoth">
        同时执行
      </el-button>
      <span v-if="analysisStore.benchmark" class="peer-info">
        对标组: {{ analysisStore.benchmark.peer_group }} | 周期: {{ analysisStore.benchmark.period }}
      </span>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" type="border-card">
      <!-- Tab: 能效分析 -->
      <el-tab-pane label="能效分析" name="efficiency">
        <div v-if="!analysisStore.efficiency" class="empty-state">
          <el-empty description="请先执行能效分析" />
        </div>
        <template v-else>
          <!-- Indicator cards -->
          <el-row :gutter="12" class="indicator-row">
            <el-col v-for="ind in efficiencyIndicators" :key="ind.name" :span="3.4" style="min-width:150px;margin-bottom:12px;">
              <el-card shadow="hover" class="ind-card" :body-style="{ padding: '12px' }">
                <div class="ind-name">{{ ind.name }}</div>
                <div class="ind-value">{{ ind.value }}</div>
                <div class="ind-unit">{{ ind.unit }}</div>
                <div class="ind-dev" :style="{ color: deviationColor(ind.deviation) }">
                  偏差: {{ ind.deviation > 0 ? '+' : '' }}{{ ind.deviation }}
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- Efficiency bar chart -->
          <el-card shadow="never" class="chart-card">
            <template #header><span style="font-weight:600">能效指标对比（实际值 vs 设计值）</span></template>
            <VChart :option="efficiencyBarOption" style="height:300px;width:100%;" autoresize />
          </el-card>

          <!-- Suggestions -->
          <el-card v-if="suggestions.length > 0" shadow="never" class="suggest-card">
            <template #header><span style="font-weight:600">优化建议</span></template>
            <ul class="suggest-list">
              <li v-for="(s, idx) in suggestions" :key="idx">{{ s }}</li>
            </ul>
          </el-card>
        </template>
      </el-tab-pane>

      <!-- Tab: 对标对比 -->
      <el-tab-pane label="对标对比" name="benchmark">
        <div v-if="!analysisStore.benchmark" class="empty-state">
          <el-empty description="请先执行对标分析" />
        </div>
        <template v-else>
          <!-- Row 1: Grouped bar + Radar -->
          <el-row :gutter="16">
            <el-col :span="12">
              <el-card shadow="never" class="chart-card">
                <template #header><span style="font-weight:600">指标对比（本机组 vs 同类均值）</span></template>
                <VChart :option="benchmarkBarOption" style="height:340px;width:100%;" autoresize />
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never" class="chart-card">
                <template #header><span style="font-weight:600">多维雷达图</span></template>
                <VChart :option="benchmarkRadarOption" style="height:340px;width:100%;" autoresize />
              </el-card>
            </el-col>
          </el-row>

          <!-- Row 2: Gap deviation chart -->
          <el-card shadow="never" class="chart-card">
            <template #header><span style="font-weight:600">差距分布（偏差值）</span></template>
            <VChart :option="gapDeviationOption" style="height:280px;width:100%;" autoresize />
          </el-card>

          <!-- Row 3: Table + Strengths/Weaknesses -->
          <el-row :gutter="16">
            <el-col :span="14">
              <el-card shadow="never" class="table-card">
                <template #header><span style="font-weight:600">差距分析明细</span></template>
                <el-table :data="gapTableData" stripe size="small" max-height="300">
                  <el-table-column prop="indicator" label="指标" min-width="130" />
                  <el-table-column prop="thisUnit" label="本机组" width="100" align="center" />
                  <el-table-column prop="peerAvg" label="同类均值" width="100" align="center" />
                  <el-table-column prop="gap" label="差距" width="100" align="center">
                    <template #default="{ row }">
                      <span :style="{ color: parseFloat(row.gap) > 0 ? '#f56c6c' : '#67c23a', fontWeight: 600 }">
                        {{ row.gap }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="unit" label="单位" width="80" align="center" />
                  <el-table-column label="状态" width="80" align="center">
                    <template #default="{ row }">
                      <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>

            <el-col :span="10">
              <el-card shadow="never" class="sw-card">
                <template #header><span style="font-weight:600">优势与劣势</span></template>
                <div class="sw-section">
                  <h4 style="color:#67c23a;margin-bottom:8px;">优势指标</h4>
                  <div v-if="strengths.length === 0" class="empty-tip">暂无优势指标</div>
                  <el-tag v-for="s in strengths" :key="s.indicator" type="success" size="small" style="margin:0 4px 4px 0;">
                    {{ s.indicator }} ({{ round2(s.gap) }})
                  </el-tag>
                </div>
                <el-divider />
                <div class="sw-section">
                  <h4 style="color:#f56c6c;margin-bottom:8px;">劣势指标</h4>
                  <div v-if="weaknesses.length === 0" class="empty-tip">暂无劣势指标</div>
                  <el-tag v-for="w in weaknesses" :key="w.indicator" type="danger" size="small" style="margin:0 4px 4px 0;">
                    {{ w.indicator }} (+{{ round2(w.gap) }})
                  </el-tag>
                </div>
              </el-card>

              <el-card v-if="suggestions.length > 0" shadow="never" class="suggest-card" style="margin-top:16px;">
                <template #header><span style="font-weight:600">优化建议</span></template>
                <ul class="suggest-list">
                  <li v-for="(s, idx) in suggestions" :key="idx">{{ s }}</li>
                </ul>
              </el-card>
            </el-col>
          </el-row>
        </template>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.page-optimization {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.peer-info {
  font-size: 13px;
  color: #909399;
}

.empty-state {
  padding: 40px 0;
}

.chart-card,
.table-card,
.sw-card,
.suggest-card {
  border-radius: 8px;
}

.indicator-row {
  margin-bottom: 8px;
}

.ind-card {
  border-radius: 6px;
  text-align: center;
}

.ind-name {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.ind-value {
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.ind-unit {
  font-size: 11px;
  color: #c0c4cc;
  margin-bottom: 4px;
}

.ind-dev {
  font-size: 11px;
  font-weight: 600;
}

.sw-section h4 {
  font-size: 13px;
}

.empty-tip {
  font-size: 12px;
  color: #c0c4cc;
}

.suggest-list {
  padding-left: 20px;
  margin: 0;
  line-height: 2;
  font-size: 13px;
  color: #606266;
}
</style>
