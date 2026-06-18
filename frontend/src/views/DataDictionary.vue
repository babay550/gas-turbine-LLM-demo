<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import * as api from '../api'
import type { ParameterDefinition, BaselineConfig, BenchmarkIndicator } from '../types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Download, Upload, Document } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'

const activeTab = ref('parameters')
const loading = ref(false)

const parameters = ref<ParameterDefinition[]>([])
const paramTotal = ref(0)
const baselines = ref<BaselineConfig[]>([])
const baselineTotal = ref(0)
const benchmarkIndicators = ref<BenchmarkIndicator[]>([])
const benchmarkTotal = ref(0)

// --- 搜索 ---
const paramSearch = ref('')
const filteredParameters = computed(() => {
  if (!paramSearch.value) return parameters.value
  const kw = paramSearch.value.toLowerCase()
  return parameters.value.filter(p =>
    p.name.toLowerCase().includes(kw) ||
    p.id.toLowerCase().includes(kw) ||
    ((p as any).subsystem || '').toLowerCase().includes(kw) ||
    ((p as any).key || '').toLowerCase().includes(kw)
  )
})

// --- Parameter add/edit form ---
const showParamDialog = ref(false)
const paramDialogMode = ref<'add' | 'edit'>('add')
const paramForm = reactive({
  id: '', name: '', unit: '', subsystem: '其他', location: '',
  normal_range_min: 0, normal_range_max: 100, source: '时序数据库', update_freq: '1s',
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

// --- Parameter import ---
const showImportDialog = ref(false)
const importLoading = ref(false)

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

// ──── CRUD: 调用后端 API ────

function openAddParamDialog() {
  paramDialogMode.value = 'add'
  Object.assign(paramForm, { id: '', name: '', unit: '', subsystem: '其他', location: '', normal_range_min: 0, normal_range_max: 100, source: '时序数据库', update_freq: '1s' })
  showParamDialog.value = true
}

function openEditParamDialog(param: ParameterDefinition) {
  paramDialogMode.value = 'edit'
  Object.assign(paramForm, {
    id: param.id,
    name: param.name,
    unit: param.unit,
    subsystem: (param as any).subsystem || '其他',
    location: param.location,
    normal_range_min: param.normal_range?.[0] ?? 0,
    normal_range_max: param.normal_range?.[1] ?? 100,
    source: param.source,
    update_freq: param.update_freq,
  })
  showParamDialog.value = true
}

async function handleSaveParameter() {
  if (!paramForm.name) { ElMessage.warning('请填写参数名称'); return }
  try {
    if (paramDialogMode.value === 'add') {
      await api.createParameter({
        name: paramForm.name, unit: paramForm.unit, subsystem: paramForm.subsystem,
        location: paramForm.location, normal_min: paramForm.normal_range_min,
        normal_max: paramForm.normal_range_max, source: paramForm.source, update_freq: paramForm.update_freq,
      })
      ElMessage.success('监测参数已添加')
    } else {
      await api.updateParameter(paramForm.id, {
        name: paramForm.name, unit: paramForm.unit, subsystem: paramForm.subsystem,
        location: paramForm.location, normal_min: paramForm.normal_range_min,
        normal_max: paramForm.normal_range_max, source: paramForm.source, update_freq: paramForm.update_freq,
      })
      ElMessage.success('参数已更新')
    }
    showParamDialog.value = false
    await loadParameters()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message || e))
  }
}

async function handleDeleteParameter(param: ParameterDefinition) {
  try {
    await ElMessageBox.confirm(`确定删除参数"${param.name}"？`, '确认删除', { type: 'warning' })
    await api.deleteParameter(param.id)
    await loadParameters()
    ElMessage.success('参数已删除')
  } catch { /* cancelled */ }
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

// ──── XLSX 模板导入/导出 ────

async function handleDownloadTemplate() {
  try {
    await api.downloadParameterTemplate()
    ElMessage.success('模板下载成功')
  } catch (e: unknown) {
    ElMessage.error('下载失败: ' + (e instanceof Error ? e.message : String(e)))
  }
}

async function handleExportParameters() {
  try {
    await api.exportParameters()
    ElMessage.success('导出成功')
  } catch (e: unknown) {
    ElMessage.error('导出失败: ' + (e instanceof Error ? e.message : String(e)))
  }
}

function handleImportBeforeUpload(file: UploadFile) {
  if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
    ElMessage.warning('请上传 .xlsx 文件')
    return false
  }
  return true
}

