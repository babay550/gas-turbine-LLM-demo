<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
} from 'echarts/components'
import { fetchEfficiencyTrend, realtimeStore } from '../stores'
import { runEfficiency, analysisStore } from '../stores'
import type { EfficiencyIndicator } from '../types'
import { ElMessage } from 'element-plus'
import * as api from '../api'

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent])

const loading = ref(false)
const mockActive = ref(false)

// --- SCADA raw value groups mapped to indicators ---
interface ScadaField { key: string; label: string; unit: string }
interface IndicatorGroup {
  name: string
  scadaFields: ScadaField[]
}

const indicatorGroups: Record<string, IndicatorGroup> = {
  '发电气耗': {
    name: '发电气耗',
    scadaFields: [
      { key: '天然气瞬时流量', label: '天然气瞬时流量', unit: '万Nm³/h' },
      { key: '天然气累计流量', label: '天然气累计流量', unit: '万Nm³' },
      { key: '发电机有功功率', label: '发电机有功功率', unit: 'MW' },
      { key: '累计发电量', label: '累计发电量', unit: 'MWh' },
      { key: '燃气温度', label: '燃气温度', unit: '°C' },
      { key: '燃气压力', label: '燃气压力', unit: 'MPa' },
    ],
  },
  '压气机效率': {
    name: '压气机效率',
    scadaFields: [
      { key: '压气机进口温度_T1', label: '进口温度 T1', unit: '°C' },
      { key: '压气机进口压力_P1', label: '进口压力 P1', unit: 'MPa' },
      { key: '压气机出口温度_T2', label: '出口温度 T2', unit: '°C' },
      { key: '压气机出口压力_P2', label: '出口压力 P2', unit: 'MPa' },
    ],
  },
  '燃烧效率': {
    name: '燃烧效率',
    scadaFields: [
      { key: '天然气瞬时流量', label: '天然气流量', unit: '万Nm³/h' },
      { key: '天然气低位热值', label: '低位热值', unit: 'MJ/Nm³' },
      { key: '空气流量', label: '出口空气流量', unit: 'kg/s' },
      { key: '压气机出口温度_T2', label: '出口空气温度', unit: '°C' },
      { key: '压气机出口压力_P2', label: '出口空气压力', unit: 'MPa' },
      { key: '透平进口温度_T3', label: '透平进口温度 T3', unit: '°C' },
      { key: '燃烧室出口压力_P3', label: '燃烧室出口压力 P3', unit: 'MPa' },
      { key: '排烟含氧量', label: '排烟含氧量', unit: '%' },
      { key: 'CO排放', label: 'CO排放', unit: 'ppm' },
      { key: '未燃碳氢', label: '未燃碳氢', unit: 'ppm' },
    ],
  },
  '透平效率': {
    name: '透平效率',
    scadaFields: [
      { key: '透平进口温度_T3', label: '进口温度 T3', unit: '°C' },
      { key: '燃烧室出口压力_P3', label: '进口压力 P3', unit: 'MPa' },
      { key: '透平出口温度_T4', label: '出口温度 T4', unit: '°C' },
      { key: '透平出口压力_P4', label: '出口压力 P4', unit: 'MPa' },
      { key: '天然气瞬时流量', label: '燃气流量', unit: '万Nm³/h' },
    ],
  },
  '热耗率': {
    name: '热耗率',
    scadaFields: [
      { key: '天然气累计流量', label: '天然气累计流量', unit: '万Nm³' },
      { key: '天然气低位热值', label: '低位热值', unit: 'MJ/Nm³' },
      { key: '发电机有功功率', label: '燃机发电功率', unit: 'MW' },
      { key: '累计发电量', label: '累计发电量', unit: 'MWh' },
      { key: '压气机进口温度_T1', label: '压气机进口温度', unit: '°C' },
      { key: '压气机出口温度_T2', label: '压气机出口温度', unit: '°C' },
      { key: '透平进口温度_T3', label: '透平进口温度', unit: '°C' },
      { key: '透平出口温度_T4', label: '透平出口温度', unit: '°C' },
    ],
  },
  '发电效率': {
    name: '发电效率',
    scadaFields: [],  // 3600 / 热耗率，无独立 SCADA
  },
  '联合循环效率': {
    name: '联合循环效率',
    scadaFields: [
      { key: '天然气瞬时流量', label: '燃机燃料流量', unit: '万Nm³/h' },
      { key: '天然气低位热值', label: '燃料热值', unit: 'MJ/Nm³' },
      { key: '发电机有功功率', label: '燃机发电量', unit: 'MW' },
      { key: '主蒸汽流量', label: '主蒸汽流量', unit: 't/h' },
      { key: '主蒸汽温度', label: '主蒸汽温度', unit: '°C' },
      { key: '主蒸汽压力', label: '主蒸汽压力', unit: 'MPa' },
      { key: '汽机发电功率', label: '汽机发电量', unit: 'MW' },
      { key: 'HRB进口烟温', label: 'HRB进口烟温', unit: '°C' },
      { key: 'HRB出口烟温', label: 'HRB出口烟温', unit: '°C' },
      { key: 'HRB蒸汽温度', label: 'HRB蒸汽温度', unit: '°C' },
      { key: 'HRB蒸汽压力', label: 'HRB蒸汽压力', unit: 'MPa' },
    ],
  },
}

