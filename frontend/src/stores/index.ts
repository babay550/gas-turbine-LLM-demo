// ============================================================
// Reactive Stores — Vue 3 reactive()-based state management
// ============================================================

import { reactive, readonly } from 'vue'
import type {
  RealtimeData,
  EfficiencyTrendResponse,
  EfficiencyAnalysisResult,
  LossAnalysisResult,
  BenchmarkAnalysisResult,
  DecompositionResult,
  Warning,
  WarningDetail,
  ScheduleTask,
  ExecutionLog,
  ChatMessage,
  ChatCitation,
  DebugLogEntry,
  ChatSession,
  SkillDefinition,
} from '../types'
import * as api from '../api'

// ---- Realtime Store ----

const _realtime = reactive({
  data: null as RealtimeData | null,
  trend: null as EfficiencyTrendResponse | null,
  loading: false,
  error: null as string | null,
})

export const realtimeStore = readonly(_realtime)

export async function fetchRealtimeData() {
  _realtime.loading = true
  _realtime.error = null
  try {
    _realtime.data = await api.getRealtimeData()
  } catch (e: unknown) {
    _realtime.error = e instanceof Error ? e.message : String(e)
  } finally {
    _realtime.loading = false
  }
}

export async function fetchEfficiencyTrend(days = 7) {
  _realtime.loading = true
  _realtime.error = null
  try {
    _realtime.trend = await api.getEfficiencyTrend(days)
  } catch (e: unknown) {
    _realtime.error = e instanceof Error ? e.message : String(e)
  } finally {
    _realtime.loading = false
  }
}

// ---- Analysis Store ----

interface AnalysisState {
  efficiency: EfficiencyAnalysisResult | null
  loss: LossAnalysisResult | null
  benchmark: BenchmarkAnalysisResult | null
  decomposition: DecompositionResult | null
  loading: boolean
  error: string | null
}

const _analysis = reactive<AnalysisState>({
  efficiency: null,
  loss: null,
  benchmark: null,
  decomposition: null,
  loading: false,
  error: null,
})

export const analysisStore = readonly(_analysis)

export async function runEfficiency() {
  _analysis.loading = true
  _analysis.error = null
  try {
    const res = await api.runEfficiencyAnalysis()
    _analysis.efficiency = res.result
  } catch (e: unknown) {
    _analysis.error = e instanceof Error ? e.message : String(e)
  } finally {
    _analysis.loading = false
  }
}

export async function runLoss(aggregation: string = 'raw') {
  _analysis.loading = true
  _analysis.error = null
  try {
    const res = await api.runLossAnalysis(aggregation)
    _analysis.loss = res.result
  } catch (e: unknown) {
    _analysis.error = e instanceof Error ? e.message : String(e)
  } finally {
    _analysis.loading = false
  }
}

export async function runBenchmark() {
  _analysis.loading = true
  _analysis.error = null
  try {
    const res = await api.runBenchmarkAnalysis()
    _analysis.benchmark = res.result
  } catch (e: unknown) {
    _analysis.error = e instanceof Error ? e.message : String(e)
  } finally {
    _analysis.loading = false
  }
}

export async function runDecomposition() {
  _analysis.loading = true
  _analysis.error = null
  try {
    _analysis.decomposition = await api.runDecomposition()
  } catch (e: unknown) {
    _analysis.error = e instanceof Error ? e.message : String(e)
  } finally {
    _analysis.loading = false
  }
}

// ---- Warning Store ----

interface WarningState {
  list: Warning[]
  currentDetail: WarningDetail | null
  total: number
  loading: boolean
  error: string | null
}

const _warning = reactive<WarningState>({
  list: [],
  currentDetail: null,
  total: 0,
  loading: false,
  error: null,
})

export const warningStore = readonly(_warning)

export async function fetchWarnings(status?: string) {
  _warning.loading = true
  _warning.error = null
  try {
    const res = await api.getWarnings(status)
    _warning.list = res.warnings
    _warning.total = res.total
  } catch (e: unknown) {
    _warning.error = e instanceof Error ? e.message : String(e)
  } finally {
    _warning.loading = false
  }
}

export async function fetchWarningDetail(warningId: string) {
  _warning.loading = true
  _warning.error = null
  try {
    _warning.currentDetail = await api.getWarningDetail(warningId)
  } catch (e: unknown) {
    _warning.error = e instanceof Error ? e.message : String(e)
  } finally {
    _warning.loading = false
  }
}

// ---- Schedule Store ----

interface ScheduleState {
  tasks: ScheduleTask[]
  logs: ExecutionLog[]
  loading: boolean
  error: string | null
}

const _schedule = reactive<ScheduleState>({
  tasks: [],
  logs: [],
  loading: false,
  error: null,
})

