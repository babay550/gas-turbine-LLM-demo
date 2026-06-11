<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete, Download, Refresh } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import {
  uploadDataFile,
  executeImport,
  getImportJobs,
  deleteImportJob,
  getImportJobStatus,
  getImportJobPreview,
  getParameters,
  getImportTimeFormats,
} from '../api'
import type { ImportPreview, ImportJob, ImportColumnMapping, ParameterDefinition } from '../types'

// ────── 状态 ──────

const step = ref(0) // 0=上传, 1=列映射, 2=完成

// 上传
const uploading = ref(false)
const preview = ref<ImportPreview | null>(null)

// 列映射
const parameters = ref<ParameterDefinition[]>([])
const paramLoading = ref(false)
const formatType = ref<'wide' | 'long'>('wide')
const timestampColumn = ref('')
const timestampFormat = ref('')
const unitId = ref('GT-01')
const timestampPresets = ref<any[]>([])
const presetSelect = ref('auto')
// 宽表映射
const columnMap = ref<Record<string, string>>({})
// 长表字段
const longParamColumn = ref('')
const longValueColumn = ref('')

// 执行
const importing = ref(false)
const importProgress = ref(0)
const importResult = ref<{ job_id: number; status: string; imported_rows?: number; error_message?: string } | null>(null)

// 历史记录
const jobs = ref<ImportJob[]>([])
const jobsLoading = ref(false)
const restoringPreview = ref(false)

// ────── 计算属性 ──────

const fileColumns = computed(() => preview.value?.columns || [])

const groupedParams = computed(() => {
  const groups: Record<string, { key: string; name: string; unit: string }[]> = {}
  for (const p of parameters.value) {
    const sub = (p as any).subsystem || '其他'
    if (!groups[sub]) groups[sub] = []
    groups[sub].push({ key: (p as any).key || p.name.replace(/ /g, '_'), name: p.name, unit: p.unit })
  }
  return groups
})

const paramOptions = computed(() => {
  const opts: { label: string; value: string; group: string }[] = []
  for (const [group, items] of Object.entries(groupedParams.value)) {
    for (const item of items) {
      opts.push({ label: `${item.name} (${item.unit})`, value: item.key, group })
    }
  }
  return opts
})

// ────── 方法 ──────

async function loadParameters() {
  paramLoading.value = true
  try {
    const res = await getParameters()
    parameters.value = res.parameters
  } catch (e: any) {
    ElMessage.error('加载参数列表失败: ' + (e.message || e))
  } finally {
    paramLoading.value = false
  }
}

async function handleUpload(uploadFile: UploadFile) {
  if (!uploadFile.raw) return
  uploading.value = true
  preview.value = null

  try {
    const res = await uploadDataFile(uploadFile.raw)
    preview.value = res
    formatType.value = res.format_hint as 'wide' | 'long'
    timestampColumn.value = res.detected_timestamp_column || ''

    // 自动匹配列名到参数
    columnMap.value = {}
    for (const col of res.columns) {
      if (col === timestampColumn.value) {
        columnMap.value[col] = 'skip'
        continue
      }
      // 尝试精确匹配参数名
      const matched = parameters.value.find(p => {
        const key = (p as any).key || p.name.replace(/ /g, '_')
        return col === p.name || col === key || p.name.includes(col) || col.includes(p.name)
      })
      columnMap.value[col] = matched ? ((matched as any).key || matched.name.replace(/ /g, '_')) : ''
    }

    step.value = 1
    ElMessage.success(`文件解析完成，共 ${res.row_count} 行`)
  } catch (e: any) {
    ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message || e))
  } finally {
    uploading.value = false
  }
}

function autoMatchColumns() {
  for (const col of fileColumns.value) {
    if (col === timestampColumn.value) {
      columnMap.value[col] = 'skip'
      continue
    }
    const matched = parameters.value.find(p => {
      const key = (p as any).key || p.name.replace(/ /g, '_')
      return col === p.name || col === key || p.name.includes(col) || col.includes(p.name)
    })
    if (matched) {
      columnMap.value[col] = (matched as any).key || matched.name.replace(/ /g, '_')
    }
  }
  ElMessage.success('已自动匹配列名')
}

