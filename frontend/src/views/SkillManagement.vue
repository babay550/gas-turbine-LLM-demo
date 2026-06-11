<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getSkills, createSkill, updateSkill, deleteSkill,
  executeSkill, reloadSkills, getSkillTypes,
  importSkillZip, exportSkillUrl,
  listSkillFiles, readSkillFile, writeSkillFile,
} from '../api'
import { loadSkills as syncSkillStore } from '../stores'
import type { SkillDefinition, SkillCreateRequest, SkillTypeOption, SkillFileInfo } from '../types'

const skills = ref<SkillDefinition[]>([])
const skillTypes = ref<SkillTypeOption[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const form = reactive<SkillCreateRequest & { version: string }>({
  name: '', description: '', skill_type: 'http', version: '1.0.0',
  trigger_words: [], inputs: [], outputs: [], execution: {}, enabled: true,
})
const editingName = ref('')
const triggerWordInput = ref('')
const executionJson = ref('{}')
const testDialogVisible = ref(false)
const testSkillName = ref('')
const testArgsJson = ref('{}')
const testResult = ref<unknown>(null)
const testLoading = ref(false)

// ---- ZIP 导入 ----
const importLoading = ref(false)

// ---- 文件编辑器 ----
const fileEditorVisible = ref(false)
const fileEditorSkillName = ref('')
const fileList = ref<SkillFileInfo[]>([])
const fileLoading = ref(false)
const selectedFilePath = ref('')
const fileContent = ref('')
const fileDirty = ref(false)
const fileSaving = ref(false)

const currentTypeSchema = computed(() => {
  const t = skillTypes.value.find(st => st.value === form.skill_type)
  return t?.execution_schema || {}
})

const typeOptions = [
  { value: 'http', label: '🌐 HTTP 接口' },
  { value: 'dataset', label: '📚 知识库检索' },
  { value: 'workflow', label: '🔗 工作流编排' },
  { value: 'python', label: '🐍 Python 脚本' },
  { value: 'shell', label: '🖥️ Shell 脚本' },
  { value: 'db', label: '🗄️ 数据库查询' },
]

onMounted(async () => {
  await Promise.all([fetchSkills(), fetchSkillTypes()])
})

async function fetchSkills() {
  loading.value = true
  try {
    skills.value = await getSkills()
    await syncSkillStore()  // 同步刷新全局 skillStore（供 ChatSidebar @mention 使用）
  }
  catch (e: unknown) { ElMessage.error('加载失败: ' + (e instanceof Error ? e.message : String(e))) }
  finally { loading.value = false }
}

async function fetchSkillTypes() {
  try { const res = await getSkillTypes(); skillTypes.value = res.types } catch { /* non-critical */ }
}

function openCreateDialog() {
  dialogMode.value = 'create'; dialogVisible.value = true; resetForm()
}

function openEditDialog(skill: SkillDefinition) {
  dialogMode.value = 'edit'; editingName.value = skill.name; dialogVisible.value = true
  form.name = skill.name; form.description = skill.description; form.skill_type = skill.skill_type
  form.version = skill.version; form.trigger_words = [...skill.trigger_words]
  form.inputs = [...skill.inputs]; form.outputs = [...skill.outputs]
  form.execution = { ...skill.execution }; form.enabled = skill.enabled
  executionJson.value = JSON.stringify(skill.execution, null, 2)
  triggerWordInput.value = ''
}

function resetForm() {
  form.name = ''; form.description = ''; form.skill_type = 'http'; form.version = '1.0.0'
  form.trigger_words = []; form.inputs = []; form.outputs = []; form.execution = {}
  form.enabled = true; editingName.value = ''; triggerWordInput.value = ''; executionJson.value = '{}'
}

async function handleSubmit() {
  if (!form.name.trim() || !form.description.trim()) { ElMessage.warning('请填写技能名称和描述'); return }
  try { form.execution = JSON.parse(executionJson.value) }
  catch { ElMessage.error('执行配置 JSON 格式错误'); return }
  try {
    if (dialogMode.value === 'create') { await createSkill(form as SkillCreateRequest); ElMessage.success('创建成功') }
    else { await updateSkill(editingName.value, { description: form.description, trigger_words: form.trigger_words, execution: form.execution, enabled: form.enabled }); ElMessage.success('更新成功') }
    dialogVisible.value = false; await fetchSkills()
  } catch (e: unknown) { ElMessage.error('操作失败: ' + (e instanceof Error ? e.message : String(e))) }
}

async function handleDelete(skill: SkillDefinition) {
  try {
    await ElMessageBox.confirm(`确定删除技能 "${skill.name}"？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteSkill(skill.name); ElMessage.success('删除成功'); await fetchSkills()
  } catch { /* cancelled */ }
}

async function handleReload() {
  try { const res = await reloadSkills(); ElMessage.success(`已重载 ${res.count} 个技能`); await fetchSkills() }
  catch (e: unknown) { ElMessage.error('重载失败: ' + (e instanceof Error ? e.message : String(e))) }
}

function openTestDialog(skill: SkillDefinition) {
  testSkillName.value = skill.name; testArgsJson.value = JSON.stringify({ query: '' }, null, 2)
  testResult.value = null; testDialogVisible.value = true
}

async function handleTest() {
  testLoading.value = true; testResult.value = null
  try { const args = JSON.parse(testArgsJson.value); testResult.value = await executeSkill(testSkillName.value, args) }
  catch (e: unknown) { testResult.value = { error: e instanceof Error ? e.message : String(e) } }
  finally { testLoading.value = false }
}

// ---- ZIP 导入 ----
function handleImportClick() {
  const input = document.createElement('input')
  input.type = 'file'; input.accept = '.zip'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    importLoading.value = true
    try {
      const res = await importSkillZip(file)
      ElMessage.success(`导入成功: ${res.name} (${res.type})`)
      await fetchSkills()
    } catch (e: unknown) {
      ElMessage.error('导入失败: ' + (e instanceof Error ? e.message : String(e)))
    } finally { importLoading.value = false }
  }
  input.click()
}

function handleExport(skill: SkillDefinition) {
  const url = exportSkillUrl(skill.name)
  const a = document.createElement('a')
  a.href = url; a.download = `${skill.name}.zip`; a.click()
}

// ---- 文件编辑器 ----
async function openFileEditor(skill: SkillDefinition) {
  fileEditorSkillName.value = skill.name
  selectedFilePath.value = ''
  fileContent.value = ''
  fileDirty.value = false
  fileEditorVisible.value = true
  await loadFileList()
}

async function loadFileList() {
  fileLoading.value = true
  try {
    const res = await listSkillFiles(fileEditorSkillName.value)
    fileList.value = res.files
    // 默认选中 SKILL.md
    const skillMd = res.files.find(f => f.path === 'SKILL.md')
    if (skillMd) await selectFile(skillMd.path)
  } catch (e: unknown) { ElMessage.error('加载文件列表失败') }
  finally { fileLoading.value = false }
}

async function selectFile(path: string) {
  if (fileDirty.value) {
    try {
      await ElMessageBox.confirm('当前文件已修改但未保存，是否放弃修改？', '未保存', { confirmButtonText: '放弃', cancelButtonText: '留在此文件', type: 'warning' })
    } catch { return }
  }
  selectedFilePath.value = path
  fileDirty.value = false
  try {
    const res = await readSkillFile(fileEditorSkillName.value, path)
    fileContent.value = res.binary ? `[二进制文件, ${res.size} 字节]` : (res.content || '')
  } catch { fileContent.value = '' }
}

function onContentChange() {
  fileDirty.value = true
}

async function saveFile() {
  fileSaving.value = true
  try {
    await writeSkillFile(fileEditorSkillName.value, selectedFilePath.value, fileContent.value)
    fileDirty.value = false
    ElMessage.success('保存成功')
    // 如果保存的是 SKILL.md，刷新 skill 列表（元数据可能变了）
    if (selectedFilePath.value === 'SKILL.md') await fetchSkills()
  } catch (e: unknown) { ElMessage.error('保存失败: ' + (e instanceof Error ? e.message : String(e))) }
  finally { fileSaving.value = false }
}

function fileCategory(path: string): string {
  if (path.startsWith('assets/')) return '📦 assets'
  if (path.startsWith('scripts/')) return '📜 scripts'
  if (path.startsWith('references/')) return '📄 references'
  return '📋 根目录'
}

function fileIcon(path: string): string {
  if (path.endsWith('.md')) return '📝'
  if (path.endsWith('.py')) return '🐍'
  if (path.endsWith('.sh') || path.endsWith('.bash')) return '🖥️'
  if (path.endsWith('.yaml') || path.endsWith('.yml')) return '⚙️'
  if (path.endsWith('.json')) return '📋'
  if (path.endsWith('.sql')) return '🗄️'
  if (path.endsWith('.txt')) return '📄'
  return '📄'
}

function addTriggerWord() {
  const w = triggerWordInput.value.trim()
  if (w && !form.trigger_words.includes(w)) { form.trigger_words.push(w); triggerWordInput.value = '' }
}
function removeTriggerWord(i: number) { form.trigger_words.splice(i, 1) }
function addInput() { form.inputs.push({ name: '', type: 'string', description: '', required: true }) }
function removeInput(i: number) { form.inputs.splice(i, 1) }

function skillTypeBadge(type: string) {
  const map: Record<string, { icon: string; color: string }> = {
    http: { icon: '🌐', color: '#409eff' }, dataset: { icon: '📚', color: '#67c23a' },
    workflow: { icon: '🔗', color: '#e6a23c' }, python: { icon: '🐍', color: '#9b59b6' },
    shell: { icon: '🖥️', color: '#606266' }, db: { icon: '🗄️', color: '#f56c6c' },
  }
  return map[type] || { icon: '🔧', color: '#909399' }
}
</script>

<template>
  <div class="skill-management">
    <div class="page-header">
      <h2>技能管理</h2>
      <p class="page-desc">声明式 Agent 技能：HTTP 接口、知识库检索、工作流编排、Python/Shell 脚本、数据库查询。支持 @mention 触发、工作流节点调用和 LLM 自动识别。</p>
    </div>
    <div class="toolbar">
      <el-button type="primary" @click="openCreateDialog">+ 创建技能</el-button>
      <el-button @click="handleImportClick" :loading="importLoading">📦 导入 ZIP</el-button>
      <el-button @click="handleReload" :loading="loading">🔄 重新加载</el-button>
      <span class="toolbar-info">已注册 {{ skills.length }} 个技能</span>
    </div>

    <el-table :data="skills" stripe v-loading="loading" style="width: 100%">
      <el-table-column prop="name" label="名称" width="150">
        <template #default="{ row }"><span class="skill-name">{{ row.name }}</span></template>
      </el-table-column>
      <el-table-column label="类型" width="120">
        <template #default="{ row }">
          <el-tag :color="skillTypeBadge(row.skill_type).color" effect="dark" size="small" style="border:none;">
            {{ skillTypeBadge(row.skill_type).icon }} {{ row.skill_type.toUpperCase() }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
      <el-table-column label="触发词" width="160">
        <template #default="{ row }">
          <el-tag v-for="tw in (row.trigger_words || []).slice(0, 3)" :key="tw" size="small" style="margin:2px">{{ tw }}</el-tag>
          <span v-if="(row.trigger_words || []).length > 3" class="more-tag">+{{ row.trigger_words.length - 3 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="70" align="center">
        <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '禁用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openFileEditor(row)">📁 文件</el-button>
          <el-button size="small" @click="handleExport(row)">💾 导出</el-button>
          <el-button size="small" @click="openTestDialog(row)">测试</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="!loading && skills.length === 0" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><MagicStick /></el-icon>
      <p>暂无注册技能</p>
      <p class="empty-hint">点击"创建技能"或"导入 ZIP"添加技能</p>
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '创建技能' : `编辑: ${editingName}`" width="680px" @close="resetForm">
      <el-form label-width="100px" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="技能名称" required><el-input v-model="form.name" placeholder="如: weather_api" :disabled="dialogMode === 'edit'" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="技能类型" required>
              <el-select v-model="form.skill_type" style="width:100%" :disabled="dialogMode === 'edit'">
                <el-option v-for="opt in typeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述" required><el-input v-model="form.description" type="textarea" :rows="2" placeholder="简要描述技能用途" /></el-form-item>
        <el-form-item label="触发词">
          <div class="trigger-words-editor">
            <div class="tw-tags"><el-tag v-for="(tw, i) in form.trigger_words" :key="i" closable @close="removeTriggerWord(i)" style="margin:2px">{{ tw }}</el-tag></div>
            <div class="tw-input-row"><el-input v-model="triggerWordInput" placeholder="输入触发词" size="small" @keydown.enter.prevent="addTriggerWord" style="width:200px" /><el-button size="small" @click="addTriggerWord">添加</el-button></div>
          </div>
        </el-form-item>
        <el-form-item label="执行配置 (JSON)">
          <el-input v-model="executionJson" type="textarea" :rows="6" placeholder='如: { "url": "https://api.example.com", "method": "GET" }' />
          <div class="schema-hint"><strong>配置说明:</strong><span v-for="(desc, key) in currentTypeSchema" :key="key" class="schema-item">{{ key }}: {{ desc }}</span></div>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :disabled="!form.name.trim()">{{ dialogMode === 'create' ? '创建' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <!-- Test Dialog -->
    <el-dialog v-model="testDialogVisible" :title="`测试: ${testSkillName}`" width="600px">
      <el-form label-position="top"><el-form-item label="输入参数 (JSON)"><el-input v-model="testArgsJson" type="textarea" :rows="4" /></el-form-item></el-form>
      <div v-if="testResult" class="test-result">
        <div class="test-result-header">执行结果</div>
        <pre class="test-result-json">{{ JSON.stringify(testResult, null, 2) }}</pre>
      </div>
      <template #footer>
        <el-button @click="testDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleTest" :loading="testLoading">执行测试</el-button>
      </template>
    </el-dialog>

    <!-- File Editor Dialog -->
    <el-dialog v-model="fileEditorVisible" :title="`文件管理: ${fileEditorSkillName}`" width="900px" top="5vh">
      <div class="file-editor-layout">
        <!-- Left: file tree -->
        <div class="file-tree-panel">
          <div class="file-tree-header">文件列表 ({{ fileList.length }})</div>
          <div class="file-tree-list" v-loading="fileLoading">
            <div
              v-for="f in fileList" :key="f.path"
              :class="['file-tree-item', f.path === selectedFilePath ? 'file-tree-active' : '']"
              @click="selectFile(f.path)"
            >
              <span class="file-icon">{{ fileIcon(f.path) }}</span>
              <div class="file-meta">
                <span class="file-path">{{ f.path }}</span>
                <span class="file-size">{{ f.size > 1024 ? (f.size / 1024).toFixed(1) + ' KB' : f.size + ' B' }}</span>
              </div>
            </div>
            <div v-if="fileList.length === 0 && !fileLoading" class="file-tree-empty">无文件</div>
          </div>
        </div>
        <!-- Right: code editor -->
        <div class="file-content-panel">
          <div class="file-content-header">
            <span v-if="selectedFilePath" class="file-current">
              {{ fileIcon(selectedFilePath) }} {{ selectedFilePath }}
              <el-tag v-if="fileDirty" type="warning" size="small" style="margin-left:6px">已修改</el-tag>
            </span>
            <span v-else class="file-placeholder">选择左侧文件查看/编辑</span>
            <el-button v-if="selectedFilePath" type="primary" size="small" @click="saveFile" :loading="fileSaving" :disabled="!fileDirty">
              保存
            </el-button>
          </div>
          <el-input
            v-if="selectedFilePath"
            v-model="fileContent"
            type="textarea"
            :rows="22"
            @input="onContentChange"
            class="file-editor-textarea"
          />
          <div v-else class="file-editor-empty">
            <p>点击左侧文件开始编辑</p>
            <p class="file-editor-hint">
              📝 SKILL.md — 技能元信息 &nbsp;|&nbsp;
              📦 assets/ — 预加载资源 &nbsp;|&nbsp;
              📜 scripts/ — 执行脚本 &nbsp;|&nbsp;
              📄 references/ — 按需加载资源
            </p>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script lang="ts">
import { MagicStick } from '@element-plus/icons-vue'
export default { components: { MagicStick } }
</script>

<style scoped>
.skill-management { padding: 20px; height: 100%; overflow-y: auto; }
.page-header { margin-bottom: 16px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; color: #303133; }
.page-desc { font-size: 13px; color: #909399; margin: 0; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.toolbar-info { margin-left: auto; font-size: 13px; color: #909399; }
.skill-name { font-weight: 600; color: #303133; font-family: 'Courier New', monospace; }
.more-tag { font-size: 11px; color: #909399; margin-left: 4px; }
.empty-state { display: flex; flex-direction: column; align-items: center; padding: 60px 0; color: #c0c4cc; gap: 8px; }
.empty-state p { margin: 0; font-size: 14px; }
.empty-hint { font-size: 12px !important; }
.trigger-words-editor { width: 100%; }
.tw-tags { margin-bottom: 6px; }
.tw-input-row { display: flex; gap: 6px; }
.param-row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
.schema-hint { margin-top: 6px; font-size: 11px; color: #909399; }
.schema-item { display: inline-block; margin-left: 8px; padding: 1px 4px; background: #f5f7fa; border-radius: 3px; }
.test-result { margin-top: 12px; border: 1px solid #e4e7ed; border-radius: 6px; overflow: hidden; }
.test-result-header { padding: 4px 10px; font-size: 12px; font-weight: 600; color: #606266; background: #f5f7fa; border-bottom: 1px solid #e4e7ed; }
.test-result-json { margin: 0; padding: 10px; font-size: 12px; line-height: 1.5; max-height: 300px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; background: #fafafa; }

/* File Editor Layout */
.file-editor-layout { display: flex; gap: 0; height: 520px; border: 1px solid #e4e7ed; border-radius: 6px; overflow: hidden; }
.file-tree-panel { width: 240px; border-right: 1px solid #e4e7ed; display: flex; flex-direction: column; flex-shrink: 0; background: #fafafa; }
.file-tree-header { padding: 8px 12px; font-size: 12px; font-weight: 600; color: #606266; border-bottom: 1px solid #ebeef5; background: #f5f7fa; }
.file-tree-list { flex: 1; overflow-y: auto; }
.file-tree-item { display: flex; align-items: center; gap: 6px; padding: 6px 12px; cursor: pointer; transition: background .15s; border-bottom: 1px solid #f0f2f5; }
.file-tree-item:hover { background: #ecf5ff; }
.file-tree-active { background: #ecf5ff; border-left: 3px solid #409eff; }
.file-icon { font-size: 14px; flex-shrink: 0; }
.file-meta { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.file-path { font-size: 11px; color: #303133; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-family: 'Courier New', monospace; }
.file-size { font-size: 10px; color: #909399; }
.file-tree-empty { padding: 20px; text-align: center; color: #c0c4cc; font-size: 12px; }

.file-content-panel { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.file-content-header { display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; border-bottom: 1px solid #ebeef5; background: #f5f7fa; flex-shrink: 0; }
.file-current { font-size: 12px; font-weight: 600; color: #303133; font-family: 'Courier New', monospace; }
.file-placeholder { font-size: 12px; color: #909399; }
.file-editor-textarea { flex: 1; }
.file-editor-textarea :deep(textarea) { font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; line-height: 1.5; border: none; border-radius: 0; }
.file-editor-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #c0c4cc; gap: 8px; }
.file-editor-empty p { margin: 0; font-size: 14px; }
.file-editor-hint { font-size: 12px !important; color: #c0c4cc; }
</style>
