<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import * as api from '../api'
import type { ParameterDefinition, BaselineConfig, BenchmarkIndicator } from '../types'
import { ElMessage } from 'element-plus'

const activeTab = ref('parameters')
const loading = ref(false)

const parameters = ref<ParameterDefinition[]>([])
const paramTotal = ref(0)
const baselines = ref<BaselineConfig[]>([])
const baselineTotal = ref(0)
const benchmarkIndicators = ref<BenchmarkIndicator[]>([])
const benchmarkTotal = ref(0)

// --- Parameter add form ---
const showParamDialog = ref(false)
const paramForm = reactive({
  id: '', name: '', unit: '', location: '', normal_range_min: 0, normal_range_max: 100, source: '', update_freq: '1s',
})

// --- Baseline add form ---
const showBaselineDialog = ref(false)
const baselineForm = reactive({
  parameter_id: '', parameter_name: '', model_type: '多元回归', features_text: '', accuracy: 0.95,
})

// --- Benchmark add form ---
const showBenchmarkDialog = ref(false)
const benchmarkForm = reactive({
  name: '', unit: '', source: '对标分析模型', peer_avg: 0,
})

async function loadParameters() {
  loading.value = true
  try { const res = await api.getParameters(); parameters.value = res.parameters; paramTotal.value = res.total }
  catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : String(e)) }
  finally { loading.value = false }
}
async function loadBaselines() {
  loading.value = true
  try { const res = await api.getBaselines(); baselines.value = res.baselines; baselineTotal.value = res.total }
  catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : String(e)) }
  finally { loading.value = false }
}
async function loadBenchmarkIndicators() {
  loading.value = true
  try { const res = await api.getBenchmarkIndicators(); benchmarkIndicators.value = res.indicators; benchmarkTotal.value = res.total }
  catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : String(e)) }
  finally { loading.value = false }
}

async function handleTabChange(tab: string) {
  if (tab === 'parameters' && parameters.value.length === 0) await loadParameters()
  else if (tab === 'baselines' && baselines.value.length === 0) await loadBaselines()
  else if (tab === 'benchmark' && benchmarkIndicators.value.length === 0) await loadBenchmarkIndicators()
}

function formatRange(range: [number, number]): string { return `${range[0]} ~ ${range[1]}` }

function handleAddParameter() {
  const newParam: ParameterDefinition = {
    id: paramForm.id || `P${String(parameters.value.length + 1).padStart(3, '0')}`,
    name: paramForm.name,
    unit: paramForm.unit,
    location: paramForm.location,
    normal_range: [paramForm.normal_range_min, paramForm.normal_range_max],
    source: paramForm.source,
    update_freq: paramForm.update_freq,
  }
  parameters.value.push(newParam)
  paramTotal.value = parameters.value.length
  showParamDialog.value = false
  Object.assign(paramForm, { id: '', name: '', unit: '', location: '', normal_range_min: 0, normal_range_max: 100, source: '', update_freq: '1s' })
  ElMessage.success('监测参数已添加')
}

function handleAddBaseline() {
  const newBaseline: BaselineConfig = {
    parameter_id: baselineForm.parameter_id,
    parameter_name: baselineForm.parameter_name,
    model_type: baselineForm.model_type,
    features: baselineForm.features_text.split(',').map(s => s.trim()).filter(Boolean),
    accuracy: baselineForm.accuracy,
  }
  baselines.value.push(newBaseline)
  baselineTotal.value = baselines.value.length
  showBaselineDialog.value = false
  Object.assign(baselineForm, { parameter_id: '', parameter_name: '', model_type: '多元回归', features_text: '', accuracy: 0.95 })
  ElMessage.success('基准值模型已添加')
}

function handleAddBenchmark() {
  const newIndicator: BenchmarkIndicator = {
    id: `B${String(benchmarkIndicators.value.length + 1).padStart(3, '0')}`,
    name: benchmarkForm.name,
    unit: benchmarkForm.unit,
    source: benchmarkForm.source,
    peer_avg: benchmarkForm.peer_avg,
  }
  benchmarkIndicators.value.push(newIndicator)
  benchmarkTotal.value = benchmarkIndicators.value.length
  showBenchmarkDialog.value = false
  Object.assign(benchmarkForm, { name: '', unit: '', source: '对标分析模型', peer_avg: 0 })
  ElMessage.success('对标指标已添加')
}

onMounted(async () => { await loadParameters() })
</script>

