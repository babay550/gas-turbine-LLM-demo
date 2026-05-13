<script setup lang="ts">
import { ref, computed } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getWorkflows,
  saveWorkflow,
  deleteWorkflow,
  getWorkflowTemplates,
  getWorkflowNodeTypes,
  executeWorkflow,
} from '../api'
import type {
  WorkflowDefinition,
  WorkflowNode,
  WorkflowEdge,
  NodeTypeDef,
  ExecutionResult,
} from '../types'

const { onConnect, addEdges, project, vueFlowRef } = useVueFlow()

// ---- State ----
const nodeTypes = ref<NodeTypeDef[]>([])
const workflows = ref<WorkflowDefinition[]>([])
const templates = ref<WorkflowDefinition[]>([])
const selectedNode = ref<WorkflowNode | null>(null)
const editingConfig = ref<Record<string, unknown>>({})
const wfName = ref('新建工作流')
const wfDescription = ref('')
const currentWfId = ref<string | null>(null)
const executing = ref(false)
const execResult = ref<ExecutionResult | null>(null)
const execInput = ref('')
const execDialogVisible = ref(false)

// Vue Flow 内部状态
const nodes = ref<any[]>([])
const edges = ref<any[]>([])

// ---- 节点分类 ----
const categories = computed(() => {
  const map = new Map<string, NodeTypeDef[]>()
  for (const nt of nodeTypes.value) {
    const list = map.get(nt.category) || []
    list.push(nt)
    map.set(nt.category, list)
  }
  return Array.from(map.entries())
})

const categoryIcons: Record<string, string> = {
  '输入': '📥', '分析': '🔍', '知识': '📚', '输出': '📤', '通用': '⚙️',
}

// ---- 初始化 ----
async function init() {
  const [nt, wf, tpl] = await Promise.all([
    getWorkflowNodeTypes(),
    getWorkflows(),
    getWorkflowTemplates(),
  ])
  nodeTypes.value = nt
  workflows.value = wf
  templates.value = tpl
}
init()

// ---- 拖拽添加节点 ----
let nodeIdCounter = 0

function onDragOver(e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
}

function onDrop(e: DragEvent) {
  const type = e.dataTransfer?.getData('application/vueflow')
  if (!type) return
  const def = nodeTypes.value.find(n => n.type === type)
  if (!def) return

  const bounds = vueFlowRef.value?.getBoundingClientRect()
  if (!bounds) return
  const position = project({ x: e.clientX - bounds.left, y: e.clientY - bounds.top })

  const id = `n${++nodeIdCounter}`
  const config: Record<string, unknown> = {}
  for (const f of def.config_fields) {
    if (f.default !== undefined) config[f.key] = f.default
  }

  nodes.value = [
    ...nodes.value,
    {
      id,
      type: 'custom',
      position,
      data: { label: def.label, nodeType: def.type, color: def.color, icon: def.icon, config },
    },
  ]
  selectedNode.value = { id, type: def.type, label: def.label, position, config }
  editingConfig.value = { ...config }
}

// ---- 点击节点选中 ----
function onNodeClick({ node }: { node: any }) {
  const d = node.data
  selectedNode.value = { id: node.id, type: d.nodeType, label: d.label, position: node.position, config: { ...d.config } }
  editingConfig.value = { ...d.config }
}

function onPaneClick() {
  selectedNode.value = null
}

// ---- 连线 ----
onConnect((params) => {
  addEdges([{ ...params, type: 'smoothstep', animated: true }])
})

// ---- 删除 ----
function deleteSelectedNode() {
  if (!selectedNode.value) return
  const id = selectedNode.value.id
  nodes.value = nodes.value.filter(n => n.id !== id)
  edges.value = edges.value.filter(e => e.source !== id && e.target !== id)
  selectedNode.value = null
}

// ---- 保存 ----
async function handleSave() {
  const wfNodes: WorkflowNode[] = nodes.value.map(n => ({
    id: n.id,
    type: n.data.nodeType,
    label: n.data.label,
    position: n.position,
    config: { ...n.data.config },
  }))
  const wfEdges: WorkflowEdge[] = edges.value.map(e => {
    const edge: WorkflowEdge = { id: e.id, source: e.source, target: e.target }
    if (e.sourceHandle) edge.sourceHandle = e.sourceHandle
    return edge
  })

  const res = await saveWorkflow({
    id: currentWfId.value || '',
    name: wfName.value,
    description: wfDescription.value,
    nodes: wfNodes,
    edges: wfEdges,
  })
  currentWfId.value = res.id
  workflows.value = await getWorkflows()
  ElMessage.success('保存成功')
}

