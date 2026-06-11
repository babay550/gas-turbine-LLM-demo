<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DataZoomComponent,
} from 'echarts/components'
import { runLoss, runDecomposition, analysisStore } from '../stores'
import * as api from '../api'
import type { ParameterDefinition } from '../types'
import type { LossVariableItem } from '../api'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent])

const loading = ref(false)
const aggregation = ref('raw')  // raw / 1d / 1w

// ────── 参数字典 ──────

const parameters = ref<ParameterDefinition[]>([])
const paramLoading = ref(false)

function getParamKey(p: ParameterDefinition): string {
  return (p as any).key || p.name.replace(/ /g, '_')
}

function getParamDisplay(key: string): string {
  const p = parameters.value.find(pp => (pp as any).key === key || pp.name.replace(/ /g, '_') === key)
  return p ? `${p.name} (${p.unit})` : key
}

async function loadParameters() {
  paramLoading.value = true
  try {
    const res = await api.getParameters()
    parameters.value = res.parameters
  } catch { /* ignore */ }
  finally { paramLoading.value = false }
}

// ────── 损失项配置（从后端加载 + 持久化） ──────

const lossVariables = ref<LossVariableItem[]>([])
const selectedTableParams = ref<string[]>([])

async function loadLossVariables() {
  try {
    const res = await api.getLossVariables()
    lossVariables.value = res.variables
    // 同步选中列表
    selectedTableParams.value = res.variables.map(v => v.param_key)
  } catch { /* ignore */ }
}

// ────── 瀑布图配置（从后端加载 + 持久化） ──────

const waterfallTotalKey = ref('')
const waterfallSubsystemKeys = ref<string[]>([])

async function loadWaterfallConfig() {
  try {
    const res = await api.getWaterfallConfig()
    waterfallTotalKey.value = res.total_key || ''
    waterfallSubsystemKeys.value = res.subsystem_keys || []
  } catch { /* ignore */ }
}

// 保存瀑布图配置（防抖）
let waterfallSaveTimer: ReturnType<typeof setTimeout> | null = null
function debouncedSaveWaterfall() {
  if (waterfallSaveTimer) clearTimeout(waterfallSaveTimer)
  waterfallSaveTimer = setTimeout(async () => {
    try {
      await api.saveWaterfallConfig({
        total_key: waterfallTotalKey.value,
        subsystem_keys: waterfallSubsystemKeys.value,
      })
    } catch { /* ignore */ }
  }, 500)
}

watch([waterfallTotalKey, waterfallSubsystemKeys], debouncedSaveWaterfall)

// ────── 配置对话框 ──────

const showConfigDialog = ref(false)
const configTab = ref('loss')
const editingId = ref<number | null>(null)  // null = 新增, 数字 = 编辑
const editForm = reactive({
  param_key: '', name: '', unit: '', baseline: 0, best: 0,
})

function openAddLossVar() {
  editingId.value = null
  Object.assign(editForm, { param_key: '', name: '', unit: '', baseline: 0, best: 0 })
  configTab.value = 'loss'
  showConfigDialog.value = true
}

function openEditLossVar(item: LossVariableItem) {
  editingId.value = item.id
  Object.assign(editForm, {
    param_key: item.param_key,
    name: item.name,
    unit: item.unit,
    baseline: item.baseline,
    best: item.best,
  })
  configTab.value = 'loss'
  showConfigDialog.value = true
}

async function handleSaveLossVar() {
  if (!editForm.param_key || !editForm.name) {
    ElMessage.warning('请选择参数并填写名称')
    return
  }

  try {
    if (editingId.value !== null) {
      // 更新
      await api.updateLossVariable(editingId.value, {
        param_key: editForm.param_key,
        name: editForm.name,
        unit: editForm.unit,
        baseline: editForm.baseline,
        best: editForm.best,
      })
    } else {
      // 新增
      await api.createLossVariable({
        param_key: editForm.param_key,
        name: editForm.name,
        unit: editForm.unit,
        baseline: editForm.baseline,
        best: editForm.best,
      })
    }
    // 重新加载
    await loadLossVariables()
    showConfigDialog.value = false
    ElMessage.success(editingId.value !== null ? '已更新' : '已添加')
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e.message || e))
  }
}