// Map indicator to component position
const componentMapping: Record<string, string> = {
  '发电气耗': 'generator',
  '压气机效率': 'compressor',
  '燃烧效率': 'combustion',
  '透平效率': 'turbine',
  '热耗率': 'overall',
  '发电效率': 'overall',
  '联合循环效率': 'combined',
}

const scada = computed(() => analysisStore.efficiency?.scada ?? {})
const indicators = computed(() => analysisStore.efficiency?.indicators ?? {})

function getIndicatorValue(name: string): EfficiencyIndicator | null {
  return indicators.value[name] ?? null
}

/** 安全格式化指标值 */
function fmtValue(name: string, decimals = 2): string {
  const ind = indicators.value[name]
  if (!ind || ind.value == null) return '-'
  return ind.value.toFixed(decimals)
}

function fmtDesign(name: string, decimals = 2): string {
  const ind = indicators.value[name]
  if (!ind || ind.design == null) return '-'
  return ind.design.toFixed(decimals)
}

function fmtBest(name: string, decimals = 2): string {
  const ind = indicators.value[name]
  if (!ind || ind.best == null) return '-'
  return ind.best.toFixed(decimals)
}

function indUnit(name: string): string {
  return indicators.value[name]?.unit ?? ''
}

function getScadaValue(key: string): string {
  const val = scada.value[key]
  if (val === undefined) return '-'
  if (Math.abs(val) >= 1000) return val.toFixed(0)
  if (Math.abs(val) < 0.01) return val.toFixed(4)
  return val.toFixed(2)
}

function deviationColor(ind: EfficiencyIndicator | null): string {
  if (!ind) return '#909399'
  const dev = ind.value - ind.design
  if (Math.abs(dev / ind.design) < 0.02) return '#67c23a'
  return dev > 0 ? '#f56c6c' : '#e6a23c'
}

function deviationText(ind: EfficiencyIndicator | null): string {
  if (!ind) return '-'
  const dev = ((ind.value - ind.design) / ind.design * 100).toFixed(1)
  return `${dev > 0 ? '+' : ''}${dev}%`
}