async function handleImport() {
  if (!preview.value) return
  if (!timestampColumn.value) {
    ElMessage.warning('请选择时间戳列')
    return
  }

  // 检查宽表模式至少映射了一个参数
  if (formatType.value === 'wide') {
    const mappedCount = Object.values(columnMap.value).filter(v => v && v !== 'skip').length
    if (mappedCount === 0) {
      ElMessage.warning('请至少映射一个参数列')
      return
    }
  }

  importing.value = true
  importProgress.value = 10

  // 处理时间格式选项：auto / custom / preset(format string)
  let fmt: string | undefined = undefined
  if (presetSelect.value === 'auto') {
    fmt = undefined
  } else if (presetSelect.value === 'custom') {
    fmt = timestampFormat.value || undefined
  } else {
    fmt = presetSelect.value || undefined
  }

  const mapping: ImportColumnMapping = {
    timestamp_column: timestampColumn.value,
    timestamp_format: fmt,
    format_type: formatType.value,
    unit_id: unitId.value,
  }

  if (formatType.value === 'wide') {
    mapping.column_map = { ...columnMap.value }
  } else {
    mapping.long_param_column = longParamColumn.value
    mapping.long_value_column = longValueColumn.value
  }

  // 模拟进度
  const progressTimer = setInterval(() => {
    if (importProgress.value < 90) importProgress.value += 5
  }, 1000)

  try {
    const result = await executeImport(preview.value.job_id, mapping)
    clearInterval(progressTimer)
    importProgress.value = 100
    importResult.value = result
    step.value = 2

    if (result.status === 'completed') {
      ElMessage.success(`导入成功！共导入 ${result.imported_rows} 条记录`)
    } else {
      ElMessage.error(`导入失败: ${result.error_message || '未知错误'}`)
    }
    loadJobs()
  } catch (e: any) {
    clearInterval(progressTimer)
    ElMessage.error('导入失败: ' + (e.response?.data?.detail || e.message || e))
  } finally {
    importing.value = false
  }
}

function resetImport() {
  step.value = 0
  preview.value = null
  importResult.value = null
  importProgress.value = 0
  columnMap.value = {}
}

async function loadJobs() {
  jobsLoading.value = true
  try {
    const res = await getImportJobs()
    jobs.value = res.jobs || []
  } catch { /* ignore */ } finally {
    jobsLoading.value = false
  }
}

async function restorePreview(job: ImportJob) {
  if (job.status === 'completed' || job.status === 'error') {
    // 已完成/失败的任务也可以重新导入
  }
  restoringPreview.value = true
  try {
    const res = await getImportJobPreview(job.id)
    preview.value = res
    formatType.value = res.format_hint as 'wide' | 'long'
    timestampColumn.value = res.detected_timestamp_column || ''
    presetSelect.value = 'auto'
    timestampFormat.value = ''
    unitId.value = 'GT-01'

    // 自动匹配列名到参数
    columnMap.value = {}
    for (const col of res.columns) {
      if (col === timestampColumn.value) {
        columnMap.value[col] = 'skip'
        continue
      }
      const matched = parameters.value.find(p => {
        const key = (p as any).key || p.name.replace(/ /g, '_')
        return col === p.name || col === key || p.name.includes(col) || col.includes(p.name)
      })
      columnMap.value[col] = matched ? ((matched as any).key || matched.name.replace(/ /g, '_')) : ''
    }

    step.value = 1
    ElMessage.success(`已恢复文件预览: ${res.filename}`)
  } catch (e: any) {
    ElMessage.error('恢复预览失败: ' + (e.response?.data?.detail || e.message || e))
  } finally {
    restoringPreview.value = false
  }
}

async function handleDeleteJob(job: ImportJob) {
  try {
    await ElMessageBox.confirm(`确定删除导入任务"${job.filename}"及其所有数据？`, '确认删除', { type: 'warning' })
    await deleteImportJob(job.id)
    ElMessage.success('删除成功')
    loadJobs()
  } catch { /* cancelled */ }
}