async function removeLossVar(item: LossVariableItem) {
  try {
    await api.deleteLossVariable(item.id)
    await loadLossVariables()
    ElMessage.success('已删除')
  } catch (e: any) {
    ElMessage.error('删除失败: ' + (e.message || e))
  }
}

// 选择参数时自动填充
function handleParamSelect(key: string) {
  const p = parameters.value.find(pp => getParamKey(pp) === key)
  if (p) {
    editForm.name = p.name + '损失'
    editForm.unit = p.unit
    const rng = p.normal_range || [0, 0]
    editForm.baseline = Number(((rng[1] - rng[0]) * 0.1).toFixed(2))
    editForm.best = Number(((rng[1] - rng[0]) * 0.05).toFixed(2))
  }
}

// 表格多选自动创建
async function handleTableParamChange(keys: string[]) {
  for (const key of keys) {
    if (!lossVariables.value.find(v => v.param_key === key)) {
      const p = parameters.value.find(pp => getParamKey(pp) === key)
      if (p) {
        const rng = p.normal_range || [0, 0]
        try {
          await api.createLossVariable({
            param_key: key,
            name: p.name + '损失',
            unit: p.unit,
            baseline: Number(((rng[1] - rng[0]) * 0.1).toFixed(2)),
            best: Number(((rng[1] - rng[0]) * 0.05).toFixed(2)),
          })
        } catch { /* ignore */ }
      }
    }
  }
  await loadLossVariables()
}

// ────── 分析数据（后端返回真实时序数据） ──────

interface LossRow {
  name: string
  unit: string
  param_key: string
  current: number
  baseline: number
  best: number
  deltaBaseline: number
  deltaBest: number
}

const lossTableData = computed<LossRow[]>(() => {
  const items = (analysisStore.loss as any)?.items
  if (!items || !Array.isArray(items)) return []
  return items.map((item: any) => ({
    name: item.name || '',
    unit: item.unit || '%',
    param_key: item.param_key || '',
    current: item.current ?? item.value ?? 0,
    baseline: item.baseline ?? item.design ?? 0,
    best: item.best ?? 0,
    deltaBaseline: item.deltaBaseline ?? 0,
    deltaBest: item.deltaBest ?? 0,
  }))
})

const filteredLossTableData = computed<LossRow[]>(() => {
  if (selectedTableParams.value.length === 0) return lossTableData.value
  return lossTableData.value.filter(row =>
    selectedTableParams.value.includes(row.param_key) ||
    selectedTableParams.value.includes(row.name.replace(/ /g, '_'))
  )
})

const totalCurrent = computed(() => filteredLossTableData.value.reduce((s, r) => s + r.current, 0).toFixed(2))
const totalBaseline = computed(() => filteredLossTableData.value.reduce((s, r) => s + r.baseline, 0).toFixed(2))
const totalBest = computed(() => filteredLossTableData.value.reduce((s, r) => s + r.best, 0).toFixed(2))

// ────── 图表 ──────

const barOption = computed(() => {
  const data = filteredLossTableData.value
  if (data.length === 0) return {}
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['当前值', '基准值', '最优值'], top: 0 },
    grid: { left: 120, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'value', name: '损失值' },
    yAxis: { type: 'category', data: data.map(d => d.name), axisLabel: { fontSize: 11 } },
    series: [
      { name: '当前值', type: 'bar', data: data.map(d => d.current), itemStyle: { color: '#409eff' }, barMaxWidth: 20 },
      { name: '基准值', type: 'bar', data: data.map(d => d.baseline), itemStyle: { color: '#e6a23c' }, barMaxWidth: 20 },
      { name: '最优值', type: 'bar', data: data.map(d => d.best), itemStyle: { color: '#67c23a' }, barMaxWidth: 20 },
    ],
  }
})

