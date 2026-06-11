<script setup lang="ts">
import { ref, nextTick, watch, onMounted, computed } from 'vue'
import { chatStore, skillStore, sendChatMessage, loadSkills, createSession, switchSession, deleteSession, loadSessions } from '../../stores'
import type { DebugLogEntry, SkillDefinition } from '../../types'
import { renderMarkdown } from '../../utils/markdown'

const inputText = ref('')
const messageListRef = ref<HTMLElement>()
const showDebug = ref<Record<number, boolean>>({})
const debugMode = ref(false)
const showHistory = ref(false)

// ---- @mention 状态 ----
const mentionQuery = ref('')
const showMentionPopup = ref(false)
const mentionStartIndex = ref(-1)
const selectedMentionIndex = ref(0)
const selectedSkill = ref<string | null>(null)

const filteredSkills = computed(() => {
  if (!mentionQuery.value) return skillStore.skills
  const q = mentionQuery.value.toLowerCase()
  return skillStore.skills.filter(s =>
    s.name.toLowerCase().includes(q) ||
    s.description.toLowerCase().includes(q) ||
    s.trigger_words.some(tw => tw.toLowerCase().includes(q))
  )
})

// Resizable width
const MIN_WIDTH = 280
const MAX_WIDTH = 700
const DEFAULT_WIDTH = 360
const sidebarWidth = ref(DEFAULT_WIDTH)
const isResizing = ref(false)

function startResize(e: MouseEvent) {
  e.preventDefault()
  isResizing.value = true
  const startX = e.clientX
  const startW = sidebarWidth.value

  function onMouseMove(ev: MouseEvent) {
    const delta = startX - ev.clientX // drag left → wider
    const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startW + delta))
    sidebarWidth.value = next
  }

  function onMouseUp() {
    isResizing.value = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

const props = defineProps<{
  visible: boolean
}>()

onMounted(() => {
  loadSessions()
  loadSkills()
})

function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  const hint = selectedSkill.value
  selectedSkill.value = null
  showMentionPopup.value = false
  sendChatMessage(text, hint || undefined)
}

async function handleNewSession() {
  await createSession()
}

async function handleSwitchSession(id: string) {
  showHistory.value = false
  await switchSession(id)
}

async function handleDeleteSession(id: string) {
  await deleteSession(id)
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return time
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) + ' ' + time
}

function handleKeydown(e: KeyboardEvent) {
  if (showMentionPopup.value) {
    if (e.key === 'ArrowDown') { e.preventDefault(); selectedMentionIndex.value = Math.min(selectedMentionIndex.value + 1, filteredSkills.value.length - 1); return }
    if (e.key === 'ArrowUp') { e.preventDefault(); selectedMentionIndex.value = Math.max(selectedMentionIndex.value - 1, 0); return }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (filteredSkills.value.length > 0) selectSkill(filteredSkills.value[selectedMentionIndex.value]); return }
    if (e.key === 'Escape') { e.preventDefault(); showMentionPopup.value = false; return }
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// ---- @mention 输入检测 ----
watch(inputText, (text) => {
  if (!text) { showMentionPopup.value = false; return }
  const lastAt = text.lastIndexOf('@', text.length - 1)
  if (lastAt >= 0) {
    const afterAt = text.substring(lastAt + 1)
    if (!afterAt.includes(' ') && !afterAt.includes('\n')) {
      mentionQuery.value = afterAt
      mentionStartIndex.value = lastAt
      showMentionPopup.value = true
      selectedMentionIndex.value = 0
      return
    }
  }
  showMentionPopup.value = false
})

function selectSkill(skill: SkillDefinition) {
  const before = inputText.value.substring(0, mentionStartIndex.value)
  const after = inputText.value.substring(mentionStartIndex.value + 1 + mentionQuery.value.length)
  inputText.value = before + '@' + skill.name + ' ' + after
  selectedSkill.value = skill.name
  showMentionPopup.value = false
}

function skillTypeIcon(type: string): string {
  const map: Record<string, string> = { http: '🌐', dataset: '📚', workflow: '🔗', python: '🐍', shell: '🖥️', db: '🗄️' }
  return map[type] || '🔧'
}

function toggleDebug(idx: number) {
  showDebug.value[idx] = !showDebug.value[idx]
}

function citationIcon(tool: string): string {
  const map: Record<string, string> = {
    realtime_monitoring: '📊',
    efficiency_analysis: '⚡',
    loss_analysis: '📉',
    benchmark_analysis: '📋',
    efficiency_trend: '📈',
    warning_query: '⚠️',
  }
  return map[tool] || '🔧'
}

function stepLabel(step: string): string {
  const map: Record<string, string> = {
    init: '初始化',
    llm_call_1: 'LLM 意图识别',
    tool_exec: '工具执行',
    llm_call_2: 'LLM 结果总结',
    done: '完成',
    dispatch: '调度',
  }
  return map[step] || step
}

function statusColor(status: string): string {
  if (status === 'ok') return '#67c23a'
  if (status === 'error') return '#f56c6c'
  if (status === 'skip') return '#909399'
  if (status === 'timeout') return '#e6a23c'
  return '#909399'
}

function formatLogDetail(entry: DebugLogEntry): string {
  const parts: string[] = []
  if (entry.model) parts.push(`模型: ${entry.model}`)
  if (entry.provider) parts.push(`接入: ${entry.provider}`)
  if (entry.tools_registered) parts.push(`注册工具: ${entry.tools_registered.join(', ')}`)
  if (entry.tool_calls_requested?.length) parts.push(`请求调用: ${entry.tool_calls_requested.join(', ')}`)
  if (entry.tool) parts.push(`工具: ${entry.tool}`)
  if (entry.elapsed_ms !== undefined) parts.push(`${entry.elapsed_ms}ms`)
  if (entry.result_size !== undefined) parts.push(`数据量: ${entry.result_size} 字符`)
  if (entry.truncated) parts.push('已截断')
  if (entry.total_ms !== undefined) parts.push(`总耗时: ${entry.total_ms}ms`)
  if (entry.tools_used !== undefined) parts.push(`调用 ${entry.tools_used} 个工具`)
  if (entry.answer_length !== undefined) parts.push(`回复长度: ${entry.answer_length}`)
  if (entry.detail) parts.push(entry.detail)
  if (entry.direct_answer) parts.push('直接回答（未调用工具）')
  return parts.join(' | ')
}

watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  }
)
</script>

