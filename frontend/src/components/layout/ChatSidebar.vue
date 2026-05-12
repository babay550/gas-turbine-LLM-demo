<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { chatStore, sendChatMessage } from '../../stores'
import type { DebugLogEntry } from '../../types'

const inputText = ref('')
const messageListRef = ref<HTMLElement>()
const showDebug = ref<Record<number, boolean>>({})
const debugMode = ref(false)

const props = defineProps<{
  visible: boolean
}>()

function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  sendChatMessage(text)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
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
    <div v-if="visible" class="chat-sidebar">
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
          <div class="bubble-content">{{ msg.content }}</div>

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
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="输入问题..."
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
  width: 360px;
  height: 100%;
  background: #fff;
  border-left: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.chat-header {
  height: 50px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  padding: 0 16px;
  background: #f5f7fa;
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
</style>