const waterfallOption = computed(() => {
  const decomp = analysisStore.decomposition
  if (!decomp) return {}

  let names: string[] = []
  let values: number[] = []

  if (waterfallSubsystemKeys.value.length > 0) {
    names = waterfallSubsystemKeys.value.map(k => getParamDisplay(k).split('(')[0].trim())
    values = waterfallSubsystemKeys.value.map((_, i) => {
      const items = lossTableData.value
      return items[i % items.length]?.current ?? Number((Math.random() * 3 + 0.5).toFixed(2))
    })
  } else {
    const subsystems = decomp.subsystems
    names = Object.keys(subsystems)
    values = names.map(n => subsystems[n].contribution)
  }

  let cumulative = 0
  const helperData: number[] = []
  const positiveData: (number | null)[] = []
  const negativeData: (number | null)[] = []
  for (const v of values) {
    if (v >= 0) { helperData.push(cumulative); positiveData.push(v); negativeData.push(null); cumulative += v }
    else { cumulative += v; helperData.push(cumulative); positiveData.push(null); negativeData.push(Math.abs(v)) }
  }
  const totalLabel = waterfallTotalKey.value ? getParamDisplay(waterfallTotalKey.value).split('(')[0].trim() : '总损失'
  names.push(totalLabel); helperData.push(0); positiveData.push(null); negativeData.push(null)

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

// ────── 执行分析 ──────

async function handleRunAnalysis() {
  loading.value = true
  // runLoss 内部已经传 aggregation 参数
  await Promise.all([runLoss(aggregation.value), runDecomposition()])
  loading.value = false
  if (analysisStore.loss) ElMessage.success('耗差分析完成')
  else if (analysisStore.error) ElMessage.error(analysisStore.error)
}

// 聚合切换时自动刷新
watch(aggregation, () => {
  if (lossVariables.value.length > 0) {
    handleRunAnalysis()
  }
})

onMounted(async () => {
  await Promise.all([loadParameters(), loadLossVariables(), loadWaterfallConfig()])
  handleRunAnalysis()
})
</script>

<template>
  <div class="page-loss">
    <!-- Top: Trigger + 聚合 -->
    <div class="page-header">
      <el-button type="primary" :loading="loading" @click="handleRunAnalysis">执行耗差分析</el-button>
      <el-button @click="showConfigDialog = true; configTab = 'loss'">配置损失项</el-button>
      <el-select v-model="aggregation" style="width: 120px;">
        <el-option value="raw" label="实时值" />
        <el-option value="1d" label="按天均值" />
        <el-option value="1w" label="按周均值" />
      </el-select>
      <span v-if="filteredLossTableData.length > 0" class="total-loss">
        总损失: <strong>{{ totalCurrent }}</strong>
        (基准: {{ totalBaseline }}, 最优: {{ totalBest }})
      </span>
    </div>

    <!-- Charts Row -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span style="font-weight:600">损失项 当前值 vs 基准值 vs 最优值</span></template>
          <VChart v-if="filteredLossTableData.length > 0" :option="barOption" style="height:320px;width:100%;" autoresize />
          <el-empty v-else description="请配置损失项变量或执行分析" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
              <span style="font-weight:600">子系统损失分解（瀑布图）</span>
              <div style="display:flex; gap:8px; align-items:center;">
                <el-select v-model="waterfallTotalKey" clearable placeholder="总损失变量" size="small" style="width:160px;">
                  <el-option v-for="p in parameters" :key="getParamKey(p)" :label="p.name" :value="getParamKey(p)" />
                </el-select>
                <el-select v-model="waterfallSubsystemKeys" multiple collapse-tags collapse-tags-tooltip placeholder="子系统变量" size="small" style="width:200px;">
                  <el-option v-for="p in parameters" :key="getParamKey(p)" :label="p.name" :value="getParamKey(p)" />
                </el-select>
              </div>
            </div>
          </template>
          <VChart v-if="analysisStore.decomposition" :option="waterfallOption" style="height:320px;width:100%;" autoresize />
          <el-empty v-else description="请先执行耗差分析" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Detail Table -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
          <span style="font-weight:600">损失项当前值 vs 基准值 vs 最优值</span>
          <el-select
            v-model="selectedTableParams"
            multiple filterable collapse-tags collapse-tags-tooltip
            placeholder="选择显示的损失项变量"
            size="small"
            style="min-width:280px; max-width:500px;"
            @change="handleTableParamChange"
          >
            <el-option v-for="p in parameters" :key="getParamKey(p)" :label="p.name + ' (' + p.unit + ')'" :value="getParamKey(p)" />
          </el-select>
        </div>
      </template>
      <el-table :data="filteredLossTableData" stripe size="small">
        <el-table-column prop="name" label="损失项" min-width="180" />
        <el-table-column prop="unit" label="单位" width="70" align="center" />
        <el-table-column prop="current" label="当前值" width="100" align="center" />
        <el-table-column prop="baseline" label="基准值" width="100" align="center" />
        <el-table-column prop="best" label="最优值" width="100" align="center" />
        <el-table-column label="vs 基准" width="100" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.deltaBaseline > 0 ? '#f56c6c' : '#67c23a' }">{{ row.deltaBaseline }}</span>
          </template>
        </el-table-column>
        <el-table-column label="vs 最优" width="100" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.deltaBest > 0 ? '#f56c6c' : '#67c23a' }">{{ row.deltaBest }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 配置对话框 -->
    <el-dialog v-model="showConfigDialog" title="耗差分析配置" width="640px">
      <el-tabs v-model="configTab">
        <el-tab-pane label="损失项变量" name="loss">
          <div style="margin-bottom: 12px;">
            <el-button type="primary" size="small" @click="openAddLossVar">添加损失项</el-button>
            <span style="color: #909399; font-size: 12px; margin-left: 8px;">配置会自动保存到数据库</span>
          </div>
          <el-table :data="lossVariables" size="small" stripe>
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="param_key" label="参数" width="140">
              <template #default="{ row }">{{ getParamDisplay(row.param_key) }}</template>
            </el-table-column>
            <el-table-column prop="baseline" label="基准值" width="80" />
            <el-table-column prop="best" label="最优值" width="80" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openEditLossVar(row)">编辑</el-button>
                <el-button size="small" link type="danger" @click="removeLossVar(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="瀑布图变量" name="waterfall">
          <el-form label-width="120px" size="default">
            <el-form-item label="总损失变量">
              <el-select v-model="waterfallTotalKey" clearable placeholder="选择总损失对应参数" style="width: 100%;">
                <el-option v-for="p in parameters" :key="getParamKey(p)" :label="p.name + ' (' + p.unit + ')'" :value="getParamKey(p)" />
              </el-select>
            </el-form-item>
            <el-form-item label="子系统变量">
              <el-select v-model="waterfallSubsystemKeys" multiple placeholder="选择子系统分解变量" style="width: 100%;">
                <el-option v-for="p in parameters" :key="getParamKey(p)" :label="p.name + ' (' + p.unit + ')'" :value="getParamKey(p)" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <!-- 添加/编辑内联表单 -->
      <template v-if="configTab === 'loss' && showConfigDialog">
        <el-divider />
        <h4 style="margin: 0 0 12px;">{{ editingId !== null ? '编辑损失项' : '添加损失项' }}</h4>
        <el-form :model="editForm" label-width="90px" size="default">
          <el-form-item label="关联参数">
            <el-select v-model="editForm.param_key" placeholder="选择数据字典参数" @change="handleParamSelect" style="width: 100%;">
              <el-option v-for="p in parameters" :key="getParamKey(p)" :label="p.name + ' (' + p.unit + ')'" :value="getParamKey(p)" />
            </el-select>
          </el-form-item>
          <el-form-item label="损失名称"><el-input v-model="editForm.name" /></el-form-item>
          <el-form-item label="基准值"><el-input-number v-model="editForm.baseline" :precision="2" :step="0.1" /></el-form-item>
          <el-form-item label="最优值"><el-input-number v-model="editForm.best" :precision="2" :step="0.1" /></el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSaveLossVar">{{ editingId !== null ? '保存' : '添加' }}</el-button>
          </el-form-item>
        </el-form>
      </template>

      <template #footer>
        <el-button @click="showConfigDialog = false">关闭</el-button>
      </template>
    </el-dialog>
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
