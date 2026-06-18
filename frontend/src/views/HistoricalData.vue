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
  runHistoricalLossAnalysis,
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

// ────── 耗差分析结果（loss_analysis_tool 偏差分解） ──────

const lossResult = ref<any>(null)
const lossLoading = ref(false)
const lossMode = ref<'coal' | 'optimal'>('coal')

function onLossModeChange() {
  // 切换评估模式后，若已有结果则按新模式重新分析
  if (lossResult.value && dateRange.value) handleLossAnalysis()
}

const lossSummary = computed(() => {
  if (!lossResult.value) return null
  const r = lossResult.value
  const total = r.total || {}
  const zd = r.zone_distribution || null
  return {
    total_points: r.total_data_points,
    has_loss: total.main_value != null,
    main_value: total.main_value,
    eval_mode: r.eval_mode || 'coal',
    mode_label: r.eval_mode === 'optimal' ? '对标最优' : '对标基准',
    subsystems: r.subsystems || [],
    ranking: r.factor_ranking || [],
    zone_strategy: r.zone_strategy,
    zones: zd ? [
      { id: 1, label: '极低负荷（<10%，已舍去）', color: '#909399', count: zd.zone1?.count ?? 0, ratio: zd.zone1?.ratio ?? 0, avg_load_rate: zd.zone1?.avg_load_rate ?? 0 },
      { id: 2, label: '部分负荷（10%~60%）', color: '#e6a23c', count: zd.zone2?.count ?? 0, ratio: zd.zone2?.ratio ?? 0, avg_load_rate: zd.zone2?.avg_load_rate ?? 0 },
      { id: 3, label: '高负荷（>60%）', color: '#f56c6c', count: zd.zone3?.count ?? 0, ratio: zd.zone3?.ratio ?? 0, avg_load_rate: zd.zone3?.avg_load_rate ?? 0 },
    ] : null,
  }
})

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

// ────── 耗差分析（直接调用 loss_analysis_tool 偏差分解） ──────

