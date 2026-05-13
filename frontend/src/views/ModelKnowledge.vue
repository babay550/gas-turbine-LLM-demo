<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GraphChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import * as api from '../api'
import type { ModelEntry, ExpertRule, CausalGraph, CausalNode, VectorKBSource, ModelTestResult, WikiEntryMeta, WikiEntry, WikiStatsResponse, RawFileInfo, WikiGraphData } from '../types'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, GraphChart, TitleComponent, TooltipComponent, LegendComponent])

const activeTab = ref('models')
const loading = ref(false)

const models = ref<ModelEntry[]>([])
const modelTotal = ref(0)
const modelTestResults = ref<Record<string, ModelTestResult>>({})
const modelTesting = ref<Record<string, boolean>>({})

const knowledgeSubTab = ref('tech-kb')
const expertRules = ref<ExpertRule[]>([])
const expertRulesTotal = ref(0)
const causalGraph = ref<CausalGraph | null>(null)

const vectorSources = ref<VectorKBSource[]>([])
const vectorTotal = ref(0)

// --- Wiki 技术知识库状态 ---
const wikiEntries = ref<WikiEntryMeta[]>([])
const wikiTotal = ref(0)
const wikiStats = ref<WikiStatsResponse | null>(null)
const wikiSearch = ref('')
const wikiFilterType = ref('')
const wikiFilterCategory = ref('')
const wikiLoading = ref(false)
const wikiCurrentPage = ref(1)
const wikiPageSize = ref(20)

const showWikiDetail = ref(false)
const currentWikiEntry = ref<WikiEntry | null>(null)
const wikiDetailLoading = ref(false)

const showWikiUploadDialog = ref(false)
const wikiUploading = ref(false)

const showWikiQADialog = ref(false)
const wikiQAQuery = ref('')
const wikiQAAnswer = ref('')
const wikiQACitations = ref<any[]>([])
const wikiQALoading = ref(false)

// --- Raw 文件查看 ---
const showRawFilesDrawer = ref(false)
const rawFiles = ref<RawFileInfo[]>([])
const rawFilesLoading = ref(false)
const showRawContentDialog = ref(false)
const rawContentTitle = ref('')
const rawContentText = ref('')

// --- Wiki 索引/日志查看 ---
const showIndexDialog = ref(false)
const indexContent = ref('')
const showLogDialog = ref(false)
const logContent = ref('')

// --- Wiki 知识图谱 ---
const wikiGraphData = ref<WikiGraphData | null>(null)
const wikiGraphLoading = ref(false)

// --- Detail drawers ---
const showMaintenanceDetail = ref(false)
const currentMaintenance = ref<MaintenanceKnowledge | null>(null)
const showRuleDetail = ref(false)
const currentRule = ref<ExpertRule | null>(null)

// --- Add forms ---
const showModelDialog = ref(false)
const modelForm = reactive({ name: '', url: '', method: 'POST', input_params_text: '', output_format: '' })

const showRuleDialog = ref(false)
const ruleForm = reactive({
  name: '', condition: '', conclusion: '', confidence: 0.85,
  severity: '中', related_params_text: '', recommended_actions: '',
})

const showCausalNodeDialog = ref(false)
const causalNodeForm = reactive({ name: '', type: 'symptom', connected_nodes: [] as string[] })
const showCausalEdgeDialog = ref(false)
const causalEdgeForm = reactive({ source: '', target: '', weight: 0.5 })

const showVectorDialog = ref(false)
const vectorForm = reactive({ name: '', url: '', embedding_model: 'bge-large-zh' })

// --- Severity tag colors ---
function severityType(s?: string) {
  if (s === '高') return 'danger'
  if (s === '中') return 'warning'
  return 'info'
}

// --- Wiki type labels ---
const wikiTypeLabels: Record<string, string> = {
  content_summary: '内容摘要',
  entity: '实体词条',
  concept: '概念词条',
  comparative: '对比分析',
  overview: '总览综述',
}
function wikiTypeTag(type: string) {
  const map: Record<string, string> = { content_summary: '', entity: 'success', concept: 'warning', comparative: 'danger', overview: 'info' }
  return map[type] || ''
}

// --- Causal Graph Chart ---
const graphOption = computed(() => {
  if (!causalGraph.value) return {}
  const { nodes, edges } = causalGraph.value
  const colorMap: Record<string, string> = { symptom: '#e6a23c', subsystem: '#409eff', root_cause: '#f56c6c', trigger_rule: '#9b59b6' }
  const categoryIndex: Record<string, number> = { symptom: 0, subsystem: 1, root_cause: 2, trigger_rule: 3 }
  const categories = [
    { name: '征兆', itemStyle: { color: '#e6a23c' } },
    { name: '子系统', itemStyle: { color: '#409eff' } },
    { name: '根因', itemStyle: { color: '#f56c6c' } },
    { name: '触发规则', itemStyle: { color: '#9b59b6' } },
  ]
  const symSize = (t: string) => t === 'trigger_rule' ? 28 : t === 'root_cause' ? 50 : t === 'subsystem' ? 40 : 30
  return {
    tooltip: {},
    legend: { data: categories.map(c => c.name), top: 0, selectedMode: false },
    series: [{
      type: 'graph', layout: 'force',
      data: nodes.map((n: CausalNode) => ({
        id: n.id, name: `${n.name}\n(${n.id})`,
        symbolSize: symSize(n.type),
        itemStyle: { color: colorMap[n.type] ?? '#909399' },
        category: categoryIndex[n.type] ?? 0,
        label: { show: true, fontSize: n.type === 'trigger_rule' ? 9 : 11 },
      })),
      links: edges.map(e => ({ source: e.source, target: e.target, lineStyle: { width: Math.max(1, e.weight * 3), opacity: 0.7, curveness: 0.2 } })),
      categories, roam: true, draggable: true,
      force: { repulsion: 300, gravity: 0.1, edgeLength: [100, 200] },
      label: { position: 'bottom' },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4 } },
    }],
  }
})

