// ============================================================
// API Service Layer — Axios-based HTTP client for backend APIs
// ============================================================

import axios from 'axios'
import type {
  RealtimeData,
  EfficiencyTrendResponse,
  AnalysisResponse,
  EfficiencyAnalysisResult,
  LossAnalysisResult,
  BenchmarkAnalysisResult,
  DecompositionResult,
  RootCauseResult,
  ChatRequest,
  ChatResponse,
  ChatSession,
  ChatSessionDetail,
  ScheduleTask,
  AddTaskRequest,
  ExecutionLog,
  WarningListResponse,
  WarningDetail,
  ParameterListResponse,
  BaselineListResponse,
  BenchmarkIndicatorListResponse,
  ModelListResponse,
  ModelTestResult,
  MaintenanceListResponse,
  ExpertRuleListResponse,
  VectorKBSourceListResponse,
  CausalGraph,
  WikiEntryListResponse,
  WikiEntry,
  WikiStatsResponse,
  WikiUploadResult,
  WikiQAResponse,
  RawFileInfo,
  WikiGraphData,
  WorkflowDefinition,
  NodeTypeDef,
  ExecutionResult,
  RootCauseAnalysisResult,
} from '../types'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ---- Monitoring ----

export async function getRealtimeData(): Promise<RealtimeData> {
  const res = await http.get<RealtimeData>('/monitoring/realtime')
  return res.data
}

export async function getEfficiencyTrend(days = 7): Promise<EfficiencyTrendResponse> {
  const res = await http.get<EfficiencyTrendResponse>('/monitoring/efficiency-trend', {
    params: { days },
  })
  return res.data
}

// ---- Analysis ----

export async function runEfficiencyAnalysis(): Promise<AnalysisResponse<EfficiencyAnalysisResult>> {
  const res = await http.post<AnalysisResponse<EfficiencyAnalysisResult>>('/analysis/efficiency')
  return res.data
}

export async function runLossAnalysis(): Promise<AnalysisResponse<LossAnalysisResult>> {
  const res = await http.post<AnalysisResponse<LossAnalysisResult>>('/analysis/loss')
  return res.data
}

export async function runBenchmarkAnalysis(): Promise<AnalysisResponse<BenchmarkAnalysisResult>> {
  const res = await http.post<AnalysisResponse<BenchmarkAnalysisResult>>('/analysis/benchmark')
  return res.data
}

export async function runDecomposition(): Promise<DecompositionResult> {
  const res = await http.post<DecompositionResult>('/analysis/decomposition')
  return res.data
}

export async function runRootCause(query?: string): Promise<RootCauseAnalysisResult> {
  const res = await http.post<RootCauseAnalysisResult>('/analysis/root-cause', query ? { query } : undefined)
  return res.data
}

// ---- Chat ----

export async function sendMessage(payload: ChatRequest): Promise<ChatResponse> {
  // Agent 需要多轮 LLM 调用（意图识别→工具执行→总结），给足够时间
  const res = await http.post<ChatResponse>('/chat/message', payload, { timeout: 180000 })
  return res.data
}

// ---- Chat Sessions ----

export async function getChatSessions(): Promise<{ sessions: ChatSession[]; total: number }> {
  const res = await http.get<{ sessions: ChatSession[]; total: number }>('/chat/sessions')
  return res.data
}

export async function createChatSession(): Promise<ChatSessionDetail> {
  const res = await http.post<ChatSessionDetail>('/chat/sessions')
  return res.data
}

export async function getChatSession(id: string): Promise<ChatSessionDetail> {
  const res = await http.get<ChatSessionDetail>(`/chat/sessions/${encodeURIComponent(id)}`)
  return res.data
}

export async function deleteChatSession(id: string): Promise<{ success: boolean }> {
  const res = await http.delete<{ success: boolean }>(`/chat/sessions/${encodeURIComponent(id)}`)
  return res.data
}