<template>
  <transition name="chat-slide">
    <div v-if="visible" class="chat-sidebar" :style="{ width: sidebarWidth + 'px' }">
      <!-- Drag handle on the left edge -->
      <div
        class="resize-handle"
        :class="{ active: isResizing }"
        @mousedown="startResize"
      />
      <div class="chat-header">
        <span class="chat-title">智能助手</span>
        <el-tag size="small" type="success" style="margin-left:8px;">GLM-5</el-tag>
        <el-switch
          v-model="debugMode"
          size="small"
          active-text="调试"
          inactive-text=""
          style="margin-left:auto;"
        />
      </div>
      <div class="chat-toolbar">
        <el-button size="small" @click="handleNewSession" :disabled="chatStore.loading">
          + 新会话
        </el-button>
        <el-popover
          placement="bottom-end"
          :width="280"
          trigger="click"
          v-model:visible="showHistory"
        >
          <template #reference>
            <el-button size="small" :disabled="chatStore.loading">
              历史会话 ({{ chatStore.sessions.length }})
            </el-button>
          </template>
          <div class="session-list">
            <div v-if="chatStore.sessions.length === 0" class="session-empty">暂无历史会话</div>
            <div
              v-for="s in chatStore.sessions"
              :key="s.id"
              :class="['session-item', s.id === chatStore.currentSessionId ? 'session-active' : '']"
              @click="handleSwitchSession(s.id)"
            >
              <div class="session-info">
                <div class="session-title">{{ s.title }}</div>
                <div class="session-meta">{{ formatTime(s.updated) }} · {{ s.message_count }}条</div>
              </div>
              <el-popconfirm title="确定删除此会话？" @confirm="handleDeleteSession(s.id)" confirm-button-text="删除" cancel-button-text="取消">
                <template #reference>
                  <el-button size="small" text type="danger" @click.stop class="session-del">×</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </el-popover>
      </div>
      <div ref="messageListRef" class="chat-messages">
        <div v-if="chatStore.messages.length === 0" class="chat-empty">
          <el-icon :size="40" color="#c0c4cc"><ChatDotRound /></el-icon>
          <p>输入问题开始对话</p>
          <div class="empty-hints">
            <span>试试: "当前机组运行状态"</span>
            <span>试试: "分析能效状况"</span>
            <span>试试: "有什么预警"</span>
          </div>
        </div>
        <div
          v-for="(msg, idx) in chatStore.messages"
          :key="idx"
          :class="['chat-bubble', msg.role === 'user' ? 'bubble-user' : 'bubble-assistant']"
        >
          <div class="bubble-role">{{ msg.role === 'user' ? '我' : '助手' }}</div>
          <div v-if="msg.role === 'user'" class="bubble-content">{{ msg.content }}</div>
          <div v-else class="bubble-content markdown-body" v-html="renderMarkdown(msg.content)"></div>

          <!-- Citations -->
          <div v-if="msg.citations && msg.citations.length > 0" class="bubble-citations">
            <div class="cit-header">数据来源（{{ msg.citations.length }} 个数据源）</div>
            <div v-for="(cit, ci) in msg.citations" :key="ci" class="cit-item">
              <span class="cit-icon">{{ citationIcon(cit.tool) }}</span>
              <div class="cit-body">
                <span class="cit-label">{{ cit.label }}</span>
                <span class="cit-summary">{{ cit.summary }}</span>
              </div>
            </div>
          </div>

          <!-- Debug logs (only in debug mode) -->
          <div v-if="debugMode && msg.debug_logs && msg.debug_logs.length > 0" class="bubble-debug">
            <div class="debug-toggle" @click="toggleDebug(idx)">
              <span>调试日志（{{ msg.debug_logs.length }} 步）</span>
              <span>{{ showDebug[idx] ? '收起' : '展开' }}</span>
            </div>
            <div v-if="showDebug[idx]" class="debug-detail">
              <div v-for="(entry, ei) in msg.debug_logs" :key="ei" class="debug-entry">
                <div class="debug-step">
                  <span class="debug-step-name">{{ stepLabel(entry.step) }}</span>
                  <span class="debug-status-dot" :style="{ backgroundColor: statusColor(entry.status) }"></span>
                </div>
                <div class="debug-info">{{ formatLogDetail(entry) }}</div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="chatStore.loading" class="chat-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在调取数据并分析...</span>
        </div>
      </div>
      <div class="chat-input-area">
        <!-- @mention 浮层 -->
        <div v-if="showMentionPopup && filteredSkills.length > 0" class="mention-popup">
          <div class="mention-popup-title">选择技能</div>
          <div
            v-for="(skill, idx) in filteredSkills.slice(0, 6)"
            :key="skill.name"
            :class="['mention-item', idx === selectedMentionIndex ? 'mention-active' : '']"
            @click="selectSkill(skill)"
            @mouseenter="selectedMentionIndex = idx"
          >
            <span class="mention-icon">{{ skillTypeIcon(skill.skill_type) }}</span>
            <div class="mention-info">
              <span class="mention-name">{{ skill.name }}</span>
              <span class="mention-desc">{{ skill.description }}</span>
            </div>
          </div>
        </div>
        <!-- 已选 Skill 标签 -->
        <div v-if="selectedSkill" class="selected-skill-tag">
          <el-tag closable type="warning" @close="selectedSkill = null">@ {{ selectedSkill }}</el-tag>
        </div>
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          :placeholder="selectedSkill ? `向 @${selectedSkill} 提问...` : '输入问题... (@ 触发技能)'"
          :disabled="chatStore.loading"
          @keydown="handleKeydown"
        />
        <el-button
          type="primary"
          :icon="Promotion"
          :disabled="!inputText.trim() || chatStore.loading"
          @click="handleSend"
          style="margin-top: 8px; width: 100%"
        >
          发送
        </el-button>
      </div>
    </div>
  </transition>