function statusTagType(status: string) {
  const map: Record<string, string> = {
    completed: 'success', error: 'danger', pending: 'info',
    parsing: 'warning', validating: 'warning', storing: 'warning', preview: '',
  }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '等待中', preview: '待确认', parsing: '解析中',
    validating: '校验中', storing: '入库中', completed: '已完成', error: '失败',
  }
  return map[status] || status
}

function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

// ────── 初始化 ──────

async function loadTimeFormats() {
  try {
    const res = await getImportTimeFormats()
    timestampPresets.value = res.presets || []
  } catch (e) {
    console.error('loadTimeFormats failed', e)
  }
}

loadParameters()
loadJobs()
loadTimeFormats()
</script>

<template>
  <div class="data-import-page">
    <h2 style="margin: 0 0 16px; font-size: 20px;">数据导入</h2>

    <!-- 步骤条 -->
    <el-steps :active="step" finish-status="success" style="margin-bottom: 24px;">
      <el-step title="上传文件" />
      <el-step title="列映射配置" />
      <el-step title="导入完成" />
    </el-steps>

    <!-- Step 0: 上传 -->
    <div v-if="step === 0">
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".xlsx,.xls,.csv,.json"
        :on-change="handleUpload"
        :disabled="uploading"
        class="upload-area"
      >
        <el-icon :size="48" style="color: #c0c4cc;"><UploadFilled /></el-icon>
        <div style="margin-top: 12px; color: #606266;">
          将文件拖到此处，或 <em style="color: #409eff;">点击上传</em>
        </div>
        <template #tip>
          <div style="color: #909399; font-size: 12px; margin-top: 8px;">
            支持 .xlsx / .xls / .csv / .json 格式，文件大小不限
          </div>
        </template>
      </el-upload>
      <div v-if="uploading" style="text-align: center; margin-top: 16px;">
        <el-icon class="is-loading" :size="24"><Refresh /></el-icon>
        <span style="margin-left: 8px; color: #909399;">正在解析文件...</span>
      </div>
    </div>

    <!-- Step 1: 列映射 -->
    <div v-if="step === 1 && preview">
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>文件预览: {{ preview.filename }} ({{ preview.row_count }} 行)</span>
            <el-button @click="resetImport" text>重新上传</el-button>
          </div>
        </template>

        <!-- 数据预览表格 -->
        <el-table :data="preview.preview_rows" size="small" stripe border style="margin-bottom: 16px;"
                  :max-height="250">
          <el-table-column v-for="col in preview.columns" :key="col" :prop="col" :label="col"
                           min-width="120" show-overflow-tooltip />
        </el-table>

        <!-- 配置表单 -->
        <el-form label-width="120px" style="max-width: 600px;">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="表格式">
                <el-radio-group v-model="formatType">
                  <el-radio value="wide">宽表</el-radio>
                  <el-radio value="long">长表</el-radio>
                </el-radio-group>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="机组ID">
                <el-input v-model="unitId" style="width: 150px;" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="时间戳列">
                <el-select v-model="timestampColumn" placeholder="选择时间列">
                  <el-option v-for="col in fileColumns" :key="col" :label="col" :value="col" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="时间格式">
                <el-select v-model="presetSelect" placeholder="选择时间格式" clearable style="width: 100%;">
                  <el-option :label="'自动检测（推荐）'" :value="'auto'"></el-option>
                  <el-option v-for="p in timestampPresets" :key="p.format" :label="p.key + ' — ' + p.example" :value="p.format" />
                  <el-option :label="'自定义格式'" :value="'custom'" />
                </el-select>
                <div style="margin-top:8px;">
                  <el-input v-if="presetSelect==='custom'" v-model="timestampFormat" placeholder="%Y-%m-%d %H:%M:%S" />
                  <div v-else style="color:#909399; font-size:12px;">
                    <span v-if="presetSelect==='auto'">自动检测格式；必要时选择预设或自定义。</span>
                    <span v-else>示例: {{ timestampPresets.find(p=>p.format===presetSelect)?.example || '' }}</span>
                  </div>
                </div>
              </el-form-item>
            </el-col>
          </el-row>

          <!-- 宽表列映射 -->
          <template v-if="formatType === 'wide'">
            <el-divider content-position="left">
              列映射
              <el-button size="small" type="primary" link @click="autoMatchColumns" style="margin-left: 8px;">
                自动匹配
              </el-button>
            </el-divider>
            <el-table :data="fileColumns.map(col => ({ col, mapped: columnMap[col] || '' }))" size="small"
                      border style="width: 100%;">
              <el-table-column label="文件列名" prop="col" width="200" />
              <el-table-column label="预览值" width="150">
                <template #default="{ row }">
                  <span style="color: #909399; font-size: 12px;">
                    {{ preview?.preview_rows?.[0]?.[row.col] || '-' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="映射到参数">
                <template #default="{ row }">
                  <el-select v-model="columnMap[row.col]" placeholder="选择参数" clearable filterable
                             style="width: 100%;">
                    <el-option value="skip" label="跳过此列">
                      <span style="color: #909399;">跳过此列</span>
                    </el-option>
                    <el-option-group v-for="(items, group) in groupedParams" :key="group" :label="group">
                      <el-option v-for="item in items" :key="item.key"
                                 :label="`${item.name} (${item.unit})`" :value="item.key" />
                    </el-option-group>
                  </el-select>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <!-- 长表配置 -->
          <template v-if="formatType === 'long'">
            <el-divider content-position="left">长表配置</el-divider>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="参数名列">
                  <el-select v-model="longParamColumn" placeholder="选择参数名列">
                    <el-option v-for="col in fileColumns" :key="col" :label="col" :value="col" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="值列">
                  <el-select v-model="longValueColumn" placeholder="选择值列">
                    <el-option v-for="col in fileColumns" :key="col" :label="col" :value="col" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </template>
        </el-form>
      </el-card>

      <div style="text-align: center;">
        <el-button type="primary" size="large" :loading="importing" @click="handleImport"
                   :disabled="!timestampColumn">
          <el-icon v-if="!importing"><Upload /></el-icon>
          {{ importing ? '导入中...' : '开始导入' }}
        </el-button>
      </div>

      <el-progress v-if="importing" :percentage="importProgress" :stroke-width="20"
                   style="margin-top: 16px;" />
    </div>

    <!-- Step 2: 完成 -->
    <div v-if="step === 2">
      <el-result
        :icon="importResult?.status === 'completed' ? 'success' : 'error'"
        :title="importResult?.status === 'completed' ? '导入完成' : '导入失败'"
        :sub-title="importResult?.status === 'completed'
          ? `成功导入 ${importResult?.imported_rows} 条记录`
          : importResult?.error_message || '未知错误'"
      >
        <template #extra>
          <el-button type="primary" @click="resetImport">继续导入</el-button>
          <el-button @click="$router.push('/historical')">查看历史数据</el-button>
        </template>
      </el-result>
    </div>

    <!-- 导入历史 -->
    <el-card shadow="never" style="margin-top: 24px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>导入历史</span>
          <el-button size="small" :icon="Refresh" @click="loadJobs" :loading="jobsLoading" circle />
        </div>
      </template>
      <el-table :data="jobs" size="small" stripe v-loading="jobsLoading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip class-name="clickable-row" />
        <el-table-column prop="file_type" label="类型" width="70" />
        <el-table-column label="大小" width="90">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column prop="total_rows" label="总行数" width="90" />
        <el-table-column prop="imported_rows" label="已导入" width="80" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ row.created_at?.replace('T', ' ')?.slice(0, 19) || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="restorePreview(row)" :loading="restoringPreview">
              配置
            </el-button>
            <el-button size="small" type="danger" :icon="Delete" circle @click="handleDeleteJob(row)" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.data-import-page {
  max-width: 1200px;
  margin: 0 auto;
}
.upload-area {
  width: 100%;
}
.upload-area :deep(.el-upload-dragger) {
  width: 100%;
  padding: 40px 20px;
}
</style>