// --- Trend chart ---
const trendOption = computed(() => {
  const data = realtimeStore.trend?.data
  if (!data) return {}
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['热耗率', '设计值'], top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: data['日期'], axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: 'kJ/kWh', axisLabel: { fontSize: 11 } },
    series: [
      { name: '热耗率', type: 'line', data: data['热耗率_kJ/kWh'], smooth: true, itemStyle: { color: '#409eff' }, areaStyle: { color: 'rgba(64,158,255,0.1)' } },
      { name: '设计值', type: 'line', data: Array(data['日期'].length).fill(8000), lineStyle: { type: 'dashed', color: '#f56c6c' }, itemStyle: { color: '#f56c6c' }, symbol: 'none' },
    ],
  }
})

async function handleRunAnalysis() {
  loading.value = true
  await runEfficiency()
  loading.value = false
  if (analysisStore.efficiency) ElMessage.success('能效分析完成')
  else if (analysisStore.error) ElMessage.error(analysisStore.error)
}

async function handleMockToggle() {
  const next = !mockActive.value
  try {
    const res = await api.toggleMockMode(next)
    mockActive.value = res.mock_active
    ElMessage.success(res.message)
    // 重新加载分析数据
    await fetchEfficiencyTrend(7)
    await handleRunAnalysis()
  } catch (e: unknown) {
    ElMessage.error('切换失败: ' + (e instanceof Error ? e.message : String(e)))
  }
}

onMounted(async () => {
  // 查询当前 mock 状态
  try {
    const status = await api.getMockStatus()
    mockActive.value = status.mock_active
  } catch { /* ignore */ }
  await fetchEfficiencyTrend(7)
  await handleRunAnalysis()
})
</script>

