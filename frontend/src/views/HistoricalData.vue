<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, DataLine } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DataZoomComponent, ToolboxComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  getTimeRange,
  queryTimeSeries,
  getParameterStats,
  getParameters,
} from '../api'
import type { TimeRangeInfo, ParameterStat, ParameterDefinition } from '../types'
import HistoricalChatPanel from '../components/HistoricalChatPanel.vue'

use([
  LineChart, TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DataZoomComponent, ToolboxComponent, CanvasRenderer,
])

// ────── 状态 ──────

const parameters = ref<ParameterDefinition[]>([])
const paramLoading = ref(false)
const timeRange = ref<TimeRangeInfo>({ has_data: false, unit_id: 'GT-01' })

// 查询条件
const dateRange = ref<[Date, Date] | null>(null)
const selectedParams = ref<string[]>([])
const aggregation = ref('raw')
const unitId = ref('GT-01')

// 查询结果
const querying = ref(false)
const chartData = ref<Record<string, (number | null | string)[]>>({})
const stats = ref<ParameterStat[]>([])
const periodDays = ref(0)
const pointCount = ref(0)

// ────── 耗差分析结果 ──────

interface PeriodLossItem {
  name: string
  value: number
  design: number
  best?: number
  unit: string
}

const lossResult = ref<{
  total_loss: number
  total_design_loss: number
  total_best_loss: number
  items: PeriodLossItem[]
  major_losses: PeriodLossItem[]
} | null>(null)

// ────── 参数名映射 ──────

const parameterNames = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  for (const p of parameters.value) {
    const key = (p as any).key || p.name.replace(/ /g, '_')
    map[key] = p.name
  }
  return map
})

// ────── 计算属性 ──────

const groupedParams = computed(() => {
  const groups: Record<string, { key: string; name: string; unit: string }[]> = {}
  for (const p of parameters.value) {
    const sub = (p as any).subsystem || '其他'
    if (!groups[sub]) groups[sub] = []
    groups[sub].push({ key: (p as any).key || p.name.replace(/ /g, '_'), name: p.name, unit: p.unit })
  }
  return groups
})

const chartOption = computed(() => {
  // 检查是否有数据（兼容新旧格式）
  const keys = Object.keys(chartData.value)
  if (keys.length === 0) return {}

  const hasNewFormat = keys.some(k => {
    const d = chartData.value[k]
    return d && typeof d === 'object' && 'timestamp' in d && 'values' in d
  })

  const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#b37feb', '#36cfc9', '#ff85c0']
  const usedUnits = new Map<string, number>()
  const series: any[] = []

  if (hasNewFormat) {
    // 新格式：每个参数独立 {timestamp: [], values: []}
    selectedParams.value.forEach((key, idx) => {
      const paramData = chartData.value[key]
      const timestamps = paramData?.timestamp || []
      const values = paramData?.values || []
      if (timestamps.length === 0) return

      const param = parameters.value.find(p => (p as any).key === key || p.name.replace(/ /g, '_') === key)
      const unit = param?.unit || ''
      const name = param?.name || key

      if (!usedUnits.has(unit)) {
        usedUnits.set(unit, usedUnits.size)
      }
      const yAxisIdx = usedUnits.get(unit)!

      series.push({
        name,
        type: 'line',
        data: values.map((v: any, i: number) => [timestamps[i], v]),
        yAxisIndex: yAxisIdx,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5 },
        itemStyle: { color: colors[idx % colors.length] },
      })
    })
  } else {
    // 旧格式：共享 timestamp + 各参数值数组
    const timestamps = chartData.value['timestamp'] || []
    if (timestamps.length === 0) return {}

    selectedParams.value.forEach((key, idx) => {
      const values = chartData.value[key] || []
      const param = parameters.value.find(p => (p as any).key === key || p.name.replace(/ /g, '_') === key)
      const unit = param?.unit || ''
      const name = param?.name || key

      if (!usedUnits.has(unit)) {
        usedUnits.set(unit, usedUnits.size)
      }
      const yAxisIdx = usedUnits.get(unit)!

      series.push({
        name,
        type: 'line',
        data: values.map((v: any, i: number) => [timestamps[i], v]),
        yAxisIndex: yAxisIdx,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5 },
        itemStyle: { color: colors[idx % colors.length] },
      })
    })
  }

  if (series.length === 0) return {}

  // 构建Y轴（数组格式，ECharts 要求）
  const yAxisArr: any[] = []
  usedUnits.forEach((idx, unit) => {
    yAxisArr[idx] = {
      type: 'value',
      name: unit,
      position: idx % 2 === 0 ? 'left' : 'right',
      offset: Math.floor(idx / 2) * 60,
      axisLabel: { fontSize: 11 },
      nameTextStyle: { fontSize: 11 },
      splitLine: { show: idx === 0 },
    }
  })

  return {
    backgroundColor: '#fff',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: series.map(s => s.name),
      bottom: 0,
      type: 'scroll',
    },
    grid: {
      left: usedUnits.size > 0 ? 60 + Math.floor(usedUnits.size / 2) * 60 : 60,
      right: usedUnits.size > 1 ? 60 + Math.floor((usedUnits.size - 1) / 2) * 60 : 30,
      top: 30,
      bottom: 50,
    },
    xAxis: {
      type: 'time',
      axisLabel: {
        fontSize: 11,
        formatter: (val: number) => {
          const d = new Date(val)
          return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
        },
      },
    },
    yAxis: yAxisArr,
    series,
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, height: 20, bottom: 25 },
    ],
  }
})