</template>

<script lang="ts">
import { ChatDotRound, Loading, Promotion } from '@element-plus/icons-vue'
export default { components: { ChatDotRound, Loading, Promotion } }
</script>

<style scoped>
.chat-sidebar {
  height: 100%;
  background: #fff;
  border-left: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: relative;
}

.resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  width: 4px;
  height: 100%;
  cursor: col-resize;
  z-index: 10;
  background: transparent;
  transition: background 0.2s;
}

.resize-handle:hover,
.resize-handle.active {
  background: #409eff;
}

.chat-header {
  height: 50px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  padding: 0 16px;
  background: #f5f7fa;
  flex-shrink: 0;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-bottom: 1px solid #ebeef5;
  background: #fafafa;
  flex-shrink: 0;
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #c0c4cc;
  gap: 12px;
}

.empty-hints {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #c0c4cc;
  text-align: center;
}

.chat-bubble {
  margin-bottom: 14px;
  max-width: 95%;
}

.bubble-user {
  margin-left: auto;
}

.bubble-assistant {
  margin-right: auto;
}

.bubble-role {
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
}

.bubble-content {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-user .bubble-content {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 2px;
}

.bubble-assistant .bubble-content {
  background: #f4f4f5;
  color: #303133;
  border-bottom-left-radius: 2px;
  white-space: normal;
}

.bubble-assistant .markdown-body img {
  max-width: 100%;
  border-radius: 4px;
  margin: 8px 0;
  cursor: pointer;
}

.bubble-assistant .markdown-body table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
  font-size: 12px;
}