<template>
  <div class="page-efficiency" v-loading="loading">
    <!-- Top toolbar -->
    <div class="toolbar">
      <el-button type="primary" @click="handleRunAnalysis" :loading="loading">刷新分析</el-button>
      <el-switch
        v-model="mockActive"
        active-text="Mock数据"
        inactive-text="Real数据"
        inline-prompt
        style="--el-switch-on-color: #e6a23c; margin-left: 12px;"
        @change="handleMockToggle"
      />
      <span v-if="analysisStore.efficiency" class="update-time">
        更新: {{ analysisStore.efficiency.analysis_time?.slice(11, 19) }}
      </span>
    </div>

    <!-- SCADA Configuration Diagram -->
    <div class="scada-container" v-if="analysisStore.efficiency">
      <div class="scada-layout">

        <!-- Row 1: 压气机 → 燃烧室 → 透平 → 发电机 (schematic) -->
        <div class="schematic-row">
          <div class="component-block compressor-block">
            <div class="component-box">
              <div class="comp-label">压气机</div>
              <div class="comp-sub">Compressor</div>
              <svg viewBox="0 0 40 30" class="comp-icon"><polygon points="5,25 20,5 35,25" fill="none" stroke="#409eff" stroke-width="2"/><line x1="20" y1="10" x2="20" y2="20" stroke="#409eff" stroke-width="1.5"/><polyline points="15,15 20,10 25,15" fill="none" stroke="#409eff" stroke-width="1.5"/></svg>
            </div>
            <div class="indicator-panel">
              <div class="ind-header" :style="{borderColor: '#409eff'}">
                <span class="ind-name">压气机效率</span>
                <span class="ind-deviation" :style="{color: deviationColor(getIndicatorValue('压气机效率'))}">{{ deviationText(getIndicatorValue('压气机效率')) }}</span>
              </div>
              <div class="ind-value-row">
                <span class="ind-value" :style="{color: '#409eff'}">{{ fmtValue('压气机效率') }}</span>
                <span class="ind-unit">{{ indUnit('压气机效率') }}</span>
              </div>
              <div class="ind-design">设计值: {{ fmtDesign('压气机效率') }}</div>
              <div class="scada-grid">
                <div v-for="f in indicatorGroups['压气机效率'].scadaFields" :key="f.key" class="scada-item">
                  <span class="scada-label">{{ f.label }}</span>
                  <span class="scada-val">{{ getScadaValue(f.key) }} <small>{{ f.unit }}</small></span>
                </div>
              </div>
            </div>
          </div>

          <div class="arrow-col"><span class="arrow-text">压缩空气 →</span></div>

          <div class="component-block combustion-block">
            <div class="component-box combustion">
              <div class="comp-label">燃烧室</div>
              <div class="comp-sub">Combustion Chamber</div>
              <svg viewBox="0 0 40 30" class="comp-icon"><rect x="5" y="5" width="30" height="20" rx="3" fill="none" stroke="#e6a23c" stroke-width="2"/><circle cx="20" cy="15" r="5" fill="none" stroke="#f56c6c" stroke-width="1.5"/><circle cx="20" cy="15" r="2" fill="#f56c6c" opacity="0.6"/></svg>
            </div>
            <div class="indicator-panel">
              <div class="ind-header" :style="{borderColor: '#e6a23c'}">
                <span class="ind-name">燃烧效率</span>
                <span class="ind-deviation" :style="{color: deviationColor(getIndicatorValue('燃烧效率'))}">{{ deviationText(getIndicatorValue('燃烧效率')) }}</span>
              </div>
              <div class="ind-value-row">
                <span class="ind-value" :style="{color: '#e6a23c'}">{{ fmtValue('燃烧效率') }}</span>
                <span class="ind-unit">{{ indUnit('燃烧效率') }}</span>
              </div>
              <div class="ind-design">设计值: {{ fmtDesign('燃烧效率') }}</div>
              <div class="scada-grid">
                <div v-for="f in indicatorGroups['燃烧效率'].scadaFields" :key="f.key" class="scada-item">
                  <span class="scada-label">{{ f.label }}</span>
                  <span class="scada-val">{{ getScadaValue(f.key) }} <small>{{ f.unit }}</small></span>
                </div>
              </div>
            </div>
          </div>

          <div class="arrow-col"><span class="arrow-text">高温燃气 →</span></div>

          <div class="component-block turbine-block">
            <div class="component-box turbine">
              <div class="comp-label">透平</div>
              <div class="comp-sub">Turbine</div>
              <svg viewBox="0 0 40 30" class="comp-icon"><polygon points="5,5 35,15 5,25" fill="none" stroke="#f56c6c" stroke-width="2"/><line x1="12" y1="10" x2="12" y2="20" stroke="#f56c6c" stroke-width="1.5"/><polyline points="8,13 12,10 16,13" fill="none" stroke="#f56c6c" stroke-width="1.5"/></svg>
            </div>
            <div class="indicator-panel">
              <div class="ind-header" :style="{borderColor: '#f56c6c'}">
                <span class="ind-name">透平效率</span>
                <span class="ind-deviation" :style="{color: deviationColor(getIndicatorValue('透平效率'))}">{{ deviationText(getIndicatorValue('透平效率')) }}</span>
              </div>
              <div class="ind-value-row">
                <span class="ind-value" :style="{color: '#f56c6c'}">{{ fmtValue('透平效率') }}</span>
                <span class="ind-unit">{{ indUnit('透平效率') }}</span>
              </div>
              <div class="ind-design">设计值: {{ fmtDesign('透平效率') }}</div>
              <div class="scada-grid">
                <div v-for="f in indicatorGroups['透平效率'].scadaFields" :key="f.key" class="scada-item">
                  <span class="scada-label">{{ f.label }}</span>
                  <span class="scada-val">{{ getScadaValue(f.key) }} <small>{{ f.unit }}</small></span>
                </div>
              </div>
            </div>
          </div>

          <div class="arrow-col"><span class="arrow-text">机械功 →</span></div>

          <div class="component-block generator-block">
            <div class="component-box generator">
              <div class="comp-label">发电机</div>
              <div class="comp-sub">Generator</div>
              <svg viewBox="0 0 40 30" class="comp-icon"><circle cx="20" cy="15" r="12" fill="none" stroke="#67c23a" stroke-width="2"/><text x="20" y="19" text-anchor="middle" fill="#67c23a" font-size="12" font-weight="bold">G</text></svg>
            </div>
            <div class="indicator-panel">
              <div class="ind-header" :style="{borderColor: '#67c23a'}">
                <span class="ind-name">发电气耗</span>
                <span class="ind-deviation" :style="{color: deviationColor(getIndicatorValue('发电气耗'))}">{{ deviationText(getIndicatorValue('发电气耗')) }}</span>
              </div>
              <div class="ind-value-row">
                <span class="ind-value" :style="{color: '#67c23a'}">{{ fmtValue('发电气耗', 4) }}</span>
                <span class="ind-unit">{{ indUnit('发电气耗') }}</span>
              </div>
              <div class="ind-design">设计值: {{ fmtDesign('发电气耗', 4) }}</div>
              <div class="scada-grid">
                <div v-for="f in indicatorGroups['发电气耗'].scadaFields" :key="f.key" class="scada-item">
                  <span class="scada-label">{{ f.label }}</span>
                  <span class="scada-val">{{ getScadaValue(f.key) }} <small>{{ f.unit }}</small></span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 2: Overall indicators (热耗率, 发电效率, 联合循环效率) -->
        <div class="overall-row">
          <div class="overall-card heat-rate-card">
            <div class="ind-header" :style="{borderColor: '#909399'}">
              <span class="ind-name">燃机热耗率</span>
              <span class="ind-deviation" :style="{color: deviationColor(getIndicatorValue('热耗率'))}">{{ deviationText(getIndicatorValue('热耗率')) }}</span>
            </div>
            <div class="ind-value-row">
              <span class="ind-value large" :style="{color: deviationColor(getIndicatorValue('热耗率'))}">{{ fmtValue('热耗率', 0) }}</span>
              <span class="ind-unit">{{ indUnit('热耗率') }}</span>
            </div>
            <div class="ind-design">设计值: {{ fmtDesign('热耗率', 0) }} | 历史最优: {{ fmtBest('热耗率', 0) }}</div>
            <div class="scada-grid compact">
              <div v-for="f in indicatorGroups['热耗率'].scadaFields" :key="f.key" class="scada-item">
                <span class="scada-label">{{ f.label }}</span>
                <span class="scada-val">{{ getScadaValue(f.key) }} <small>{{ f.unit }}</small></span>
              </div>
            </div>
          </div>

          <div class="overall-card gen-eff-card">
            <div class="ind-header" :style="{borderColor: '#409eff'}">
              <span class="ind-name">发电效率</span>
              <span class="ind-deviation" :style="{color: deviationColor(getIndicatorValue('发电效率'))}">{{ deviationText(getIndicatorValue('发电效率')) }}</span>
            </div>
            <div class="ind-value-row">
              <span class="ind-value large" :style="{color: '#409eff'}">{{ fmtValue('发电效率') }}</span>
              <span class="ind-unit">{{ indUnit('发电效率') }}</span>
            </div>
            <div class="ind-design">设计值: {{ fmtDesign('发电效率') }} | 公式: 3600 ÷ 热耗率 × 100%</div>
          </div>

          <div class="overall-card cc-eff-card">
            <div class="ind-header" :style="{borderColor: '#6f42c1'}">
              <span class="ind-name">联合循环效率</span>
              <span class="ind-deviation" :style="{color: deviationColor(getIndicatorValue('联合循环效率'))}">{{ deviationText(getIndicatorValue('联合循环效率')) }}</span>
            </div>
            <div class="ind-value-row">
              <span class="ind-value large" :style="{color: '#6f42c1'}">{{ fmtValue('联合循环效率') }}</span>
              <span class="ind-unit">{{ indUnit('联合循环效率') }}</span>
            </div>
            <div class="ind-design">设计值: {{ fmtDesign('联合循环效率') }} | 历史: {{ fmtBest('联合循环效率') }}</div>
            <div class="scada-grid compact">
              <div v-for="f in indicatorGroups['联合循环效率'].scadaFields" :key="f.key" class="scada-item">
                <span class="scada-label">{{ f.label }}</span>
                <span class="scada-val">{{ getScadaValue(f.key) }} <small>{{ f.unit }}</small></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-else-if="!loading" description="请点击'刷新分析'获取数据" />

    <!-- Trend chart -->
    <el-card shadow="never" class="trend-card">
      <template #header>
        <span style="font-weight: 600">热耗率趋势（近7天）</span>
      </template>
      <VChart v-if="realtimeStore.trend" :option="trendOption" style="height: 280px; width: 100%;" autoresize />
      <el-empty v-else description="暂无趋势数据" :image-size="60" />
    </el-card>

    <!-- Suggestions -->
    <el-card v-if="analysisStore.efficiency?.suggestions?.length" shadow="never" class="suggestions-card">
      <template #header><span style="font-weight: 600">优化建议</span></template>
      <ul class="suggestions-list">
        <li v-for="(s, idx) in analysisStore.efficiency.suggestions" :key="idx">{{ s }}</li>
      </ul>
    </el-card>
  </div>