const statsColumns = computed(() => {
  return selectedParams.value.map(key => {
    const s = stats.value.find(st => st.parameter_key === key)
    const p = parameters.value.find(pp => (pp as any).key === key || pp.name.replace(/ /g, '_') === key)
    return {
      key,
      name: p?.name || key,
      unit: p?.unit || '',
      ...s,
    }
  })
})

// ────── 方法 ──────

async function loadParameters() {
  paramLoading.value = true
  try {
    const res = await getParameters()
    parameters.value = res.parameters
  } catch (e: any) {
    ElMessage.error('加载参数失败: ' + (e.message || e))
  } finally {
    paramLoading.value = false
  }
}

async function loadTimeRange() {
  try {
    timeRange.value = await getTimeRange(unitId.value)
    if (timeRange.value.has_data && timeRange.value.max_timestamp && timeRange.value.min_timestamp) {
      const end = new Date(timeRange.value.max_timestamp)
      const start = new Date(timeRange.value.min_timestamp)
      dateRange.value = [start, end]
    }
  } catch { /* ignore */ }
}

function toLocalISOString(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

async function handleQuery() {
  if (!dateRange.value || selectedParams.value.length === 0) {
    ElMessage.warning('请选择时间范围和至少一个参数')
    return
  }

  querying.value = true
  chartData.value = {}
  stats.value = []

  try {
    const [start, end] = dateRange.value
    const startStr = toLocalISOString(start)
    const endStr = toLocalISOString(end)

    const [tsResult, statsResult] = await Promise.all([
      queryTimeSeries({
        parameter_keys: selectedParams.value,
        start: startStr,
        end: endStr,
        unit_id: unitId.value,
        aggregation: aggregation.value,
      }),
      getParameterStats({
        parameter_keys: selectedParams.value,
        start: startStr,
        end: endStr,
        unit_id: unitId.value,
      }),
    ])

    chartData.value = tsResult.data || {}
    periodDays.value = tsResult.period_days
    pointCount.value = tsResult.point_count
    stats.value = statsResult.stats || []

    if (pointCount.value === 0) {
      ElMessage.warning('未查询到数据，请检查时间范围和参数选择')
    }
  } catch (e: any) {
    ElMessage.error('查询失败: ' + (e.response?.data?.detail || e.message || e))
  } finally {
    querying.value = false
  }
}

// ────── 耗差分析（直接基于统计摘要） ──────

function handleLossAnalysis() {
  if (stats.value.length === 0) {
    ElMessage.warning('请先查询数据，确保统计摘要已生成')
    return
  }

  const items: PeriodLossItem[] = stats.value
    .filter(s => s.has_data !== false)
    .map(s => {
      const mean = s.mean ?? 0
      const nrMin = s.normal_min
      const nrMax = s.normal_max

      // 基准值：正常范围中点；最优值：正常范围上限（理想状态）
      let baseline: number, best: number
      if (nrMin != null && nrMax != null) {
        baseline = +((nrMin + nrMax) / 2).toFixed(4)
        best = +(nrMax).toFixed(4)
      } else {
        baseline = +(mean).toFixed(4)
        best = +(mean * 0.95).toFixed(4)
      }

      return {
        name: s.parameter_name || s.parameter_key,
        unit: s.unit || '',
        value: +(mean).toFixed(4),
        design: baseline,
        best,
      }
    })

  lossResult.value = {
    total_loss: +(items.reduce((s, i) => s + i.value, 0)).toFixed(4),
    total_design_loss: +(items.reduce((s, i) => s + i.design, 0)).toFixed(4),
    total_best_loss: +(items.reduce((s, i) => s + i.best, 0)).toFixed(4),
    items,
    major_losses: items
      .filter(i => i.value > i.design * 1.2)
      .sort((a, b) => (b.value - b.design) - (a.value - a.design)),
  }
  ElMessage.success('耗差分析完成')
}

function formatValue(val: number | null) {
  if (val === null || val === undefined) return '-'
  return val.toFixed(2)
}

// ────── 初始化 ──────

onMounted(async () => {
  await loadParameters()
  await loadTimeRange()
})
</script>

<template>
  <div class="historical-page">
    <h2 style="margin: 0 0 16px; font-size: 20px;">历史数据分析</h2>

    <!-- 查询条件 -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <el-form :inline="true" style="display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end;">
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            style="width: 360px;"
          />
        </el-form-item>

        <el-form-item label="参数">
          <el-select
            v-model="selectedParams"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择参数"
            filterable
            style="min-width: 280px; max-width: 400px;"
          >
            <el-option-group v-for="(items, group) in groupedParams" :key="group" :label="group">
              <el-option v-for="item in items" :key="item.key"
                         :label="`${item.name} (${item.unit})`" :value="item.key" />
            </el-option-group>
          </el-select>
        </el-form-item>

        <el-form-item label="聚合">
          <el-select v-model="aggregation" style="width: 100px;">
            <el-option value="raw" label="原始" />
            <el-option value="5min" label="5分钟" />
            <el-option value="15min" label="15分钟" />
            <el-option value="1h" label="1小时" />
            <el-option value="1d" label="1天" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :icon="Search" :loading="querying" @click="handleQuery">
            查询
          </el-button>
          <el-button :icon="Refresh" @click="loadTimeRange">刷新范围</el-button>
          <el-button
            type="warning"
            :icon="DataLine"
            :disabled="stats.length === 0"
            @click="handleLossAnalysis"
          >
            耗差分析
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 数据范围提示 -->
      <div v-if="timeRange.has_data" style="color: #909399; font-size: 12px; margin-top: 8px;">
        数据范围: {{ timeRange.min_timestamp?.replace('T', ' ')?.slice(0, 19) }}
        ~ {{ timeRange.max_timestamp?.replace('T', ' ')?.slice(0, 19) }}
        (共 {{ timeRange.total_points?.toLocaleString() }} 个数据点)
      </div>
      <div v-else style="color: #e6a23c; font-size: 12px; margin-top: 8px;">
        暂无数据，请先在"数据导入"页面上传历史文件
      </div>
    </el-card>

    <!-- 趋势图 -->
    <el-card v-if="Object.keys(chartData).length > 0" shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>趋势图 ({{ periodDays }} 天, {{ pointCount.toLocaleString() }} 个数据点)</span>
        </div>
      </template>
      <v-chart :option="chartOption" autoresize style="height: 450px;" />
    </el-card>

    <!-- 统计摘要 -->
    <el-card v-if="stats.length > 0" shadow="never" style="margin-bottom: 16px;">
      <template #header>统计摘要</template>
      <el-table :data="statsColumns" size="small" stripe border>
        <el-table-column label="参数" min-width="180">
          <template #default="{ row }">{{ row.name }} ({{ row.unit }})</template>
        </el-table-column>
        <el-table-column label="数据量" prop="count" width="90" />
        <el-table-column label="均值" width="100">
          <template #default="{ row }">{{ formatValue(row.mean) }}</template>
        </el-table-column>
        <el-table-column label="标准差" width="100">
          <template #default="{ row }">{{ formatValue(row.std) }}</template>
        </el-table-column>
        <el-table-column label="最小值" width="100">
          <template #default="{ row }">{{ formatValue(row.min) }}</template>
        </el-table-column>
        <el-table-column label="最大值" width="100">
          <template #default="{ row }">{{ formatValue(row.max) }}</template>
        </el-table-column>
        <el-table-column label="正常范围" width="140">
          <template #default="{ row }">
            <span v-if="row.normal_min != null">
              {{ row.normal_min }} ~ {{ row.normal_max }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="超限次数" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.out_of_range_count > 0 ? '#f56c6c' : '#67c23a' }">
              {{ row.out_of_range_count }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 耗差分析结果 + 智能问答 -->
    <el-row v-if="lossResult || stats.length > 0" :gutter="16">
      <!-- 耗差分析结果 -->
      <el-col :span="lossResult ? 14 : 24">
        <el-card v-if="lossResult" shadow="never">
          <template #header>
            <div style="display:flex; align-items:center; justify-content:space-between;">
              <span style="font-weight:600">耗差分析结果</span>
              <span style="font-size:13px; color:#606266;">
                总损失: <strong style="color:#f56c6c;">{{ lossResult.total_loss?.toFixed(2) }}</strong>
                (基准: {{ lossResult.total_design_loss?.toFixed(2) }},
                最优: {{ lossResult.total_best_loss?.toFixed(2) }})
              </span>
            </div>
          </template>
          <el-table :data="lossResult.items" size="small" stripe>
            <el-table-column prop="name" label="损失项" min-width="160" />
            <el-table-column prop="unit" label="单位" width="70" align="center" />
            <el-table-column prop="value" label="当前值" width="90" align="center">
              <template #default="{ row }">{{ row.value?.toFixed(4) }}</template>
            </el-table-column>
            <el-table-column prop="design" label="基准值" width="90" align="center">
              <template #default="{ row }">{{ row.design?.toFixed(4) }}</template>
            </el-table-column>
            <el-table-column prop="best" label="最优值" width="90" align="center">
              <template #default="{ row }">{{ (row.best ?? row.design * 0.7)?.toFixed(4) }}</template>
            </el-table-column>
            <el-table-column label="vs 基准" width="90" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.value > row.design ? '#f56c6c' : '#67c23a' }">
                  {{ (row.value - row.design)?.toFixed(4) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="vs 最优" width="90" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.value > (row.best ?? row.design * 0.7) ? '#f56c6c' : '#67c23a' }">
                  {{ (row.value - (row.best ?? row.design * 0.7))?.toFixed(4) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="lossResult.major_losses?.length > 0" style="margin-top: 12px;">
            <el-tag type="danger" size="small">主要损失项</el-tag>
            <span v-for="ml in lossResult.major_losses" :key="ml.name" style="margin-left: 8px; font-size: 13px;">
              {{ ml.name }} ({{ ml.value?.toFixed(2) }})
            </span>
          </div>
        </el-card>
      </el-col>

      <!-- 智能问答面板 -->
      <el-col :span="lossResult ? 10 : 24">
        <HistoricalChatPanel
          :date-range="dateRange"
          :selected-params="selectedParams"
          :parameter-names="parameterNames"
          :stats="stats"
        />
      </el-col>
    </el-row>

    <!-- 当没有查询结果时，也显示问答面板（如果有数据范围） -->
    <el-row v-if="!lossResult && stats.length === 0 && timeRange.has_data" :gutter="16">
      <el-col :span="24">
        <HistoricalChatPanel
          :date-range="dateRange"
          :selected-params="selectedParams"
          :parameter-names="parameterNames"
          :stats="stats"
        />
      </el-col>
    </el-row>

    <!-- 空状态 -->
    <el-empty v-if="!querying && Object.keys(chartData).length === 0 && timeRange.has_data && stats.length === 0"
              description="请选择时间范围和参数后点击查询" />
  </div>
</template>

<style scoped>
.historical-page {
  max-width: 1400px;
  margin: 0 auto;
}
</style>