export const scheduleStore = readonly(_schedule)

export async function fetchScheduleTasks() {
  _schedule.loading = true
  _schedule.error = null
  try {
    _schedule.tasks = await api.getScheduleTasks()
  } catch (e: unknown) {
    _schedule.error = e instanceof Error ? e.message : String(e)
  } finally {
    _schedule.loading = false
  }
}

export async function addTask(taskType: string, intervalSeconds: number) {
  _schedule.loading = true
  _schedule.error = null
  try {
    await api.addScheduleTask({ task_type: taskType, interval_seconds: intervalSeconds })
    _schedule.tasks = await api.getScheduleTasks()
  } catch (e: unknown) {
    _schedule.error = e instanceof Error ? e.message : String(e)
  } finally {
    _schedule.loading = false
  }
}

export async function removeTask(taskType: string) {
  _schedule.loading = true
  _schedule.error = null
  try {
    await api.removeScheduleTask(taskType)
    _schedule.tasks = await api.getScheduleTasks()
  } catch (e: unknown) {
    _schedule.error = e instanceof Error ? e.message : String(e)
  } finally {
    _schedule.loading = false
  }
}

export async function triggerTaskNow(taskType: string) {
  _schedule.loading = true
  _schedule.error = null
  try {
    await api.triggerNow({ task_type: taskType })
  } catch (e: unknown) {
    _schedule.error = e instanceof Error ? e.message : String(e)
  } finally {
    _schedule.loading = false
  }
}

export async function fetchExecutionLogs(limit = 20) {
  _schedule.loading = true
  _schedule.error = null
  try {
    _schedule.logs = await api.getExecutionLogs(limit)
  } catch (e: unknown) {
    _schedule.error = e instanceof Error ? e.message : String(e)
  } finally {
    _schedule.loading = false
  }
}

// ---- Chat Store ----

interface ChatState {
  messages: ChatMessage[]
  loading: boolean
  error: string | null
  currentSessionId: string | null
  sessions: ChatSession[]
}

const _chat = reactive<ChatState>({
  messages: [],
  loading: false,
  error: null,
  currentSessionId: null,
  sessions: [],
})

export const chatStore = readonly(_chat)

export async function loadSessions() {
  try {
    const res = await api.getChatSessions()
    _chat.sessions = res.sessions
  } catch {
    // ignore — non-critical
  }
}

export async function createSession() {
  try {
    const session = await api.createChatSession()
    _chat.currentSessionId = session.id
    _chat.messages = []
    _chat.error = null
    await loadSessions()
    return session
  } catch (e: unknown) {
    console.warn('createSession failed:', e)
    return null
  }
}

export async function switchSession(id: string) {
  try {
    const detail = await api.getChatSession(id)
    _chat.currentSessionId = id
    _chat.messages = detail.messages || []
    _chat.error = null
  } catch (e: unknown) {
    _chat.error = e instanceof Error ? e.message : String(e)
  }
}

export async function deleteSession(id: string) {
  try {
    await api.deleteChatSession(id)
    if (_chat.currentSessionId === id) {
      _chat.currentSessionId = null
      _chat.messages = []
    }
    await loadSessions()
  } catch {
    // ignore
  }
}

export async function sendChatMessage(message: string, skillHint?: string) {
  if (!_chat.currentSessionId) {
    const session = await createSession()
    if (!session) {
      console.warn('Proceeding without session persistence')
    }
  }

  _chat.messages.push({ role: 'user', content: message })
  _chat.loading = true
  _chat.error = null
  try {
    const res = await api.sendMessage({
      message,
      session_id: _chat.currentSessionId || undefined,
      ...(skillHint ? { skill_hint: skillHint } : {}),
    })
    const citations: ChatCitation[] = res.citations || []
    const debugLogs: DebugLogEntry[] = res.debug_logs || []
    _chat.messages.push({ role: 'assistant', content: res.answer, citations, debug_logs: debugLogs })
  } catch (e: unknown) {
    const errMsg = e instanceof Error ? e.message : String(e)
    _chat.error = errMsg
    _chat.messages.push({ role: 'assistant', content: `分析出错: ${errMsg}`, citations: [], debug_logs: [] })
  } finally {
    _chat.loading = false
    loadSessions()
  }
}

// ---- Skill Store ----

interface SkillState {
  skills: SkillDefinition[]
  loading: boolean
  error: string | null
}

const _skills = reactive<SkillState>({
  skills: [],
  loading: false,
  error: null,
})

export const skillStore = readonly(_skills)

export async function loadSkills() {
  _skills.loading = true
  _skills.error = null
  try {
    _skills.skills = await api.getSkills()
  } catch (e: unknown) {
    _skills.error = e instanceof Error ? e.message : String(e)
  } finally {
    _skills.loading = false
  }
}