</template>

<style scoped>
.page-efficiency {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.update-time {
  font-size: 12px;
  color: #909399;
}

/* === SCADA Configuration Diagram === */
.scada-container {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #dcdfe6;
}

.scada-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Row 1: 4 component blocks with arrows */
.schematic-row {
  display: flex;
  align-items: flex-start;
  gap: 0;
}

.component-block {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 0;
}

.component-box {
  width: 100%;
  padding: 12px 8px;
  border-radius: 8px;
  text-align: center;
  background: #fff;
  border: 2px solid #dcdfe6;
  margin-bottom: 8px;
}

.component-box.combustion { border-color: #e6a23c; background: #fffdf5; }
.component-box.turbine { border-color: #f56c6c; background: #fef5f5; }
.component-box.generator { border-color: #67c23a; background: #f5fbf0; }

.comp-label {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}

.comp-sub {
  font-size: 10px;
  color: #c0c4cc;
  margin-bottom: 4px;
}

.comp-icon {
  width: 36px;
  height: 28px;
  margin: 0 auto;
  display: block;
}

.arrow-col {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30px 4px 0 4px;
  min-width: 60px;
}

.arrow-text {
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
}

/* Indicator panel under each component */
.indicator-panel {
  width: 100%;
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  border: 1px solid #ebeef5;
}

.ind-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 6px;
  border-bottom: 2px solid #dcdfe6;
  margin-bottom: 6px;
}

.ind-name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.ind-deviation {
  font-size: 12px;
  font-weight: 600;
}

.ind-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.ind-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}

.ind-value.large {
  font-size: 28px;
}

.ind-unit {
  font-size: 11px;
  color: #909399;
}

.ind-design {
  font-size: 11px;
  color: #909399;
  margin-bottom: 6px;
}

/* SCADA raw values grid */
.scada-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3px 12px;
}

.scada-grid.compact {
  grid-template-columns: 1fr 1fr 1fr;
}

.scada-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 0;
  border-bottom: 1px dashed #f0f0f0;
}

.scada-label {
  font-size: 11px;
  color: #909399;
  flex-shrink: 0;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scada-val {
  font-size: 12px;
  color: #303133;
  font-weight: 600;
  text-align: right;
}

.scada-val small {
  font-size: 10px;
  color: #c0c4cc;
  font-weight: 400;
  margin-left: 2px;
}

/* Row 2: Overall indicators */
.overall-row {
  display: flex;
  gap: 12px;
}

.overall-card {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #ebeef5;
}

.trend-card, .suggestions-card {
  border-radius: 8px;
}

.suggestions-list {
  padding-left: 20px;
  margin: 0;
  line-height: 2;
  font-size: 13px;
  color: #606266;
}
</style>
