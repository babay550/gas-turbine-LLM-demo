<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GraphChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import * as api from '../api'
import type { ModelEntry, MaintenanceKnowledge, ExpertRule, CausalGraph, CausalNode, VectorKBSource, ModelTestResult } from '../types'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, GraphChart, TitleComponent, TooltipComponent, LegendComponent])

const activeTab = ref('models')
const loading = ref(false)

const models = ref<ModelEntry[]>([])
const modelTotal = ref(0)
const modelTestResults = ref<Record<string, ModelTestResult>>({})
const modelTesting = ref<Record<string, boolean>>({})

const knowledgeSubTab = ref('maintenance')
const maintenanceItems = ref<MaintenanceKnowledge[]>([])
const maintenanceTotal = ref(0)
const expertRules = ref<ExpertRule[]>([])
const expertRulesTotal = ref(0)
const causalGraph = ref<CausalGraph | null>(null)

const vectorSources = ref<VectorKBSource[]>([])
const vectorTotal = ref(0)

// --- Detail drawers ---
const showMaintenanceDetail = ref(false)
const currentMaintenance = ref<MaintenanceKnowledge | null>(null)
const showRuleDetail = ref(false)
const currentRule = ref<ExpertRule | null>(null)

// --- Add forms ---
const showModelDialog = ref(false)
const modelForm = reactive({ name: '', url: '', method: 'POST', input_params_text: '', output_format: '' })

const showMaintenanceDialog = ref(false)
const maintenanceForm = reactive({
  title: '', category: '', type: '', equipment: '', severity: '中',
  keywords_text: '', symptoms: '', analysis: '', solution: '', prevention: '',
  file: null as File | null,
})

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

