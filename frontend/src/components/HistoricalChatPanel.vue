<script setup lang="ts">
import { ref, nextTick } from 'vue'
import type { ParameterStat } from '../types'
import { renderMarkdown } from '../utils/markdown'

interface LocalMessage {
  role: 'user' | 'assistant'
  content: string
}

const props = defineProps<{
  dateRange: [Date, Date] | null
  selectedParams: string[]
  parameterNames: Record<string, string>
  stats: ParameterStat[]
}>()

const inputText = ref('')
const messages = ref<LocalMessage[]>([])
const messageListRef = ref<HTMLElement>()
const loading = ref(false)

function formatTime(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function buildContext(): string {
  const parts: string[] = ['[当前分析上下文]']
  if (props.dateRange) {
    parts.push(`时间范围: ${formatTime(props.dateRange[0])} ~ ${formatTime(props.dateRange[1])}`)
  }
  if (props.selectedParams.length > 0) {
    const names = props.selectedParams.map(k => props.parameterNames[k] || k).join(', ')
    parts.push(`已选参数: ${names}`)
  }
  if (props.stats.length > 0) {
    const summaries = props.stats.slice(0, 5).map(s => {
      const name = props.parameterNames[s.parameter_key] || s.parameter_key
      return `${name}: 均值=${s.mean?.toFixed(2) ?? '-'}, 最小=${s.min?.toFixed(2) ?? '-'}, 最大=${s.max?.toFixed(2) ?? '-'}`
    })
    parts.push(`统计摘要: ${summaries.join('; ')}`)
  }
  return parts.join('\n')
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value) return
  inputText.value = ''

  messages.value.push({ role: 'user', content: text })
  loading.value = true

  // 注入上下文前缀
  const context = buildContext()
  const fullMessage = context ? `${context}\n\n用户问题: ${text}` : text

  try {
    // 复用全局 chat store 的 sendChatMessage，但我们只关心回答文本
    // 为避免污染全局 store，直接调用 API
    const api = await import('../api')
    const res = await api.sendMessage({ message: fullMessage })
    messages.value.push({ role: 'assistant', content: res.answer })
  } catch (e: any) {
    messages.value.push({ role: 'assistant', content: `分析出错: ${e.message || e}` })
  } finally {
    loading.value = false
    await nextTick()
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="historical-chat-panel">
    <div class="panel-header">
      <span class="panel-title">💬 数据问答</span>
      <span class="panel-hint">基于当前选中时间段和参数</span>
    </div>
    <div ref="messageListRef" class="message-list">
      <div v-if="messages.length === 0" class="empty-hint">
        <p>选择时间段和参数后，在此提问</p>
        <div class="hint-examples">
          <span @click="inputText = '当前参数有哪些异常?'">当前参数有哪些异常?</span>
          <span @click="inputText = '分析这段时间的能效趋势'">分析这段时间的能效趋势</span>
          <span @click="inputText = '哪些参数超出了正常范围?'">哪些参数超出了正常范围?</span>
        </div>
      </div>
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        :class="['chat-bubble', msg.role === 'user' ? 'bubble-user' : 'bubble-assistant']"
      >
        <div v-if="msg.role === 'user'" class="bubble-content">{{ msg.content }}</div>
        <div v-else class="bubble-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
      </div>
      <div v-if="loading" class="chat-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在分析...</span>
      </div>
    </div>
    <div class="input-area">
      <el-input
        v-model="inputText"
        placeholder="针对当前数据提问..."
        :disabled="loading"
        @keydown="handleKeydown"
        size="default"
      >
        <template #append>
          <el-button :icon="Promotion" :disabled="!inputText.trim() || loading" @click="handleSend" />
        </template>
      </el-input>
    </div>
  </div>
</template>

<script lang="ts">
import { Loading, Promotion } from '@element-plus/icons-vue'
export default { components: { Loading, Promotion } }
</script>

<style scoped>
.historical-chat-panel {
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  height: 420px;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid #e4e7ed;
  background: #f5f7fa;
  border-radius: 8px 8px 0 0;
  flex-shrink: 0;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.panel-hint {
  font-size: 12px;
  color: #909399;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #c0c4cc;
  gap: 12px;
}

.hint-examples {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
}

.hint-examples span {
  cursor: pointer;
  color: #409eff;
  transition: color 0.2s;
}

.hint-examples span:hover {
  color: #66b1ff;
  text-decoration: underline;
}

.chat-bubble {
  margin-bottom: 10px;
  max-width: 95%;
}

.bubble-user {
  margin-left: auto;
}

.bubble-assistant {
  margin-right: auto;
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

.bubble-assistant .markdown-body table {
  border-collapse: collapse;
  width: 100%;
  margin: 6px 0;
  font-size: 12px;
}

.bubble-assistant .markdown-body th,
.bubble-assistant .markdown-body td {
  border: 1px solid #dcdfe6;
  padding: 3px 6px;
  text-align: left;
}

.bubble-assistant .markdown-body th {
  background: #f0f2f5;
  font-weight: 600;
}

.bubble-assistant .markdown-body code {
  background: #e4e7ed;
  padding: 1px 3px;
  border-radius: 3px;
  font-size: 12px;
}

.bubble-assistant .markdown-body pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 6px 10px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
  margin: 6px 0;
}

.chat-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
  font-size: 13px;
  padding: 4px 0;
}

.input-area {
  border-top: 1px solid #e4e7ed;
  padding: 10px;
  flex-shrink: 0;
}
</style>