const nodeOptions = computed(() => {
  if (!causalGraph.value) return []
  return causalGraph.value.nodes.map(n => ({ value: n.id, label: `${n.name} (${n.id})`, type: n.type }))
})

// --- Data loaders ---
async function loadModels() {
  loading.value = true
  try { const r = await api.getModels(); models.value = r.models; modelTotal.value = r.total }
  catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : String(e)) }
  finally { loading.value = false }
}

async function loadWikiEntries() {
  wikiLoading.value = true
  try {
    const r = await api.getWikiEntries({
      search: wikiSearch.value || undefined,
      type: wikiFilterType.value || undefined,
      category: wikiFilterCategory.value || undefined,
      page: wikiCurrentPage.value,
      page_size: wikiPageSize.value,
    })
    wikiEntries.value = r.entries
    wikiTotal.value = r.total
  } catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : String(e)) }
  finally { wikiLoading.value = false }
}

async function loadWikiStats() {
  try { wikiStats.value = await api.getWikiStats() }
  catch { /* ignore */ }
}

async function loadExpertRules() {
  loading.value = true
  try { const r = await api.getExpertRules(); expertRules.value = r.rules; expertRulesTotal.value = r.total }
  catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : String(e)) }
  finally { loading.value = false }
}

async function loadCausalGraph() {
  loading.value = true
  try { causalGraph.value = await api.getCausalGraph() }
  catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : String(e)) }
  finally { loading.value = false }
}

async function loadVectorSources() {
  loading.value = true
  try { const r = await api.getVectorKBSources(); vectorSources.value = r.sources; vectorTotal.value = r.total }
  catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : String(e)) }
  finally { loading.value = false }
}

async function handleTabChange(tab: string) {
  if (tab === 'models' && models.value.length === 0) await loadModels()
  else if (tab === 'knowledge') {
    if (wikiEntries.value.length === 0) { await loadWikiEntries(); await loadWikiStats() }
    if (expertRules.value.length === 0) await loadExpertRules()
  }
  else if (tab === 'causal' && !causalGraph.value) await loadCausalGraph()
  else if (tab === 'vector' && vectorSources.value.length === 0) await loadVectorSources()
}

function handleKnowledgeSubTabChange() {
  if (knowledgeSubTab.value === 'tech-kb' && wikiEntries.value.length === 0) { loadWikiEntries(); loadWikiStats() }
  else if (knowledgeSubTab.value === 'rules' && expertRules.value.length === 0) loadExpertRules()
}

function statusType(status: string) { return status === 'online' ? 'success' : 'danger' }
function vectorStatusType(status: string) { return status === 'connected' ? 'success' : 'danger' }

// --- Wiki actions ---
async function viewWikiEntry(entry: WikiEntryMeta) {
  wikiDetailLoading.value = true
  showWikiDetail.value = true
  try {
    currentWikiEntry.value = await api.getWikiEntry(entry.id)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载词条失败')
  } finally {
    wikiDetailLoading.value = false
  }
}

async function handleWikiUpload(uploadFile: any) {
  wikiUploading.value = true
  try {
    const result = await api.uploadWikiDocument(uploadFile.raw || uploadFile, true)
    ElMessage.success(result.message || `处理完成，生成 ${result.entries_created} 条词条`)
    showWikiUploadDialog.value = false
    await loadWikiEntries()
    await loadWikiStats()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '上传处理失败')
  } finally {
    wikiUploading.value = false
  }
}

function handleWikiSearch() {
  wikiCurrentPage.value = 1
  loadWikiEntries()
}

async function handleWikiQA() {
  if (!wikiQAQuery.value.trim()) return
  wikiQALoading.value = true
  wikiQAAnswer.value = ''
  wikiQACitations.value = []
  try {
    const result = await api.wikiQA(wikiQAQuery.value)
    wikiQAAnswer.value = result.answer
    wikiQACitations.value = result.citations || []
  } catch (e: unknown) {
    wikiQAAnswer.value = '问答失败: ' + (e instanceof Error ? e.message : String(e))
  } finally {
    wikiQALoading.value = false
  }
}

async function deleteWikiEntryById(entryId: string) {
  try {
    await api.deleteWikiEntry(entryId)
    ElMessage.success('词条已删除')
    showWikiDetail.value = false
    await loadWikiEntries()
    await loadWikiStats()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

// --- Detail view handlers ---
function viewRuleDetail(rule: ExpertRule) {
  currentRule.value = rule
  showRuleDetail.value = true
}

// --- Model connectivity test ---
async function handleTestModel(model: ModelEntry) {
  modelTesting.value[model.id] = true
  try {
    const result = await api.testModelConnection(model.id)
    modelTestResults.value[model.id] = result
    model.status = result.success ? 'online' : 'offline'
    if (result.last_check) model.last_check = result.last_check
    if (result.success) ElMessage.success(`${model.name}: 联通成功 (${result.latency_ms}ms)`)
    else ElMessage.warning(`${model.name}: ${result.error || result.message || '联通失败'}`)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '测试请求失败')
  } finally {
    modelTesting.value[model.id] = false
  }
}

// --- Vector KB test ---
async function handleTestVector(source: VectorKBSource) {
  modelTesting.value[source.id] = true
  try {
    const result = await api.testVectorKBConnection(source.id)
    source.status = result.success ? 'connected' : 'disconnected'
    if (result.success) ElMessage.success(`${source.name}: 联通成功 (${result.latency_ms}ms)`)
    else ElMessage.warning(`${source.name}: ${result.error || '联通失败'}`)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '测试请求失败')
  } finally {
    modelTesting.value[source.id] = false
  }
}