// ---- 加载 ----
async function loadWorkflow(wf: WorkflowDefinition) {
  nodes.value = wf.nodes.map(n => ({
    id: n.id,
    type: 'custom',
    position: n.position,
    data: { label: n.label, nodeType: n.type, color: getColor(n.type), icon: getIcon(n.type), config: { ...n.config } },
  }))
  edges.value = wf.edges.map(e => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle || undefined,
    type: 'smoothstep',
    animated: true,
  }))
  wfName.value = wf.name
  wfDescription.value = wf.description
  currentWfId.value = wf.id
  selectedNode.value = null
  nodeIdCounter = wf.nodes.length
}

async function deleteWf(wf: WorkflowDefinition) {
  await ElMessageBox.confirm(`确定删除工作流「${wf.name}」？`, '确认')
  await deleteWorkflow(wf.id)
  workflows.value = await getWorkflows()
  if (currentWfId.value === wf.id) {
    clearCanvas()
  }
  ElMessage.success('已删除')
}

function clearCanvas() {
  nodes.value = []
  edges.value = []
  wfName.value = '新建工作流'
  wfDescription.value = ''
  currentWfId.value = null
  selectedNode.value = null
  execResult.value = null
}

// ---- 执行 ----
async function handleExecute() {
  if (!currentWfId.value && nodes.value.length === 0) {
    ElMessage.warning('请先创建或加载工作流')
    return
  }
  execInput.value = ''
  execResult.value = null
  execDialogVisible.value = true
}

async function doExecute() {
  if (!currentWfId.value) {
    await handleSave()
  }
  if (!currentWfId.value) return
  executing.value = true
  try {
    execResult.value = await executeWorkflow(currentWfId.value, execInput.value)
  } catch (e: any) {
    ElMessage.error('执行失败: ' + (e.message || e))
  } finally {
    executing.value = false
  }
}

// ---- 属性面板更新 ----
function applyConfig() {
  if (!selectedNode.value) return
  const node = nodes.value.find(n => n.id === selectedNode.value!.id)
  if (node) {
    node.data.config = { ...editingConfig.value }
    selectedNode.value.config = { ...editingConfig.value }
  }
}

// ---- Helpers ----
function getColor(type: string): string {
  return nodeTypes.value.find(n => n.type === type)?.color || '#909399'
}

function getIcon(type: string): string {
  return nodeTypes.value.find(n => n.type === type)?.icon || 'block'
}

function getSelectedNodeDef(): NodeTypeDef | undefined {
  if (!selectedNode.value) return undefined
  return nodeTypes.value.find(n => n.type === selectedNode.value!.type)
}

function formatOutput(val: unknown): string {
  if (val === null || val === undefined) return '无'
  if (typeof val === 'object') return JSON.stringify(val, null, 2)
  return String(val)
}
</script>