async function handleImportUpload(options: { file: File }) {
  importLoading.value = true
  try {
    const result = await api.importParameters(options.file)
    if (result.errors && result.errors.length > 0) {
      ElMessage.warning(`导入完成：新增 ${result.imported} 条，跳过 ${result.skipped} 条，${result.errors.length} 项有误`)
      for (const err of result.errors.slice(0, 5)) {
        console.warn('导入错误:', err)
      }
    } else {
      ElMessage.success(`导入成功：新增 ${result.imported} 条参数，跳过 ${result.skipped} 条已存在项`)
    }
    showImportDialog.value = false
    await loadParameters()
  } catch (e: any) {
    ElMessage.error('导入失败: ' + (e.response?.data?.detail || e.message || String(e)))
  } finally {
    importLoading.value = false
  }
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
            <el-input v-model="paramSearch" placeholder="搜索参数名/ID/子系统" clearable
                      style="width: 220px;" size="small" />
            <div>
              <el-button type="primary" size="small" @click="openAddParamDialog">添加参数</el-button>
              <el-button size="small" :icon="Download" @click="handleDownloadTemplate">下载模板</el-button>
              <el-button size="small" :icon="Upload" @click="showImportDialog = true">导入</el-button>
              <el-button size="small" :icon="Document" @click="handleExportParameters">导出</el-button>
              <el-button size="small" @click="loadParameters">刷新</el-button>
            </div>
          </div>
          <el-table v-loading="loading" :data="filteredParameters" stripe size="small">
            <el-table-column prop="id" label="参数ID" width="70" />
            <el-table-column prop="name" label="参数名称" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" align="center" />
            <el-table-column prop="subsystem" label="子系统" width="80" />
            <el-table-column prop="location" label="位置" width="100" />
            <el-table-column label="正常范围" width="120" align="center">
              <template #default="{ row }">{{ formatRange(row.normal_range) }}</template>
            </el-table-column>
            <el-table-column prop="source" label="来源" width="100" />
            <el-table-column prop="update_freq" label="频率" width="70" align="center" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openEditParamDialog(row)">编辑</el-button>
                <el-button size="small" link type="danger" @click="handleDeleteParameter(row)"
                           :disabled="row.id === 'P001'">删除</el-button>
              </template>
            </el-table-column>
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

    <!-- Add/Edit Parameter Dialog -->
    <el-dialog v-model="showParamDialog"
               :title="paramDialogMode === 'add' ? '添加监测参数' : '编辑参数'"
               width="520px">
      <el-form :model="paramForm" label-width="90px" size="default">
        <el-form-item label="参数名称"><el-input v-model="paramForm.name" placeholder="如 排气温度" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="paramForm.unit" placeholder="如 °C" /></el-form-item>
        <el-form-item label="子系统">
          <el-select v-model="paramForm.subsystem">
            <el-option label="全厂" value="全厂" />
            <el-option label="机组" value="机组" />
            <el-option label="燃机" value="燃机" />
            <el-option label="压气机" value="压气机" />
            <el-option label="燃烧室" value="燃烧室" />
            <el-option label="透平" value="透平" />
            <el-option label="发电机" value="发电机" />
            <el-option label="汽机" value="汽机" />
            <el-option label="余热锅炉" value="余热锅炉" />
            <el-option label="辅助" value="辅助" />
            <el-option label="环境" value="环境" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="位置"><el-input v-model="paramForm.location" placeholder="如 透平出口" /></el-form-item>
        <el-form-item label="正常下限"><el-input-number v-model="paramForm.normal_range_min" :step="1" /></el-form-item>
        <el-form-item label="正常上限"><el-input-number v-model="paramForm.normal_range_max" :step="1" /></el-form-item>
        <el-form-item label="数据来源"><el-input v-model="paramForm.source" placeholder="如 时序数据库" /></el-form-item>
        <el-form-item label="更新频率"><el-input v-model="paramForm.update_freq" placeholder="如 1s" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showParamDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveParameter">{{ paramDialogMode === 'add' ? '添加' : '保存' }}</el-button>
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

    <!-- Import Parameters Dialog -->
    <el-dialog v-model="showImportDialog" title="批量导入参数" width="480px">
      <div style="margin-bottom: 12px; color: #909399; font-size: 13px;">
        请先下载模板，按格式填写后上传。已存在的参数（按名称匹配）会自动跳过。
      </div>
      <el-upload
        drag
        :auto-upload="false"
        accept=".xlsx,.xls"
        :limit="1"
        :before-upload="handleImportBeforeUpload"
        :on-change="(f: UploadFile) => f.raw && handleImportUpload({ file: f.raw })"
        v-loading="importLoading"
      >
        <el-icon style="font-size: 32px; color: #c0c4cc;"><Upload /></el-icon>
        <div style="color: #606266; margin-top: 8px;">将 .xlsx 文件拖到此处，或点击选择</div>
      </el-upload>
      <template #footer>
        <el-button size="small" @click="handleDownloadTemplate">
          <el-icon><Download /></el-icon> 下载模板
        </el-button>
        <el-button @click="showImportDialog = false">关闭</el-button>
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