// --- Causal Graph Chart ---
const graphOption = computed(() => {
  if (!causalGraph.value) return {}
  const { nodes, edges } = causalGraph.value
  const colorMap: Record<string, string> = { symptom: '#e6a23c', subsystem: '#409eff', root_cause: '#f56c6c' }
  const categoryIndex: Record<string, number> = { symptom: 0, subsystem: 1, root_cause: 2 }
  const categories = [
    { name: '征兆', itemStyle: { color: '#e6a23c' } },
    { name: '子系统', itemStyle: { color: '#409eff' } },
    { name: '根因', itemStyle: { color: '#f56c6c' } },
  ]
  return {
    tooltip: {},
    legend: { data: categories.map(c => c.name), top: 0, selectedMode: false },
    series: [{
      type: 'graph', layout: 'force',
      data: nodes.map((n: CausalNode) => ({
        id: n.id, name: `${n.name}\n(${n.id})`,
        symbolSize: n.type === 'root_cause' ? 50 : n.type === 'subsystem' ? 40 : 30,
        itemStyle: { color: colorMap[n.type] ?? '#909399' },
        category: categoryIndex[n.type] ?? 0,
        label: { show: true, fontSize: 11 },
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

async function loadMaintenanceKnowledge() {
  loading.value = true
  try { const r = await api.getMaintenanceKnowledge(); maintenanceItems.value = r.items; maintenanceTotal.value = r.total }
  catch (e: unknown) { ElMessage.error(e instanceof Error ? e.message : String(e)) }
  finally { loading.value = false }
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
    if (maintenanceItems.value.length === 0) await loadMaintenanceKnowledge()
    if (expertRules.value.length === 0) await loadExpertRules()
  }
  else if (tab === 'causal' && !causalGraph.value) await loadCausalGraph()
  else if (tab === 'vector' && vectorSources.value.length === 0) await loadVectorSources()
}

function handleKnowledgeSubTabChange() {
  if (knowledgeSubTab.value === 'maintenance' && maintenanceItems.value.length === 0) loadMaintenanceKnowledge()
  else if (knowledgeSubTab.value === 'rules' && expertRules.value.length === 0) loadExpertRules()
}

function statusType(status: string) { return status === 'online' ? 'success' : 'danger' }
function vectorStatusType(status: string) { return status === 'connected' ? 'success' : 'danger' }

// --- Detail view handlers ---
function viewMaintenanceDetail(item: MaintenanceKnowledge) {
  currentMaintenance.value = item
  showMaintenanceDetail.value = true
}

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

function handleAddMaintenance() {
  const newItem: MaintenanceKnowledge = {
    id: `K${String(maintenanceItems.value.length + 1).padStart(3, '0')}`,
    title: maintenanceForm.title + (maintenanceForm.file ? ` (附件: ${maintenanceForm.file.name})` : ''),
    category: maintenanceForm.category,
    type: maintenanceForm.type,
    equipment: maintenanceForm.equipment,
    severity: maintenanceForm.severity,
    keywords: maintenanceForm.keywords_text.split(',').map(s => s.trim()).filter(Boolean),
    symptoms: maintenanceForm.symptoms,
    analysis: maintenanceForm.analysis,
    solution: maintenanceForm.solution,
    prevention: maintenanceForm.prevention,
    updated: new Date().toISOString().slice(0, 10),
    source: maintenanceForm.file ? 'upload' : 'manual',
    content_type: maintenanceForm.file ? 'document' : 'text',
  }
  maintenanceItems.value.push(newItem); maintenanceTotal.value = maintenanceItems.value.length
  showMaintenanceDialog.value = false
  Object.assign(maintenanceForm, { title: '', category: '', type: '', equipment: '', severity: '中', keywords_text: '', symptoms: '', analysis: '', solution: '', prevention: '', file: null })
  ElMessage.success('知识条目已添加')
}

function handleFileChange(uploadFile: any) {
  maintenanceForm.file = uploadFile.raw || null
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

function sourceLabel(source?: string) {
  const map: Record<string, string> = { manual: '手动录入', upload: '文件上传', vector: '向量检索' }
  return map[source || 'manual'] || '手动录入'
}

function sourceTagType(source?: string) {
  const map: Record<string, string> = { manual: '', upload: 'warning', vector: 'success' }
  return map[source || 'manual'] || ''
}

function contentTypeLabel(ct?: string) {
  const map: Record<string, string> = { text: '文本', document: '文档', image: '图像' }
  return map[ct || 'text'] || '文本'
}

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

            <!-- Sub-tab: 检维修知识 -->
            <el-tab-pane label="检维修知识" name="maintenance">
              <div class="tab-header">
                <span class="total-label">共 {{ maintenanceTotal }} 条知识</span>
                <div>
                  <el-button type="primary" size="small" @click="showMaintenanceDialog = true">添加知识</el-button>
                  <el-button size="small" @click="loadMaintenanceKnowledge">刷新</el-button>
                </div>
              </div>
              <el-table v-loading="loading" :data="maintenanceItems" stripe size="small" row-class-name="clickable-row" @row-click="viewMaintenanceDetail">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
                <el-table-column prop="category" label="分类" width="90" />
                <el-table-column prop="type" label="类型" width="90" />
                <el-table-column label="严重度" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag :type="severityType(row.severity)" size="small">{{ row.severity || '中' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="关键词" min-width="180">
                  <template #default="{ row }">
                    <el-tag v-for="kw in (row.keywords as string[]).slice(0, 4)" :key="kw" size="small" style="margin:0 2px 2px 0;">{{ kw }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="来源" width="100" align="center">
                  <template #default="{ row }">
                    <el-tag :type="sourceTagType(row.source)" size="small">{{ sourceLabel(row.source) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="updated" label="更新时间" width="120" />
                <el-table-column label="操作" width="70" align="center">
                  <template #default="{ row }">
                    <el-button type="primary" link size="small" @click.stop="viewMaintenanceDetail(row)">详情</el-button>
                  </template>
                </el-table-column>
              </el-table>
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
                <el-table-column prop="name" label="规则名称" min-width="160" />
                <el-table-column prop="condition" label="触发条件" min-width="220" show-overflow-tooltip />
                <el-table-column prop="conclusion" label="诊断结论" min-width="200" show-overflow-tooltip />
                <el-table-column label="严重度" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag :type="severityType(row.severity)" size="small">{{ row.severity || '中' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="置信度" width="80" align="center">
                  <template #default="{ row }">
                    <span :style="{ color: row.confidence >= 0.85 ? '#67c23a' : '#e6a23c', fontWeight: 600 }">{{ (row.confidence * 100).toFixed(0) }}%</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="70" align="center">
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
    <!-- Detail Drawer: Maintenance Knowledge -->
    <!-- ============================================ -->
    <el-drawer v-model="showMaintenanceDetail" :title="currentMaintenance?.title || '知识详情'" size="55%" direction="rtl">
      <template v-if="currentMaintenance">
        <div class="detail-header">
          <el-tag :type="severityType(currentMaintenance.severity)" size="default">{{ currentMaintenance.severity || '中' }}风险</el-tag>
          <el-tag type="info" size="small" style="margin-left:8px;">{{ currentMaintenance.category }}</el-tag>
          <el-tag size="small" style="margin-left:8px;">{{ currentMaintenance.type }}</el-tag>
          <span class="detail-meta">{{ currentMaintenance.updated }} | {{ sourceLabel(currentMaintenance.source) }}</span>
        </div>

        <div v-if="currentMaintenance.equipment" class="detail-section">
          <div class="section-title">适用设备</div>
          <div class="section-content">{{ currentMaintenance.equipment }}</div>
        </div>

        <div v-if="currentMaintenance.keywords?.length" class="detail-section">
          <div class="section-title">关键词</div>
          <div class="section-content">
            <el-tag v-for="kw in currentMaintenance.keywords" :key="kw" size="small" style="margin:0 4px 4px 0;">{{ kw }}</el-tag>
          </div>
        </div>

        <div v-if="currentMaintenance.symptoms" class="detail-section">
          <div class="section-title">故障现象</div>
          <div class="section-content pre-text">{{ currentMaintenance.symptoms }}</div>
        </div>

        <div v-if="currentMaintenance.analysis" class="detail-section">
          <div class="section-title">原因分析</div>
          <div class="section-content pre-text">{{ currentMaintenance.analysis }}</div>
        </div>

        <div v-if="currentMaintenance.solution" class="detail-section">
          <div class="section-title">处理方案</div>
          <div class="section-content pre-text">{{ currentMaintenance.solution }}</div>
        </div>

        <div v-if="currentMaintenance.prevention" class="detail-section">
          <div class="section-title">预防措施</div>
          <div class="section-content pre-text">{{ currentMaintenance.prevention }}</div>
        </div>
      </template>
    </el-drawer>

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

    <!-- Add Maintenance Knowledge Dialog — full form -->
    <el-dialog v-model="showMaintenanceDialog" title="添加检维修知识" width="680px" top="5vh">
      <el-form :model="maintenanceForm" label-width="90px" class="add-form">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="标题" required><el-input v-model="maintenanceForm.title" placeholder="如 压气机叶片积垢清洗规程" /></el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="分类" required>
              <el-select v-model="maintenanceForm.category" placeholder="选择分类">
                <el-option label="压气机" value="压气机" />
                <el-option label="燃烧室" value="燃烧室" />
                <el-option label="透平" value="透平" />
                <el-option label="发电机" value="发电机" />
                <el-option label="余热锅炉" value="余热锅炉" />
                <el-option label="控制系统" value="控制系统" />
                <el-option label="整机" value="整机" />
                <el-option label="辅助系统" value="辅助系统" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="类型" required>
              <el-select v-model="maintenanceForm.type" placeholder="选择类型">
                <el-option label="检修规程" value="检修规程" />
                <el-option label="故障诊断" value="故障诊断" />
                <el-option label="处理案例" value="处理案例" />
                <el-option label="检测标准" value="检测标准" />
                <el-option label="预防指南" value="预防指南" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="适用设备"><el-input v-model="maintenanceForm.equipment" placeholder="如 压气机叶片（静叶/动叶）" /></el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="严重度">
              <el-select v-model="maintenanceForm.severity">
                <el-option label="高" value="高" />
                <el-option label="中" value="中" />
                <el-option label="低" value="低" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="关键词"><el-input v-model="maintenanceForm.keywords_text" placeholder="逗号分隔" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="故障现象">
          <el-input v-model="maintenanceForm.symptoms" type="textarea" :rows="3" placeholder="描述故障的主要表现和可观测到的异常指标" />
        </el-form-item>
        <el-form-item label="原因分析">
          <el-input v-model="maintenanceForm.analysis" type="textarea" :rows="4" placeholder="分析可能的故障原因及其物理机制" />
        </el-form-item>
        <el-form-item label="处理方案">
          <el-input v-model="maintenanceForm.solution" type="textarea" :rows="4" placeholder="按步骤描述处理/检修方案" />
        </el-form-item>
        <el-form-item label="预防措施">
          <el-input v-model="maintenanceForm.prevention" type="textarea" :rows="3" placeholder="描述预防同类故障再次发生的措施" />
        </el-form-item>
        <el-form-item label="附件">
          <el-upload :auto-upload="false" :limit="1" :on-change="handleFileChange" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.txt">
            <template #trigger><el-button size="small">选择文件</el-button></template>
            <template #tip><div class="upload-tip">支持 PDF、Word、图片、文本文件</div></template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="showMaintenanceDialog = false">取消</el-button><el-button type="primary" @click="handleAddMaintenance">确定</el-button></template>
    </el-dialog>

    <!-- Add Expert Rule Dialog — full form -->
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

.detail-section {
  margin-bottom: 18px;
}
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
.pre-text {
  white-space: pre-wrap;
  word-break: break-word;
}
.highlight-box {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 10px 12px;
  font-weight: 500;
}
</style>