<template>
  <div class="workflow-editor">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="currentWfId" placeholder="选择工作流" clearable style="width: 200px" @change="(v: string) => { const wf = workflows.find(w => w.id === v); if (wf) loadWorkflow(wf) }">
          <el-option v-for="wf in workflows" :key="wf.id" :label="wf.name" :value="wf.id" />
        </el-select>
        <el-dropdown trigger="click" @command="(cmd: string) => { const t = templates.find(t => t.id === cmd); if (t) loadWorkflow(t) }">
          <el-button>加载模板<el-icon class="el-icon--right"><arrow-down /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="t in templates" :key="t.id" :command="t.id">{{ t.name }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-input v-model="wfName" style="width: 180px" placeholder="工作流名称" />
      </div>
      <div class="toolbar-right">
        <el-button @click="clearCanvas">清空</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
        <el-button type="success" @click="handleExecute" :disabled="nodes.length === 0">执行</el-button>
      </div>
    </div>

    <div class="editor-body">
      <!-- 左侧节点面板 -->
      <div class="node-palette">
        <div v-for="[cat, items] in categories" :key="cat" class="palette-group">
          <div class="palette-group-title">{{ categoryIcons[cat] || '📦' }} {{ cat }}</div>
          <div
            v-for="nt in items"
            :key="nt.type"
            class="palette-item"
            draggable="true"
            @dragstart="(e: DragEvent) => e.dataTransfer?.setData('application/vueflow', nt.type)"
          >
            <span class="palette-dot" :style="{ background: nt.color }"></span>
            <span class="palette-label">{{ nt.label }}</span>
          </div>
        </div>

        <!-- 已保存列表 -->
        <div v-if="workflows.length" class="palette-group" style="margin-top: 16px; border-top: 1px solid #304050; padding-top: 12px;">
          <div class="palette-group-title">📋 已保存</div>
          <div v-for="wf in workflows" :key="wf.id" class="palette-item saved-item" @click="loadWorkflow(wf)">
            <span class="palette-dot" style="background: #409eff"></span>
            <span class="palette-label">{{ wf.name }}</span>
            <el-icon class="del-btn" @click.stop="deleteWf(wf)"><Close /></el-icon>
          </div>
        </div>
      </div>

      <!-- 中间画布 -->
      <div class="canvas-area" @dragover="onDragOver" @drop="onDrop">
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :default-viewport="{ zoom: 0.9, x: 50, y: 50 }"
          :snap-to-grid="true"
          :snap-grid="[15, 15]"
          fit-view-on-init
          @node-click="onNodeClick"
          @pane-click="onPaneClick"
          @nodes-change="() => {}"
          @edges-change="() => {}"
        >
          <template #node-custom="props">
            <div class="wf-node" :style="{ borderColor: props.data.color }">
              <div class="wf-node-header" :style="{ background: props.data.color }">
                <span class="wf-node-title">{{ props.data.label }}</span>
              </div>
              <div class="wf-node-body">
                <Handle type="target" :position="Position.Left" />
                <Handle type="source" :position="Position.Right" />
                <Handle v-if="props.data.nodeType === 'condition_branch'" type="source" :position="Position.Bottom" id="yes" />
                <Handle v-if="props.data.nodeType === 'condition_branch'" type="source" :position="Position.Top" id="no" />
                <span class="wf-node-type">{{ props.data.nodeType }}</span>
              </div>
            </div>
          </template>
          <Background />
          <Controls />
        </VueFlow>
      </div>

      <!-- 右侧属性面板 -->
      <div class="props-panel">
        <template v-if="selectedNode">
          <div class="props-header">
            <span>{{ selectedNode.label }}</span>
            <el-button type="danger" size="small" link @click="deleteSelectedNode">删除</el-button>
          </div>
          <div class="props-type-badge" :style="{ background: getColor(selectedNode.type) }">
            {{ selectedNode.type }}
          </div>

          <el-form label-position="top" size="small" class="props-form">
            <el-form-item label="节点名称">
              <el-input
                :model-value="selectedNode.label"
                @update:model-value="(v: string) => { selectedNode!.label = v; const n = nodes.find(n => n.id === selectedNode!.id); if (n) n.data.label = v }"
              />
            </el-form-item>

            <template v-if="getSelectedNodeDef()">
              <el-form-item v-for="field in getSelectedNodeDef()!.config_fields" :key="field.key" :label="field.label">
                <el-select v-if="field.type === 'select'" v-model="editingConfig[field.key]" @change="applyConfig">
                  <el-option v-for="opt in field.options" :key="opt" :label="opt" :value="opt" />
                </el-select>
                <el-select v-else-if="field.type === 'multiselect'" v-model="editingConfig[field.key]" multiple @change="applyConfig">
                  <el-option v-for="opt in field.options" :key="opt" :label="opt" :value="opt" />
                </el-select>
                <el-input-number v-else-if="field.type === 'number'" v-model="editingConfig[field.key]" @change="applyConfig" />
                <el-input v-else-if="field.type === 'textarea'" type="textarea" :rows="3" v-model="editingConfig[field.key]" @change="applyConfig" />
                <el-input v-else v-model="editingConfig[field.key]" @change="applyConfig" />
              </el-form-item>
            </template>
          </el-form>
        </template>
        <template v-else>
          <div class="props-empty">
            <p>点击画布中的节点查看配置</p>
            <p style="color: #909399; font-size: 12px">从左侧面板拖拽节点到画布</p>
            <p style="color: #909399; font-size: 12px">拖拽节点端口连线</p>
          </div>
        </template>
      </div>
    </div>

    <!-- 执行对话框 -->
    <el-dialog v-model="execDialogVisible" title="执行工作流" width="600px">
      <el-form label-position="top">
        <el-form-item label="用户输入（可选）">
          <el-input v-model="execInput" type="textarea" :rows="2" placeholder="输入问题或参数" />
        </el-form-item>
        <el-button type="primary" :loading="executing" @click="doExecute">
          {{ executing ? '执行中...' : '开始执行' }}
        </el-button>
      </el-form>

      <div v-if="execResult" class="exec-result">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="状态">{{ execResult.status }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ execResult.total_ms }}ms</el-descriptions-item>
        </el-descriptions>

        <div class="exec-logs">
          <h4>执行日志</h4>
          <div v-for="log in execResult.logs" :key="log.node" class="exec-log-item">
            <span :class="['log-status', `log-${log.status}`]">{{ log.status }}</span>
            <span class="log-node">{{ log.label || log.node }}</span>
            <span class="log-time">{{ log.elapsed_ms }}ms</span>
            <span v-if="log.detail" class="log-detail">{{ log.detail }}</span>
          </div>
        </div>

        <div class="exec-output">
          <h4>最终输出</h4>
          <pre>{{ formatOutput(execResult.final_output) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { Close, ArrowDown } from '@element-plus/icons-vue'

export default {
  components: { Close, ArrowDown, Handle },
  data() {
    return { Position }
  },
}
</script>

<style scoped>
.workflow-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #1a1a2e;
  color: #e0e0e0;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #16213e;
  border-bottom: 1px solid #2a3a5c;
  flex-shrink: 0;
  gap: 12px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.editor-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 左侧节点面板 */
.node-palette {
  width: 200px;
  background: #16213e;
  border-right: 1px solid #2a3a5c;
  overflow-y: auto;
  padding: 8px;
  flex-shrink: 0;
}

.palette-group {
  margin-bottom: 12px;
}

.palette-group-title {
  font-size: 12px;
  color: #8892a4;
  margin-bottom: 6px;
  padding-left: 4px;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: grab;
  font-size: 13px;
  transition: background 0.15s;
}

.palette-item:hover {
  background: #2a3a5c;
}

.palette-item.saved-item {
  cursor: pointer;
}

.palette-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.palette-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.del-btn {
  opacity: 0;
  color: #f56c6c;
  cursor: pointer;
  transition: opacity 0.15s;
}

.palette-item:hover .del-btn {
  opacity: 1;
}

/* 中间画布 */
.canvas-area {
  flex: 1;
  height: 100%;
}

/* 自定义节点 */
.wf-node {
  background: #1e293b;
  border: 2px solid #4a5568;
  border-radius: 8px;
  min-width: 140px;
  font-size: 12px;
}

.wf-node-header {
  padding: 4px 10px;
  border-radius: 6px 6px 0 0;
  color: #fff;
  font-weight: 600;
}

.wf-node-body {
  padding: 8px 10px;
  position: relative;
}

.wf-node-type {
  color: #8892a4;
  font-size: 10px;
}

/* 右侧属性面板 */
.props-panel {
  width: 260px;
  background: #16213e;
  border-left: 1px solid #2a3a5c;
  padding: 12px;
  overflow-y: auto;
  flex-shrink: 0;
}

.props-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 8px;
}

.props-type-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 11px;
  color: #fff;
  margin-bottom: 12px;
}

.props-form :deep(.el-form-item__label) {
  color: #a0aec0;
  font-size: 12px;
}

.props-form :deep(.el-input__wrapper),
.props-form :deep(.el-textarea__inner) {
  background: #1a1a2e;
  border-color: #2a3a5c;
  color: #e0e0e0;
}

.props-empty {
  text-align: center;
  padding-top: 60px;
  color: #8892a4;
}

/* 执行结果 */
.exec-result {
  margin-top: 16px;
}

.exec-logs {
  margin-top: 12px;
}

.exec-logs h4, .exec-output h4 {
  margin: 8px 0;
  font-size: 13px;
  color: #606266;
}

.exec-log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.log-status {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}

.log-ok { background: #e6f7e6; color: #52c41a; }
.log-error { background: #fff1f0; color: #f5222d; }
.log-skipped { background: #f0f0f0; color: #999; }

.log-node { flex: 1; }
.log-time { color: #999; }
.log-detail { color: #f56c6c; font-size: 11px; }

.exec-output pre {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
}
</style>