async function handleLossAnalysis() {
  if (!dateRange.value) {
    ElMessage.warning('请先选择时间范围')
    return
  }
  const [start, end] = dateRange.value
  const startStr = toLocalISOString(start)
  const endStr = toLocalISOString(end)

  lossLoading.value = true
  try {
    const res = await runHistoricalLossAnalysis({
      start: startStr,
      end: endStr,
      unit_id: unitId.value,
      aggregation: aggregation.value === 'raw' ? '1h' : aggregation.value,
      mode: lossMode.value,
    })
    if (res.error) {
      ElMessage.error(res.error)
      return
    }
    lossResult.value = res.result
    ElMessage.success('耗差分析完成')
  } catch (e: any) {
    ElMessage.error('耗差分析失败: ' + (e.response?.data?.detail || e.message || e))
  } finally {
    lossLoading.value = false
  }
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
            :loading="lossLoading"
            :disabled="!dateRange"
            @click="handleLossAnalysis"
          >
            耗差分析
          </el-button>
          <el-radio-group v-model="lossMode" size="small" @change="onLossModeChange" style="margin-left:8px;">
            <el-radio-button value="coal">对标基准</el-radio-button>
            <el-radio-button value="optimal">对标最优</el-radio-button>
          </el-radio-group>
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
              <span style="font-size:12px; color:#909399;">耗时 {{ lossResult.elapsed_ms }}ms · {{ lossResult.total_data_points }} 个数据点</span>
            </div>
          </template>

          <el-alert
            v-if="!lossSummary?.has_loss"
            type="warning"
            :closable="false"
            show-icon
            style="margin-top:4px;"
          >
            <template #title>该时段数据不含已算好的耗差值（coalLossValue），无法执行偏差分解</template>
            <div style="margin-top:6px; font-size:13px; line-height:1.6;">
              偏差分解需基于系统上报的「{因素}_coalLossValue」时序项。请确认导入数据包含这些耗差字段，或在「数据问答」中提问（将综合统计摘要与知识库作答）。
            </div>
          </el-alert>

          <template v-else>
          <!-- 关键汇总指标 -->
          <el-row :gutter="12" style="margin-bottom:14px;">
            <el-col :span="8" v-if="lossSummary?.main_value != null">
              <div class="metric-card">
                <div class="metric-label">综合能耗偏差（{{ lossSummary.mode_label }}）</div>
                <div class="metric-value" :style="{color: lossSummary.main_value > 0 ? '#f56c6c' : '#67c23a'}">{{ lossSummary.main_value }}<small> g/kWh</small></div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="metric-card">
                <div class="metric-label">评估模式</div>
                <div class="metric-value" style="font-size:16px;">{{ lossSummary?.mode_label }}</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="metric-card">
                <div class="metric-label">分析数据点</div>
                <div class="metric-value">{{ lossSummary?.total_points ?? 0 }}</div>
              </div>
            </el-col>
          </el-row>

          <!-- 负荷率区间分布 -->
          <div v-if="lossSummary?.zones" style="margin-bottom:14px;">
            <div style="font-size:13px; font-weight:600; margin-bottom:8px; color:#303133;">负荷率区间分布（按负荷率三区间）</div>
            <div v-for="z in lossSummary.zones" :key="z.id" style="margin-bottom:6px;">
              <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">
                <span>{{ z.label }}</span>
                <span style="color:#909399;">{{ z.count }} 点（{{ z.ratio }}%），平均负荷 {{ z.avg_load_rate }}%</span>
              </div>
              <el-progress :percentage="z.ratio" :show-text="false" :color="z.color" />
            </div>
          </div>

          <!-- 子系统贡献分解 -->
          <div v-if="lossSummary?.subsystems?.length" style="margin-bottom:14px;">
            <div style="font-size:13px; font-weight:600; margin-bottom:8px; color:#303133;">子系统贡献分解</div>
            <div v-for="s in lossSummary.subsystems" :key="s.name" style="margin-bottom:8px;">
              <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">
                <span>{{ s.name }}</span>
                <span :style="{color: s.main_value > 0 ? '#f56c6c' : '#67c23a'}">{{ s.main_value }} g/kWh（权重 {{ s.contribution_to_total }}%）</span>
              </div>
              <el-progress :percentage="s.contribution_to_total" :show-text="false" :color="s.main_value > 0 ? '#f56c6c' : '#67c23a'" />
              <div v-if="s.factors?.length" style="font-size:11px; color:#909399; margin-top:2px;">
                主要因素：<span v-for="(f, i) in s.factors.slice(0,3)" :key="f.name">{{ i > 0 ? '、' : '' }}{{ f.name }}({{ f.main_value }})</span>
              </div>
            </div>
          </div>

          <!-- 因素耗差排名 -->
          <div v-if="lossSummary?.ranking?.length" style="margin-bottom:14px;">
            <div style="font-size:13px; font-weight:600; margin-bottom:8px; color:#303133;">因素耗差排名（影响权重 Top 5）</div>
            <el-table :data="lossSummary.ranking.slice(0,5)" size="small" border>
              <el-table-column type="index" label="#" width="40" />
              <el-table-column prop="name" label="因素" />
              <el-table-column label="归属子系统" prop="subsystem" width="120" />
              <el-table-column :label="lossSummary.mode_label + ' (g/kWh)'" width="160">
                <template #default="{ row }">
                  <span :style="{color: (row.main_value ?? 0) > 0 ? '#f56c6c' : '#67c23a'}">{{ row.main_value }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 文字报告 -->
          <div class="loss-report">{{ lossResult.report }}</div>
          </template>
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

.metric-card {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 10px 12px;
}

.metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.metric-value small {
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

.loss-report {
  white-space: pre-wrap;
  word-break: break-word;
  background: #fafafa;
  border-left: 3px solid #409eff;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.7;
  color: #303133;
  max-height: 360px;
  overflow-y: auto;
}
</style>