// --- Add handlers ---
function handleAddModel() {
  const newModel: ModelEntry = {
    id: `M${String(models.value.length + 1).padStart(3, '0')}`,
    name: modelForm.name, url: modelForm.url, method: modelForm.method,
    input_params: modelForm.input_params_text.split(',').map(s => s.trim()).filter(Boolean),
    output_format: modelForm.output_format, status: 'offline', last_check: '-',
  }
  models.value.push(newModel); modelTotal.value = models.value.length
  showModelDialog.value = false
  Object.assign(modelForm, { name: '', url: '', method: 'POST', input_params_text: '', output_format: '' })
  ElMessage.success('模型接口已添加，可点击"联通测试"验证')
}

function handleAddRule() {
  const newRule: ExpertRule = {
    id: `R${String(expertRules.value.length + 1).padStart(3, '0')}`,
    name: ruleForm.name, condition: ruleForm.condition, conclusion: ruleForm.conclusion, confidence: ruleForm.confidence,
    severity: ruleForm.severity,
    related_params: ruleForm.related_params_text.split(',').map(s => s.trim()).filter(Boolean),
    recommended_actions: ruleForm.recommended_actions,
  }
  expertRules.value.push(newRule); expertRulesTotal.value = expertRules.value.length
  showRuleDialog.value = false
  Object.assign(ruleForm, { name: '', condition: '', conclusion: '', confidence: 0.85, severity: '中', related_params_text: '', recommended_actions: '' })
  ElMessage.success('专家规则已添加')
}

function handleAddCausalNode() {
  if (!causalGraph.value) return
  const newId = `n${causalGraph.value.nodes.length + 1}`
  causalGraph.value.nodes.push({ id: newId, name: causalNodeForm.name, type: causalNodeForm.type as any })
  for (const targetId of causalNodeForm.connected_nodes) {
    const sourceExists = causalGraph.value.nodes.find(n => n.id === newId)
    const targetExists = causalGraph.value.nodes.find(n => n.id === targetId)
    if (sourceExists && targetExists) {
      causalGraph.value.edges.push({ source: newId, target: targetId, weight: 0.5 })
    }
  }
  showCausalNodeDialog.value = false
  Object.assign(causalNodeForm, { name: '', type: 'symptom', connected_nodes: [] })
  ElMessage.success('因果图节点已添加')
}

function handleAddCausalEdge() {
  if (!causalGraph.value) return
  causalGraph.value.edges.push({ source: causalEdgeForm.source, target: causalEdgeForm.target, weight: causalEdgeForm.weight })
  showCausalEdgeDialog.value = false
  Object.assign(causalEdgeForm, { source: '', target: '', weight: 0.5 })
  ElMessage.success('因果图边已添加')
}

async function handleAddVectorSource() {
  try {
    await api.addVectorKBSource({ name: vectorForm.name, url: vectorForm.url, embedding_model: vectorForm.embedding_model })
    ElMessage.success('向量知识库已接入')
    showVectorDialog.value = false
    Object.assign(vectorForm, { name: '', url: '', embedding_model: 'bge-large-zh' })
    await loadVectorSources()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '添加失败')
  }
}

function openCausalNodeDialog() {
  causalNodeForm.connected_nodes = []
  showCausalNodeDialog.value = true
}

// --- Raw files ---
async function loadRawFiles() {
  rawFilesLoading.value = true
  try {
    const r = await api.getWikiRawFiles()
    rawFiles.value = r.files
  } catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : '加载失败') }
  finally { rawFilesLoading.value = false }
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function viewRawFile(file: RawFileInfo) {
  if (file.type === 'md') {
    try {
      const r = await api.getWikiRawFile(file.name)
      rawContentTitle.value = file.name
      rawContentText.value = r.content
      showRawContentDialog.value = true
    } catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : '加载失败') }
  } else {
    window.open(`/api/knowledge/knowledge/wiki/raw-files/${encodeURIComponent(file.name)}`, '_blank')
  }
}

function openRawFilesDrawer() {
  showRawFilesDrawer.value = true
  if (rawFiles.value.length === 0) loadRawFiles()
}

// --- Index/Log dialogs ---
async function openIndexDialog() {
  showIndexDialog.value = true
  if (!indexContent.value) {
    try { indexContent.value = await api.getWikiIndexContent() }
    catch (e: unknown) { indexContent.value = '加载失败' }
  }
}

async function openLogDialog() {
  showLogDialog.value = true
  try { logContent.value = await api.getWikiLogContent() }
  catch (e: unknown) { logContent.value = '加载失败' }
}

// --- Wiki graph ---
async function loadWikiGraph() {
  wikiGraphLoading.value = true
  try { wikiGraphData.value = await api.getWikiGraph() }
  catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : '加载图谱失败') }
  finally { wikiGraphLoading.value = false }
}