.bubble-assistant .markdown-body th,
.bubble-assistant .markdown-body td {
  border: 1px solid #dcdfe6;
  padding: 4px 8px;
  text-align: left;
}

.bubble-assistant .markdown-body th {
  background: #f0f2f5;
  font-weight: 600;
}

.bubble-assistant .markdown-body ul,
.bubble-assistant .markdown-body ol {
  padding-left: 20px;
  margin: 4px 0;
}

.bubble-assistant .markdown-body code {
  background: #e4e7ed;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}

.bubble-assistant .markdown-body pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 8px 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
  margin: 8px 0;
}

.bubble-assistant .markdown-body h1,
.bubble-assistant .markdown-body h2,
.bubble-assistant .markdown-body h3 {
  margin: 8px 0 4px;
  font-weight: 600;
}

.bubble-assistant .markdown-body h1 { font-size: 16px; }
.bubble-assistant .markdown-body h2 { font-size: 14px; }
.bubble-assistant .markdown-body h3 { font-size: 13px; }

.bubble-assistant .markdown-body blockquote {
  border-left: 3px solid #409eff;
  padding-left: 10px;
  margin: 6px 0;
  color: #606266;
}

/* Citation styles */
.bubble-citations {
  margin-top: 6px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fafafa;
  overflow: hidden;
}

.cit-header {
  font-size: 11px;
  font-weight: 600;
  color: #909399;
  padding: 4px 8px;
  background: #f0f2f5;
  border-bottom: 1px solid #ebeef5;
}

.cit-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 5px 8px;
  border-bottom: 1px solid #f0f2f5;
}

.cit-item:last-child {
  border-bottom: none;
}

.cit-icon {
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 1px;
}

.cit-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.cit-label {
  font-size: 11px;
  font-weight: 600;
  color: #409eff;
}

.cit-summary {
  font-size: 11px;
  color: #606266;
  line-height: 1.4;
  word-break: break-all;
}

/* Debug log styles */
.bubble-debug {
  margin-top: 6px;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  overflow: hidden;
}

.debug-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: #fef0f0;
  cursor: pointer;
  font-size: 11px;
  color: #f56c6c;
  font-weight: 500;
  user-select: none;
}

.debug-toggle:hover {
  background: #fde2e2;
}

.debug-detail {
  padding: 6px 8px;
  background: #fefefe;
}

.debug-entry {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 3px 0;
  border-bottom: 1px dotted #f0f0f0;
  font-size: 11px;
}

.debug-entry:last-child {
  border-bottom: none;
}

.debug-step {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  min-width: 90px;
}

.debug-step-name {
  font-weight: 600;
  color: #606266;
}

.debug-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.debug-info {
  color: #909399;
  line-height: 1.3;
  word-break: break-all;
}

.chat-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
  font-size: 13px;
  padding: 4px 0;
}

.chat-input-area {
  border-top: 1px solid #e4e7ed;
  padding: 12px;
}

.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all 0.3s ease;
}

.chat-slide-enter-from,
.chat-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.session-list {
  max-height: 320px;
  overflow-y: auto;
}

.session-empty {
  color: #c0c4cc;
  font-size: 12px;
  text-align: center;
  padding: 16px 0;
}

.session-item {
  display: flex;
  align-items: center;
  padding: 8px 4px;
  border-bottom: 1px solid #f0f2f5;
  cursor: pointer;
  transition: background 0.15s;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item:last-child {
  border-bottom: none;
}

.session-active {
  background: #ecf5ff;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.session-del {
  flex-shrink: 0;
  font-size: 16px;
  width: 24px;
  height: 24px;
}

/* @mention popup */
.mention-popup {
  position: absolute;
  bottom: 140px;
  left: 12px;
  right: 12px;
  max-height: 220px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,.12);
  z-index: 20;
}
.mention-popup-title {
  font-size: 11px;
  font-weight: 600;
  color: #909399;
  padding: 6px 10px 4px;
  border-bottom: 1px solid #f0f2f5;
}
.mention-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  cursor: pointer;
  transition: background .15s;
}
.mention-item:hover,
.mention-active { background: #ecf5ff; }
.mention-icon { font-size: 16px; flex-shrink: 0; }
.mention-info { display: flex; flex-direction: column; min-width: 0; }
.mention-name { font-size: 12px; font-weight: 600; color: #303133; }
.mention-desc { font-size: 11px; color: #909399; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.selected-skill-tag { margin-bottom: 6px; }
</style>