/** Build a WebSocket URL for the chat stream. Caller is responsible for opening/closing. */
export function buildChatWsUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/api/chat/ws`
}

// ---- Schedule ----

export async function getScheduleTasks(): Promise<ScheduleTask[]> {
  const res = await http.get<ScheduleTask[]>('/schedule/tasks')
  return res.data
}

export async function addScheduleTask(payload: AddTaskRequest): Promise<{ success: boolean }> {
  const res = await http.post<{ success: boolean }>('/schedule/tasks', payload)
  return res.data
}

export async function removeScheduleTask(taskType: string): Promise<{ success: boolean }> {
  const res = await http.delete<{ success: boolean }>(`/schedule/tasks/${encodeURIComponent(taskType)}`)
  return res.data
}

export async function triggerNow(payload: { task_type: string }): Promise<unknown> {
  const res = await http.post('/schedule/trigger', payload)
  return res.data
}

export async function getExecutionLogs(limit = 20): Promise<ExecutionLog[]> {
  const res = await http.get<ExecutionLog[]>('/schedule/logs', { params: { limit } })
  return res.data
}

// ---- Warning ----

export async function getWarnings(status?: string): Promise<WarningListResponse> {
  const res = await http.get<WarningListResponse>('/warning/list', {
    params: status ? { status } : undefined,
  })
  return res.data
}

export async function getWarningDetail(warningId: string): Promise<WarningDetail> {
  const res = await http.get<WarningDetail>(`/warning/${encodeURIComponent(warningId)}`)
  return res.data
}

// ---- Dictionary ----

export async function getParameters(): Promise<ParameterListResponse> {
  const res = await http.get<ParameterListResponse>('/dictionary/parameters')
  return res.data
}

export async function getBaselines(): Promise<BaselineListResponse> {
  const res = await http.get<BaselineListResponse>('/dictionary/baselines')
  return res.data
}

export async function getBenchmarkIndicators(): Promise<BenchmarkIndicatorListResponse> {
  const res = await http.get<BenchmarkIndicatorListResponse>('/dictionary/benchmark-indicators')
  return res.data
}

// ---- Knowledge ----

export async function getModels(): Promise<ModelListResponse> {
  const res = await http.get<ModelListResponse>('/knowledge/models')
  return res.data
}

export async function getMaintenanceKnowledge(category?: string): Promise<MaintenanceListResponse> {
  const res = await http.get<MaintenanceListResponse>('/knowledge/knowledge/maintenance', {
    params: category ? { category } : undefined,
  })
  return res.data
}

export async function getExpertRules(): Promise<ExpertRuleListResponse> {
  const res = await http.get<ExpertRuleListResponse>('/knowledge/knowledge/rules')
  return res.data
}

export async function getCausalGraph(): Promise<CausalGraph> {
  const res = await http.get<CausalGraph>('/knowledge/knowledge/causal-graph')
  return res.data
}

export async function testModelConnection(modelId: string): Promise<ModelTestResult> {
  const res = await http.post<ModelTestResult>(`/knowledge/models/${encodeURIComponent(modelId)}/test`)
  return res.data
}

export async function getVectorKBSources(): Promise<VectorKBSourceListResponse> {
  const res = await http.get<VectorKBSourceListResponse>('/knowledge/knowledge/vector-sources')
  return res.data
}

export async function addVectorKBSource(payload: { name: string; url: string; embedding_model?: string }): Promise<{ success: boolean; id: string; message: string }> {
  const res = await http.post('/knowledge/knowledge/vector-sources', payload)
  return res.data
}

export async function testVectorKBConnection(sourceId: string): Promise<ModelTestResult> {
  const res = await http.post<ModelTestResult>(`/knowledge/knowledge/vector-sources/${encodeURIComponent(sourceId)}/test`)
  return res.data
}

// ---- Wiki 技术知识库 ----

export async function getWikiEntries(params?: {
  type?: string; category?: string; tag?: string; search?: string
  page?: number; page_size?: number
}): Promise<WikiEntryListResponse> {
  const res = await http.get<WikiEntryListResponse>('/knowledge/knowledge/wiki/entries', { params })
  return res.data
}

export async function getWikiEntry(entryId: string): Promise<WikiEntry> {
  const res = await http.get<WikiEntry>(`/knowledge/knowledge/wiki/entries/${encodeURIComponent(entryId)}`)
  return res.data
}

export async function updateWikiEntry(entryId: string, data: Partial<WikiEntry>): Promise<{ success: boolean }> {
  const res = await http.put<{ success: boolean }>(`/knowledge/knowledge/wiki/entries/${encodeURIComponent(entryId)}`, data)
  return res.data
}

export async function deleteWikiEntry(entryId: string): Promise<{ success: boolean }> {
  const res = await http.delete<{ success: boolean }>(`/knowledge/knowledge/wiki/entries/${encodeURIComponent(entryId)}`)
  return res.data
}

export async function uploadWikiDocument(file: File, autoGenerate = true): Promise<WikiUploadResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('auto_generate', String(autoGenerate))
  const res = await http.post<WikiUploadResult>('/knowledge/knowledge/wiki/upload', form, {
    timeout: 300000,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function getWikiCategories(): Promise<string[]> {
  const res = await http.get<{ categories: string[] }>('/knowledge/knowledge/wiki/categories')
  return res.data.categories
}

export async function getWikiTags(): Promise<string[]> {
  const res = await http.get<{ tags: string[] }>('/knowledge/knowledge/wiki/tags')
  return res.data.tags
}

export async function getWikiStats(): Promise<WikiStatsResponse> {
  const res = await http.get<WikiStatsResponse>('/knowledge/knowledge/wiki/stats')
  return res.data
}

export async function wikiQA(query: string): Promise<WikiQAResponse> {
  // Wiki QA 需要 LLM 检索+生成，耗时较长
  const res = await http.post<WikiQAResponse>('/knowledge/knowledge/wiki/qa', { query }, { timeout: 180000 })
  return res.data
}

export async function rebuildWikiIndex(): Promise<{ success: boolean }> {
  const res = await http.post<{ success: boolean }>('/knowledge/knowledge/wiki/rebuild-index')
  return res.data
}

export async function getWikiRawFiles(): Promise<{ files: RawFileInfo[]; total: number }> {
  const res = await http.get<{ files: RawFileInfo[]; total: number }>('/knowledge/knowledge/wiki/raw-files')
  return res.data
}

export async function getWikiRawFile(filename: string): Promise<{ filename: string; content: string; type: string }> {
  const res = await http.get<{ filename: string; content: string; type: string }>(`/knowledge/knowledge/wiki/raw-files/${encodeURIComponent(filename)}`)
  return res.data
}

export async function getWikiGraph(): Promise<WikiGraphData> {
  const res = await http.get<WikiGraphData>('/knowledge/knowledge/wiki/graph')
  return res.data
}

export async function getWikiIndexContent(): Promise<string> {
  const res = await http.get<{ content: string }>('/knowledge/knowledge/wiki/index')
  return res.data.content
}

export async function getWikiLogContent(): Promise<string> {
  const res = await http.get<{ content: string }>('/knowledge/knowledge/wiki/log')
  return res.data.content
}

// ---- Workflow ----

export async function getWorkflows(): Promise<WorkflowDefinition[]> {
  const res = await http.get<WorkflowDefinition[]>('/workflow/list')
  return res.data
}

export async function getWorkflow(id: string): Promise<WorkflowDefinition> {
  const res = await http.get<WorkflowDefinition>(`/workflow/${encodeURIComponent(id)}`)
  return res.data
}

export async function saveWorkflow(data: WorkflowDefinition): Promise<{ success: boolean; id: string }> {
  const res = await http.post<{ success: boolean; id: string }>('/workflow', data)
  return res.data
}

export async function deleteWorkflow(id: string): Promise<{ success: boolean }> {
  const res = await http.delete<{ success: boolean }>(`/workflow/${encodeURIComponent(id)}`)
  return res.data
}

export async function getWorkflowTemplates(): Promise<WorkflowDefinition[]> {
  const res = await http.get<WorkflowDefinition[]>('/workflow/templates')
  return res.data
}

export async function getWorkflowNodeTypes(): Promise<NodeTypeDef[]> {
  const res = await http.get<NodeTypeDef[]>('/workflow/node-types')
  return res.data
}

export async function executeWorkflow(id: string, userInput: string): Promise<ExecutionResult> {
  const res = await http.post<ExecutionResult>(`/workflow/${encodeURIComponent(id)}/execute`, {
    user_input: userInput,
  })
  return res.data
}