const wikiGraphOption = computed(() => {
  if (!wikiGraphData.value || wikiGraphData.value.nodes.length === 0) return {}
  const { nodes, edges } = wikiGraphData.value
  const typeLabels: Record<string, string> = {
    content_summary: '内容摘要', entity: '实体词条', concept: '概念词条',
    comparative: '对比分析', overview: '总览综述',
  }
  const categories = [
    { name: '内容摘要', itemStyle: { color: '#409eff' } },
    { name: '实体词条', itemStyle: { color: '#67c23a' } },
    { name: '概念词条', itemStyle: { color: '#e6a23c' } },
    { name: '对比分析', itemStyle: { color: '#f56c6c' } },
    { name: '总览综述', itemStyle: { color: '#9b59b6' } },
  ]
  const catIdx: Record<string, number> = { content_summary: 0, entity: 1, concept: 2, comparative: 3, overview: 4 }
  return {
    tooltip: { formatter: '{b}' },
    legend: { data: categories.map(c => c.name), top: 0 },
    animationDurationUpdate: 300,
    series: [{
      type: 'graph', layout: 'force',
      data: nodes.map(n => ({
        id: n.id, name: n.name,
        symbolSize: 16 + Math.min(n.degree * 4, 24),
        itemStyle: { color: n.color },
        category: catIdx[n.type] ?? 0,
        label: { show: true, fontSize: 8, color: '#606266' },
      })),
      links: edges.map(e => ({
        source: e.source, target: e.target,
        lineStyle: { width: Math.max(1, e.weight * 3), opacity: 0.5, curveness: 0.05 },
      })),
      categories, roam: true, draggable: true,
      force: {
        repulsion: 500,
        gravity: 0.03,
        edgeLength: [60, 150],
        friction: 0.6,
        layoutAnimation: false,
      },
      label: { position: 'right' },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4 } },
    }],
  }
})

onMounted(async () => { await loadModels() })
</script>