<template>
  <div class="page-dictionary">
    <el-card shadow="never" class="dict-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- Tab 1: Parameters -->
        <el-tab-pane label="监测参数" name="parameters">
          <div class="tab-header">
            <span class="total-label">共 {{ paramTotal }} 条参数</span>
            <div>
              <el-button type="primary" size="small" @click="showParamDialog = true">添加参数</el-button>
              <el-button size="small" @click="loadParameters">刷新</el-button>
            </div>
          </div>
          <el-table v-loading="loading" :data="parameters" stripe size="small">
            <el-table-column prop="id" label="参数ID" width="120" />
            <el-table-column prop="name" label="参数名称" min-width="140" />
            <el-table-column prop="unit" label="单位" width="80" align="center" />
            <el-table-column prop="location" label="位置" width="120" />
            <el-table-column label="正常范围" width="130" align="center">
              <template #default="{ row }">{{ formatRange(row.normal_range) }}</template>
            </el-table-column>
            <el-table-column prop="source" label="来源" width="120" />
            <el-table-column prop="update_freq" label="更新频率" width="90" />
          </el-table>
        </el-tab-pane>

        <!-- Tab 2: Baselines -->
        <el-tab-pane label="基准值模型" name="baselines">
          <div class="tab-header">
            <span class="total-label">共 {{ baselineTotal }} 条基准配置</span>
            <div>
              <el-button type="primary" size="small" @click="showBaselineDialog = true">添加模型</el-button>
              <el-button size="small" @click="loadBaselines">刷新</el-button>
            </div>
          </div>
          <el-table v-loading="loading" :data="baselines" stripe size="small">
            <el-table-column prop="parameter_id" label="参数ID" width="120" />
            <el-table-column prop="parameter_name" label="参数名称" min-width="140" />
            <el-table-column prop="model_type" label="模型类型" width="120" />
            <el-table-column label="特征列表" min-width="200">
              <template #default="{ row }">
                <el-tag v-for="f in (row.features as string[]).slice(0, 4)" :key="f" size="small" type="info" style="margin:0 2px 2px 0;">{{ f }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="精度" width="90" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.accuracy >= 0.9 ? '#67c23a' : '#e6a23c' }">{{ (row.accuracy * 100).toFixed(1) }}%</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab 3: Benchmark Indicators -->
        <el-tab-pane label="对标指标" name="benchmark">
          <div class="tab-header">
            <span class="total-label">共 {{ benchmarkTotal }} 条指标</span>
            <div>
              <el-button type="primary" size="small" @click="showBenchmarkDialog = true">添加指标</el-button>
              <el-button size="small" @click="loadBenchmarkIndicators">刷新</el-button>
            </div>
          </div>
          <el-table v-loading="loading" :data="benchmarkIndicators" stripe size="small">
            <el-table-column prop="id" label="指标ID" width="120" />
            <el-table-column prop="name" label="指标名称" min-width="140" />
            <el-table-column prop="unit" label="单位" width="80" align="center" />
            <el-table-column prop="source" label="来源" width="120" />
            <el-table-column label="同类均值" width="110" align="center">
              <template #default="{ row }">{{ row.peer_avg.toFixed(2) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Add Parameter Dialog -->
    <el-dialog v-model="showParamDialog" title="添加监测参数" width="520px">
      <el-form :model="paramForm" label-width="90px" size="default">
        <el-form-item label="参数ID"><el-input v-model="paramForm.id" placeholder="如 P011，留空自动生成" /></el-form-item>
        <el-form-item label="参数名称"><el-input v-model="paramForm.name" placeholder="如 排气温度" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="paramForm.unit" placeholder="如 °C" /></el-form-item>
        <el-form-item label="位置"><el-input v-model="paramForm.location" placeholder="如 透平出口" /></el-form-item>
        <el-form-item label="正常下限"><el-input-number v-model="paramForm.normal_range_min" :step="1" /></el-form-item>
        <el-form-item label="正常上限"><el-input-number v-model="paramForm.normal_range_max" :step="1" /></el-form-item>
        <el-form-item label="数据来源"><el-input v-model="paramForm.source" placeholder="如 时序数据库" /></el-form-item>
        <el-form-item label="更新频率"><el-input v-model="paramForm.update_freq" placeholder="如 1s" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showParamDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddParameter">确定</el-button>
      </template>
    </el-dialog>

    <!-- Add Baseline Dialog -->
    <el-dialog v-model="showBaselineDialog" title="添加基准值模型" width="520px">
      <el-form :model="baselineForm" label-width="90px" size="default">
        <el-form-item label="参数ID"><el-input v-model="baselineForm.parameter_id" placeholder="如 P001" /></el-form-item>
        <el-form-item label="参数名称"><el-input v-model="baselineForm.parameter_name" placeholder="如 排气温度" /></el-form-item>
        <el-form-item label="模型类型">
          <el-select v-model="baselineForm.model_type">
            <el-option label="多元回归" value="多元回归" />
            <el-option label="设计值插值" value="设计值插值" />
            <el-option label="热力模型" value="热力模型" />
            <el-option label="神经网络" value="神经网络" />
          </el-select>
        </el-form-item>
        <el-form-item label="特征列表"><el-input v-model="baselineForm.features_text" placeholder="逗号分隔，如 负荷率,环境温度" /></el-form-item>
        <el-form-item label="精度"><el-input-number v-model="baselineForm.accuracy" :min="0" :max="1" :step="0.01" :precision="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBaselineDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddBaseline">确定</el-button>
      </template>
    </el-dialog>

    <!-- Add Benchmark Dialog -->
    <el-dialog v-model="showBenchmarkDialog" title="添加对标指标" width="480px">
      <el-form :model="benchmarkForm" label-width="90px" size="default">
        <el-form-item label="指标名称"><el-input v-model="benchmarkForm.name" placeholder="如 供电煤耗" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="benchmarkForm.unit" placeholder="如 g/kWh" /></el-form-item>
        <el-form-item label="数据来源"><el-input v-model="benchmarkForm.source" placeholder="如 对标分析模型" /></el-form-item>
        <el-form-item label="同类均值"><el-input-number v-model="benchmarkForm.peer_avg" :step="1" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBenchmarkDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddBenchmark">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-dictionary { padding-bottom: 24px; }
.dict-card { border-radius: 8px; }
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.total-label { font-size: 13px; color: #909399; }
</style>