<template>
  <div class="page-knowledge">
    <el-card shadow="never" class="knowledge-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">

        <!-- Tab 1: Models -->
        <el-tab-pane label="小模型接口" name="models">
          <div class="tab-header">
            <span class="total-label">共 {{ modelTotal }} 个模型</span>
            <div>
              <el-button type="primary" size="small" @click="showModelDialog = true">添加模型</el-button>
              <el-button size="small" @click="loadModels">刷新</el-button>
            </div>
          </div>
          <el-table v-loading="loading" :data="models" stripe size="small">
            <el-table-column prop="id" label="模型ID" width="100" />
            <el-table-column prop="name" label="模型名称" min-width="140" />
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ row.status === 'online' ? '在线' : '离线' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="url" label="接口地址" width="220" show-overflow-tooltip />
            <el-table-column prop="method" label="方法" width="70" align="center" />
            <el-table-column label="输入参数" min-width="160">
              <template #default="{ row }">
                <el-tag v-for="p in (row.input_params as string[]).slice(0, 3)" :key="p" size="small" type="info" style="margin:0 2px 2px 0;">{{ p }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_check" label="最后检查" width="160" />
            <el-table-column label="联通测试" width="160" align="center">
              <template #default="{ row }">
                <div class="test-cell">
                  <el-button size="small" :loading="modelTesting[row.id]" @click="handleTestModel(row)">
                    {{ modelTestResults[row.id]?.success ? '重测' : '测试' }}
                  </el-button>
                  <template v-if="modelTestResults[row.id]">
                    <el-tag v-if="modelTestResults[row.id].success" type="success" size="small">
                      {{ modelTestResults[row.id].latency_ms }}ms
                    </el-tag>
                    <el-tooltip v-else :content="modelTestResults[row.id].error || ''" placement="top">
                      <el-tag type="danger" size="small">失败</el-tag>
                    </el-tooltip>
                  </template>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab 2: Knowledge -->
        <el-tab-pane label="知识库" name="knowledge">
          <el-tabs v-model="knowledgeSubTab" @tab-change="handleKnowledgeSubTabChange">

            <!-- Sub-tab: 技术知识库 -->
            <el-tab-pane label="技术知识库" name="tech-kb">
              <div class="tab-header">
                <div class="wiki-stats-bar">
                  <span class="total-label">共 {{ wikiTotal }} 条词条</span>
                  <template v-if="wikiStats">
                    <el-tag v-for="(count, t) in wikiStats.by_type" :key="t" size="small" :type="wikiTypeTag(t)" style="margin-left:6px;">
                      {{ wikiTypeLabels[t] || t }} {{ count }}
                    </el-tag>
                  </template>
                </div>
                <div>
                  <el-button type="primary" size="small" @click="showWikiUploadDialog = true">上传文档</el-button>
                  <el-button size="small" @click="openRawFilesDrawer">原始资料</el-button>
                  <el-button size="small" @click="openIndexDialog">内容索引</el-button>
                  <el-button size="small" @click="openLogDialog">操作日志</el-button>
                  <el-button size="small" @click="showWikiQADialog = true">知识问答</el-button>
                  <el-button size="small" @click="loadWikiEntries(); loadWikiStats()">刷新</el-button>
                </div>
              </div>

              <!-- 搜索和筛选 -->
              <div class="wiki-filter-bar">
                <el-input v-model="wikiSearch" placeholder="搜索词条..." clearable style="width:260px;" size="small" @keyup.enter="handleWikiSearch" @clear="handleWikiSearch">
                  <template #prefix><el-icon><Search /></el-icon></template>
                </el-input>
                <el-select v-model="wikiFilterType" placeholder="类型" clearable size="small" style="width:130px;margin-left:8px;" @change="handleWikiSearch">
                  <el-option v-for="(label, key) in wikiTypeLabels" :key="key" :label="label" :value="key" />
                </el-select>
                <el-select v-model="wikiFilterCategory" placeholder="分类" clearable size="small" style="width:120px;margin-left:8px;" @change="handleWikiSearch">
                  <el-option label="压气机" value="压气机" />
                  <el-option label="燃烧室" value="燃烧室" />
                  <el-option label="透平" value="透平" />
                  <el-option label="发电机" value="发电机" />
                  <el-option label="余热锅炉" value="余热锅炉" />
                  <el-option label="控制系统" value="控制系统" />
                  <el-option label="整机" value="整机" />
                  <el-option label="辅助系统" value="辅助系统" />
                </el-select>
                <el-button type="primary" size="small" style="margin-left:8px;" @click="handleWikiSearch">搜索</el-button>
              </div>

              <!-- 词条表格 -->
              <el-table v-loading="wikiLoading" :data="wikiEntries" stripe size="small" row-class-name="clickable-row" @row-click="viewWikiEntry">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
                <el-table-column label="类型" width="100" align="center">
                  <template #default="{ row }">
                    <el-tag :type="wikiTypeTag(row.type)" size="small">{{ wikiTypeLabels[row.type] || row.type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="category" label="分类" width="90" />
                <el-table-column label="标签" min-width="160">
                  <template #default="{ row }">
                    <el-tag v-for="t in (row.tags as string[]).slice(0, 3)" :key="t" size="small" style="margin:0 2px 2px 0;">{{ t }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="updated" label="更新时间" width="120" />
                <el-table-column label="操作" width="70" align="center">
                  <template #default="{ row }">
                    <el-button type="primary" link size="small" @click.stop="viewWikiEntry(row)">详情</el-button>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 分页 -->
              <div style="display:flex;justify-content:flex-end;margin-top:12px;">
                <el-pagination v-model:current-page="wikiCurrentPage" :page-size="wikiPageSize" :total="wikiTotal" layout="total, prev, pager, next" size="small" @current-change="loadWikiEntries" />
              </div>
            </el-tab-pane>

            <!-- Sub-tab: 知识图谱 -->
            <el-tab-pane label="知识图谱" name="wiki-graph" @tab-click="() => { if (!wikiGraphData) loadWikiGraph() }">
              <div class="tab-header">
                <span class="total-label">{{ wikiGraphData ? `${wikiGraphData.nodes.length} 节点, ${wikiGraphData.edges.length} 关联边` : '' }}</span>
                <el-button size="small" @click="loadWikiGraph">刷新</el-button>
              </div>
              <VChart v-if="wikiGraphData && wikiGraphData.nodes.length > 0" :option="wikiGraphOption" style="height:520px;width:100%;" autoresize />
              <el-empty v-else-if="!wikiGraphLoading" description="暂无图谱数据，请先上传文档生成 wiki 词条" />
              <div v-else style="text-align:center;padding:80px 0;color:#909399;">加载中...</div>
            </el-tab-pane>

            <!-- Sub-tab: 专家规则 -->
            <el-tab-pane label="专家规则" name="rules">
              <div class="tab-header">
                <span class="total-label">共 {{ expertRulesTotal }} 条规则</span>
                <div>
                  <el-button type="primary" size="small" @click="showRuleDialog = true">添加规则</el-button>
                  <el-button size="small" @click="loadExpertRules">刷新</el-button>
                </div>
              </div>
              <el-table v-loading="loading" :data="expertRules" stripe size="small" row-class-name="clickable-row" @row-click="viewRuleDetail">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="name" label="规则名称" min-width="150" />
                <el-table-column prop="condition" label="触发条件" min-width="200" show-overflow-tooltip />
                <el-table-column label="因果标签" min-width="260">
                  <template #default="{ row }">
                    <el-tag v-if="row.symptom_tag" size="small" color="#e6a23c" style="color:#fff;border:none;margin-right:4px;" effect="dark">{{ row.symptom_tag }}</el-tag>
                    <el-tag v-if="row.subsystem_tag && row.subsystem_tag !== '综合'" size="small" color="#409eff" style="color:#fff;border:none;margin-right:4px;" effect="dark">{{ row.subsystem_tag }}</el-tag>
                    <el-tag v-if="row.root_cause_tag" size="small" color="#f56c6c" style="color:#fff;border:none;margin-right:4px;" effect="dark">{{ row.root_cause_tag }}</el-tag>
                    <el-tag v-if="row.trigger_rule_id" size="small" color="#9b59b6" style="color:#fff;border:none;" effect="dark">{{ row.trigger_rule_id }}</el-tag>
                    <span v-if="!row.symptom_tag && !row.subsystem_tag && !row.root_cause_tag" style="color:#c0c4cc;font-size:12px;">综合诊断规则</span>
                  </template>
                </el-table-column>
                <el-table-column prop="conclusion" label="诊断结论" min-width="180" show-overflow-tooltip />
                <el-table-column label="严重度" width="70" align="center">
                  <template #default="{ row }">
                    <el-tag :type="severityType(row.severity)" size="small">{{ row.severity || '中' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="置信度" width="70" align="center">
                  <template #default="{ row }">
                    <span :style="{ color: row.confidence >= 0.85 ? '#67c23a' : '#e6a23c', fontWeight: 600 }">{{ (row.confidence * 100).toFixed(0) }}%</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="60" align="center">
                  <template #default="{ row }">
                    <el-button type="primary" link size="small" @click.stop="viewRuleDetail(row)">详情</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <!-- Tab 3: Vector KB Sources -->
        <el-tab-pane label="向量知识库" name="vector">
          <div class="tab-header">
            <span class="total-label">已接入 {{ vectorTotal }} 个向量知识库</span>
            <div>
              <el-button type="primary" size="small" @click="showVectorDialog = true">接入向量知识库</el-button>
              <el-button size="small" @click="loadVectorSources">刷新</el-button>
            </div>
          </div>
          <el-table v-loading="loading" :data="vectorSources" stripe size="small">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="知识库名称" min-width="160" />
            <el-table-column prop="url" label="接口地址" min-width="220" show-overflow-tooltip />
            <el-table-column prop="embedding_model" label="嵌入模型" width="130" />
            <el-table-column label="文档数" width="90" align="center">
              <template #default="{ row }">{{ row.doc_count.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="vectorStatusType(row.status)" size="small">{{ row.status === 'connected' ? '已连接' : '未连接' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="联通测试" width="130" align="center">
              <template #default="{ row }">
                <div class="test-cell">
                  <el-button size="small" :loading="modelTesting[row.id]" @click="handleTestVector(row)">测试</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="vectorSources.length === 0 && !loading" description="暂未接入向量知识库，点击上方按钮接入" />
        </el-tab-pane>

        <!-- Tab 4: Causal Graph -->
        <el-tab-pane label="因果图" name="causal">
          <div class="tab-header">
            <span class="total-label">{{ causalGraph ? `${causalGraph.nodes.length} 节点, ${causalGraph.edges.length} 边` : '' }}</span>
            <div>
              <el-button type="primary" size="small" @click="openCausalNodeDialog">添加节点</el-button>
              <el-button size="small" @click="showCausalEdgeDialog = true">添加边</el-button>
              <el-button size="small" @click="loadCausalGraph">刷新</el-button>
            </div>
          </div>
          <VChart v-if="causalGraph" :option="graphOption" style="height:500px;width:100%;" autoresize />
          <el-empty v-else description="请先加载因果图" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- ============================================ -->
    <!-- Wiki Detail Drawer -->
    <!-- ============================================ -->
    <el-drawer v-model="showWikiDetail" :title="currentWikiEntry?.title || '词条详情'" size="55%" direction="rtl">
      <div v-loading="wikiDetailLoading">
        <template v-if="currentWikiEntry">
          <div class="detail-header">
            <el-tag :type="wikiTypeTag(currentWikiEntry.type)" size="default">{{ wikiTypeLabels[currentWikiEntry.type] || currentWikiEntry.type }}</el-tag>
            <el-tag type="info" size="small" style="margin-left:8px;">{{ currentWikiEntry.category }}</el-tag>
            <el-tag v-if="currentWikiEntry.severity" :type="severityType(currentWikiEntry.severity)" size="small" style="margin-left:8px;">{{ currentWikiEntry.severity }}</el-tag>
            <span class="detail-meta">{{ currentWikiEntry.updated }} | {{ currentWikiEntry.source_file }}</span>
          </div>

          <div v-if="currentWikiEntry.tags?.length" class="detail-section">
            <div class="section-title">标签</div>
            <div class="section-content">
              <el-tag v-for="t in currentWikiEntry.tags" :key="t" size="small" style="margin:0 4px 4px 0;">{{ t }}</el-tag>
            </div>
          </div>

          <div v-if="currentWikiEntry.equipment" class="detail-section">
            <div class="section-title">关联设备</div>
            <div class="section-content">{{ currentWikiEntry.equipment }}</div>
          </div>

          <div class="detail-section">
            <div class="section-title">词条内容</div>
            <div class="section-content wiki-content pre-text">{{ currentWikiEntry.content }}</div>
          </div>

          <div v-if="currentWikiEntry.related_entries?.length" class="detail-section">
            <div class="section-title">关联词条</div>
            <div class="section-content">
              <el-tag v-for="eid in currentWikiEntry.related_entries" :key="eid" size="small" type="info" style="margin:0 4px 4px 0;cursor:pointer;" @click="viewWikiEntry({ id: eid } as any)">{{ eid }}</el-tag>
            </div>
          </div>

          <div style="margin-top:24px;">
            <el-popconfirm title="确定删除此词条？" @confirm="deleteWikiEntryById(currentWikiEntry!.id)">
              <template #reference><el-button type="danger" size="small">删除词条</el-button></template>
            </el-popconfirm>
          </div>
        </template>
      </div>
    </el-drawer>

    <!-- ============================================ -->
    <!-- Wiki Upload Dialog -->
    <!-- ============================================ -->
    <el-dialog v-model="showWikiUploadDialog" title="上传文档到技术知识库" width="560px">
      <div v-if="!wikiUploading">
        <el-upload drag :auto-upload="false" :limit="1" :on-change="(f: any) => handleWikiUpload(f)" accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.md,.txt">
          <el-icon style="font-size:48px;color:#c0c4cc;"><UploadFilled /></el-icon>
          <div style="margin-top:8px;">拖拽文件到此处，或 <em>点击上传</em></div>
          <template #tip>
            <div class="upload-tip">支持 PDF、Word、PowerPoint、Excel、Markdown 文件。上传后 LLM 将自动解析并生成 wiki 词条。</div>
          </template>
        </el-upload>
      </div>
      <div v-else class="upload-progress">
        <el-icon class="is-loading" style="font-size:32px;color:#409eff;"><Loading /></el-icon>
        <div style="margin-top:12px;font-size:14px;color:#606266;">LLM 正在处理文档并生成 wiki 词条...</div>
        <div style="font-size:12px;color:#909399;margin-top:4px;">这可能需要 1-3 分钟，请耐心等待</div>
      </div>
    </el-dialog>

    <!-- ============================================ -->
    <!-- Wiki QA Dialog -->
    <!-- ============================================ -->
    <el-dialog v-model="showWikiQADialog" title="技术知识库问答" width="700px" top="5vh">
      <div class="qa-container">
        <div class="qa-input-bar">
          <el-input v-model="wikiQAQuery" placeholder="输入您的问题，如：压气机叶片积垢怎么处理？" @keyup.enter="handleWikiQA" />
          <el-button type="primary" :loading="wikiQALoading" @click="handleWikiQA" style="margin-left:8px;">提问</el-button>
        </div>

        <div v-if="wikiQAAnswer" class="qa-answer">
          <div class="section-title">回答</div>
          <div class="section-content pre-text">{{ wikiQAAnswer }}</div>
        </div>

        <div v-if="wikiQACitations.length" class="qa-citations">
          <div class="section-title">来源引用</div>
          <div v-for="c in wikiQACitations" :key="c.entry_id" class="citation-item">
            <el-tag :type="wikiTypeTag(c.type)" size="small">{{ wikiTypeLabels[c.type] || c.type }}</el-tag>
            <span class="citation-title" @click="viewWikiEntry({ id: c.entry_id } as any)">{{ c.entry_id }}: {{ c.title }}</span>
            <span class="citation-score">相关度: {{ c.relevance_score }}</span>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- ============================================ -->
    <!-- Detail Drawer: Expert Rule -->
    <!-- ============================================ -->
    <el-drawer v-model="showRuleDetail" :title="currentRule?.name || '规则详情'" size="50%" direction="rtl">
      <template v-if="currentRule">
        <div class="detail-header">
          <el-tag :type="severityType(currentRule.severity)" size="default">{{ currentRule.severity || '中' }}风险</el-tag>
          <span class="detail-meta">置信度 {{ (currentRule.confidence * 100).toFixed(0) }}%</span>
        </div>

        <div class="detail-section">
          <div class="section-title">触发条件</div>
          <div class="section-content highlight-box">{{ currentRule.condition }}</div>
        </div>

        <div class="detail-section">
          <div class="section-title">诊断结论</div>
          <div class="section-content highlight-box">{{ currentRule.conclusion }}</div>
        </div>

        <div v-if="currentRule.related_params?.length" class="detail-section">
          <div class="section-title">关联监测参数</div>
          <div class="section-content">
            <el-tag v-for="p in currentRule.related_params" :key="p" type="info" size="small" style="margin:0 4px 4px 0;">{{ p }}</el-tag>
          </div>
        </div>

        <div v-if="currentRule.recommended_actions" class="detail-section">
          <div class="section-title">建议处置措施</div>
          <div class="section-content pre-text">{{ currentRule.recommended_actions }}</div>
        </div>
      </template>
    </el-drawer>

    <!-- ============================================ -->
    <!-- Add Dialogs -->
    <!-- ============================================ -->

    <!-- Add Model Dialog -->
    <el-dialog v-model="showModelDialog" title="添加小模型接口" width="520px">
      <el-form :model="modelForm" label-width="90px">
        <el-form-item label="模型名称"><el-input v-model="modelForm.name" placeholder="如 预警诊断模型" /></el-form-item>
        <el-form-item label="接口地址"><el-input v-model="modelForm.url" placeholder="如 http://192.168.1.100:8001/api/warning" /></el-form-item>
        <el-form-item label="请求方法"><el-select v-model="modelForm.method"><el-option label="POST" value="POST" /><el-option label="GET" value="GET" /></el-select></el-form-item>
        <el-form-item label="输入参数"><el-input v-model="modelForm.input_params_text" placeholder="逗号分隔，如 unit_id, parameters" /></el-form-item>
        <el-form-item label="输出格式"><el-input v-model="modelForm.output_format" placeholder="如 warning_list" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showModelDialog = false">取消</el-button><el-button type="primary" @click="handleAddModel">确定</el-button></template>
    </el-dialog>

    <!-- Add Expert Rule Dialog -->
    <el-dialog v-model="showRuleDialog" title="添加专家规则" width="620px" top="5vh">
      <el-form :model="ruleForm" label-width="100px" class="add-form">
        <el-form-item label="规则名称" required><el-input v-model="ruleForm.name" placeholder="如 排气温度超限预警规则" /></el-form-item>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="严重度">
              <el-select v-model="ruleForm.severity">
                <el-option label="高" value="高" />
                <el-option label="中" value="中" />
                <el-option label="低" value="低" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="置信度"><el-input-number v-model="ruleForm.confidence" :min="0" :max="1" :step="0.05" :precision="2" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="关联参数"><el-input v-model="ruleForm.related_params_text" placeholder="逗号分隔" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="触发条件" required>
          <el-input v-model="ruleForm.condition" type="textarea" :rows="2" placeholder="如 透平出口温度 T4 > 580°C 且持续 3 个采样周期" />
        </el-form-item>
        <el-form-item label="诊断结论" required>
          <el-input v-model="ruleForm.conclusion" type="textarea" :rows="2" placeholder="如 燃烧器状态异常或燃气品质变化" />
        </el-form-item>
        <el-form-item label="建议措施">
          <el-input v-model="ruleForm.recommended_actions" type="textarea" :rows="4" placeholder="按步骤列出建议的处置措施" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="showRuleDialog = false">取消</el-button><el-button type="primary" @click="handleAddRule">确定</el-button></template>
    </el-dialog>

    <!-- Add Vector KB Dialog -->
    <el-dialog v-model="showVectorDialog" title="接入外部向量知识库" width="520px">
      <el-form :model="vectorForm" label-width="100px">
        <el-form-item label="知识库名称"><el-input v-model="vectorForm.name" placeholder="如 燃机运维知识库" /></el-form-item>
        <el-form-item label="接口地址"><el-input v-model="vectorForm.url" placeholder="如 http://192.168.1.200:8001/api/vectors" /></el-form-item>
        <el-form-item label="嵌入模型">
          <el-select v-model="vectorForm.embedding_model" filterable allow-create>
            <el-option label="bge-large-zh" value="bge-large-zh" />
            <el-option label="bge-small-zh" value="bge-small-zh" />
            <el-option label="text2vec-large-chinese" value="text2vec-large-chinese" />
            <el-option label="m3e-base" value="m3e-base" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="showVectorDialog = false">取消</el-button><el-button type="primary" @click="handleAddVectorSource">确定</el-button></template>
    </el-dialog>

    <!-- Add Causal Node Dialog -->
    <el-dialog v-model="showCausalNodeDialog" title="添加因果图节点" width="500px">
      <el-form :model="causalNodeForm" label-width="100px">
        <el-form-item label="节点名称"><el-input v-model="causalNodeForm.name" placeholder="如 热耗率偏高" /></el-form-item>
        <el-form-item label="节点类型">
          <el-select v-model="causalNodeForm.type">
            <el-option label="征兆 (symptom)" value="symptom" />
            <el-option label="子系统 (subsystem)" value="subsystem" />
            <el-option label="根因 (root_cause)" value="root_cause" />
            <el-option label="触发规则 (trigger_rule)" value="trigger_rule" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联节点">
          <el-select v-model="causalNodeForm.connected_nodes" multiple filterable placeholder="搜索或选择关联节点" style="width: 100%">
            <el-option v-for="opt in nodeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <div class="field-hint">选择后自动创建从本节点到关联节点的边</div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="showCausalNodeDialog = false">取消</el-button><el-button type="primary" @click="handleAddCausalNode">确定</el-button></template>
    </el-dialog>

    <!-- Add Causal Edge Dialog -->
    <el-dialog v-model="showCausalEdgeDialog" title="添加因果图边" width="500px">
      <el-form :model="causalEdgeForm" label-width="100px">
        <el-form-item label="源节点">
          <el-select v-model="causalEdgeForm.source" filterable placeholder="搜索选择源节点" style="width: 100%">
            <el-option v-for="opt in nodeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标节点">
          <el-select v-model="causalEdgeForm.target" filterable placeholder="搜索选择目标节点" style="width: 100%">
            <el-option v-for="opt in nodeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="权重"><el-input-number v-model="causalEdgeForm.weight" :min="0" :max="1" :step="0.1" :precision="1" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showCausalEdgeDialog = false">取消</el-button><el-button type="primary" @click="handleAddCausalEdge">确定</el-button></template>
    </el-dialog>

    <!-- ============================================ -->
    <!-- Raw Files Drawer -->
    <!-- ============================================ -->
    <el-drawer v-model="showRawFilesDrawer" title="原始资料文件" size="55%" direction="rtl">
      <div style="margin-bottom:12px;">
        <el-button size="small" @click="loadRawFiles">刷新</el-button>
      </div>
      <el-table v-loading="rawFilesLoading" :data="rawFiles" stripe size="small">
        <el-table-column prop="name" label="文件名" min-width="260" show-overflow-tooltip />
        <el-table-column label="大小" width="100" align="right">
          <template #default="{ row }">{{ formatFileSize(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="modified" label="修改时间" width="140" />
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewRawFile(row)">{{ row.type === 'md' ? '查看' : '下载' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="rawFiles.length === 0 && !rawFilesLoading" description="暂无原始资料文件" />
    </el-drawer>

    <!-- Raw Content Dialog (md 查看器) -->
    <el-dialog v-model="showRawContentDialog" :title="rawContentTitle" width="700px" top="5vh">
      <div class="pre-text raw-content-view">{{ rawContentText }}</div>
    </el-dialog>

    <!-- Wiki Index Dialog -->
    <el-dialog v-model="showIndexDialog" title="内容索引 (index.md)" width="700px" top="5vh">
      <div class="pre-text raw-content-view">{{ indexContent }}</div>
    </el-dialog>

    <!-- Wiki Log Dialog -->
    <el-dialog v-model="showLogDialog" title="操作日志 (log.md)" width="700px" top="5vh">
      <div class="pre-text raw-content-view">{{ logContent }}</div>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-knowledge { padding-bottom: 24px; }
.knowledge-card { border-radius: 8px; }
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.total-label { font-size: 13px; color: #909399; }
.test-cell { display: flex; align-items: center; gap: 6px; justify-content: center; }
.field-hint { font-size: 11px; color: #c0c4cc; margin-top: 4px; }
.upload-tip { font-size: 12px; color: #909399; margin-top: 4px; }
.add-form :deep(.el-textarea__inner) { font-family: inherit; }

:deep(.clickable-row) { cursor: pointer; }
:deep(.clickable-row:hover) { background-color: #ecf5ff !important; }

.wiki-stats-bar { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.wiki-filter-bar { display: flex; align-items: center; margin-bottom: 12px; }

.upload-progress {
  display: flex; flex-direction: column; align-items: center;
  padding: 48px 0;
}

.qa-container { min-height: 200px; }
.qa-input-bar { display: flex; margin-bottom: 20px; }
.qa-answer { margin-bottom: 20px; }
.qa-citations { border-top: 1px solid #ebeef5; padding-top: 12px; }
.citation-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 0; font-size: 13px;
}
.citation-title { color: #409eff; cursor: pointer; }
.citation-title:hover { text-decoration: underline; }
.citation-score { color: #909399; font-size: 12px; margin-left: auto; }

/* Detail drawer styles */
.detail-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}
.detail-meta {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
}

.detail-section { margin-bottom: 18px; }
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
  padding-left: 8px;
  border-left: 3px solid #409eff;
}
.section-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.8;
  padding-left: 11px;
}
.pre-text { white-space: pre-wrap; word-break: break-word; }
.highlight-box { background: #f5f7fa; border-radius: 4px; padding: 10px 12px; font-weight: 500; }
.wiki-content { max-height: 60vh; overflow-y: auto; }
.raw-content-view { max-height: 65vh; overflow-y: auto; font-size: 13px; line-height: 1.8; color: #303133; }
</style>
