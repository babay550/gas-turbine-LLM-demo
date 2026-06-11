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
  VectorRetrieveResponse,
  VectorQAResponse,
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
  SkillDefinition,
  SkillCreateRequest,
  SkillExecuteResult,
  SkillTypeOption,
  SkillFileInfo,
  SkillFileContent,
  ImportPreview,
  ImportColumnMapping,
  ImportJob,
  TimeRangeInfo,
  TimeSeriesQueryResponse,
  ParameterStat,
  ParameterTrendResponse,
  LoginRequest,
  LoginResponse,
  UserInfo,
  UserListResponse,
  UserCreateRequest,
  Organization,
  OrganizationTreeResponse,
  ChangePasswordRequest,
} from '../types'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ---- 认证拦截器 ----

// 请求拦截器：注入 JWT token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('gas_turbine_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：处理 401 → 跳转登录
http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('gas_turbine_token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

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

export async function runLossAnalysis(aggregation: string = 'raw'): Promise<AnalysisResponse<LossAnalysisResult>> {
  const res = await http.post<AnalysisResponse<LossAnalysisResult>>('/analysis/loss', { aggregation })
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

export async function runPeriodLossAnalysis(params: {
  parameter_keys: string[]
  start: string
  end: string
  unit_id?: string
}): Promise<AnalysisResponse<LossAnalysisResult>> {
  const res = await http.post<AnalysisResponse<LossAnalysisResult>>('/analysis/period-loss', {
    parameter_keys: params.parameter_keys,
    start: params.start,
    end: params.end,
    unit_id: params.unit_id || 'GT-01',
  })
  return res.data
}

export async function runRootCause(query?: string): Promise<RootCauseAnalysisResult> {
  const res = await http.post<RootCauseAnalysisResult>('/analysis/root-cause', query ? { query } : undefined)
  return res.data
}

// ---- Chat ----

export async function sendMessage(payload: ChatRequest & { skill_hint?: string }): Promise<ChatResponse> {
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

export async function getImportTimeFormats(): Promise<{ presets: { key: string; format: string; example: string }[] }> {
  const res = await http.get('/data-import/time-formats')
  return res.data
}

export async function createParameter(data: {
  name: string; unit: string; subsystem?: string; location?: string;
  normal_min?: number; normal_max?: number; source?: string; update_freq?: string;
}): Promise<{ success: boolean; id: string; message: string }> {
  const res = await http.post('/dictionary/parameters', data)
  return res.data
}

export async function updateParameter(id: string, data: Record<string, unknown>): Promise<{ success: boolean }> {
  const res = await http.put(`/dictionary/parameters/${encodeURIComponent(id)}`, data)
  return res.data
}

export async function deleteParameter(id: string): Promise<{ success: boolean }> {
  const res = await http.delete(`/dictionary/parameters/${encodeURIComponent(id)}`)
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

// ---- Loss Variable Config (耗差分析损失项配置) ----

export interface LossVariableItem {
  id: number
  param_key: string
  name: string
  unit: string
  baseline: number
  best: number
  sort_order: number
}

export async function getLossVariables(): Promise<{ variables: LossVariableItem[]; total: number }> {
  const res = await http.get<{ variables: LossVariableItem[]; total: number }>('/dictionary/loss-variables')
  return res.data
}

export async function createLossVariable(data: {
  param_key: string; name: string; unit: string; baseline: number; best: number;
}): Promise<{ success: boolean; id: number; variable: LossVariableItem }> {
  const res = await http.post<{ success: boolean; id: number; variable: LossVariableItem }>('/dictionary/loss-variables', data)
  return res.data
}

export async function updateLossVariable(id: number, data: {
  param_key?: string; name?: string; unit?: string; baseline?: number; best?: number; sort_order?: number;
}): Promise<{ success: boolean; variable: LossVariableItem }> {
  const res = await http.put<{ success: boolean; variable: LossVariableItem }>(`/dictionary/loss-variables/${id}`, data)
  return res.data
}

export async function deleteLossVariable(id: number): Promise<{ success: boolean }> {
  const res = await http.delete<{ success: boolean }>(`/dictionary/loss-variables/${id}`)
  return res.data
}

// ---- Waterfall Config (瀑布图配置) ----

export async function getWaterfallConfig(): Promise<{ total_key: string; subsystem_keys: string[] }> {
  const res = await http.get<{ total_key: string; subsystem_keys: string[] }>('/dictionary/waterfall-config')
  return res.data
}

export async function saveWaterfallConfig(data: {
  total_key: string; subsystem_keys: string[];
}): Promise<{ success: boolean }> {
  const res = await http.put<{ success: boolean }>('/dictionary/waterfall-config', data)
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

export async function addVectorKBSource(payload: {
  name: string
  retrieve_url: string
  ocr_url?: string
  minio_url?: string
  minio_bucket?: string
  default_final_top_k?: number
  default_hyde_mode?: boolean
  default_query_decomposition_mode?: boolean
}): Promise<{ success: boolean; id: string; message: string }> {
  const res = await http.post('/knowledge/knowledge/vector-sources', payload)
  return res.data
}

export async function deleteVectorKBSource(sourceId: string): Promise<{ success: boolean; message: string }> {
  const res = await http.delete(`/knowledge/knowledge/vector-sources/${encodeURIComponent(sourceId)}`)
  return res.data
}

export async function testVectorKBConnection(sourceId: string): Promise<ModelTestResult> {
  const res = await http.post<ModelTestResult>(`/knowledge/knowledge/vector-sources/${encodeURIComponent(sourceId)}/test`)
  return res.data
}

export async function vectorRetrieve(sourceId: string, params: {
  query: string
  tags?: string
  final_top_k?: number
  hyde_mode?: boolean
  query_decomposition_mode?: boolean
  doc_sources?: string
}): Promise<VectorRetrieveResponse> {
  const res = await http.post<VectorRetrieveResponse>(
    `/knowledge/knowledge/vector-sources/${encodeURIComponent(sourceId)}/retrieve`,
    params,
    { timeout: 60000 },
  )
  return res.data
}

export async function vectorQA(sourceId: string, query: string): Promise<VectorQAResponse> {
  const res = await http.post<VectorQAResponse>(
    `/knowledge/knowledge/vector-sources/${encodeURIComponent(sourceId)}/qa`,
    { query },
    { timeout: 180000 },
  )
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

// ---- Skills ----

export async function getSkills(): Promise<SkillDefinition[]> {
  const res = await http.get<SkillDefinition[]>('/skills/list')
  return res.data
}

export async function getSkill(name: string): Promise<SkillDefinition> {
  const res = await http.get<SkillDefinition>(`/skills/${encodeURIComponent(name)}`)
  return res.data
}

export async function getSkillTypes(): Promise<{ types: SkillTypeOption[] }> {
  const res = await http.get<{ types: SkillTypeOption[] }>('/skills/types')
  return res.data
}

export async function createSkill(data: SkillCreateRequest): Promise<{ success: boolean; name: string }> {
  const res = await http.post<{ success: boolean; name: string }>('/skills', data)
  return res.data
}

export async function updateSkill(name: string, data: Partial<SkillDefinition>): Promise<{ success: boolean }> {
  const res = await http.put<{ success: boolean }>(`/skills/${encodeURIComponent(name)}`, data)
  return res.data
}

export async function deleteSkill(name: string): Promise<{ success: boolean }> {
  const res = await http.delete<{ success: boolean }>(`/skills/${encodeURIComponent(name)}`)
  return res.data
}

export async function executeSkill(name: string, args: Record<string, unknown> = {}): Promise<SkillExecuteResult> {
  const res = await http.post<SkillExecuteResult>(`/skills/${encodeURIComponent(name)}/execute`, { args })
  return res.data
}

export async function getSkillReferences(name: string): Promise<{ skill: string; files: string[]; total: number }> {
  const res = await http.get<{ skill: string; files: string[]; total: number }>(`/skills/${encodeURIComponent(name)}/references`)
  return res.data
}

export async function reloadSkills(): Promise<{ success: boolean; count: number }> {
  const res = await http.post<{ success: boolean; count: number }>('/skills/reload')
  return res.data
}

// ---- Skills: ZIP Import/Export ----

export async function importSkillZip(file: File): Promise<{ success: boolean; name: string; type: string; description: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await http.post<{ success: boolean; name: string; type: string; description: string }>(
    '/skills/import', form,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 },
  )
  return res.data
}

export function exportSkillUrl(name: string): string {
  return `/api/skills/${encodeURIComponent(name)}/export`
}

// ---- Skills: File Browser/Editor ----

export async function listSkillFiles(name: string): Promise<{ skill: string; files: SkillFileInfo[]; total: number }> {
  const res = await http.get<{ skill: string; files: SkillFileInfo[]; total: number }>(`/skills/${encodeURIComponent(name)}/files`)
  return res.data
}

export async function readSkillFile(name: string, filePath: string): Promise<SkillFileContent> {
  const res = await http.get<SkillFileContent>(`/skills/${encodeURIComponent(name)}/files/${encodeURIComponent(filePath)}`)
  return res.data
}

export async function writeSkillFile(name: string, filePath: string, content: string): Promise<{ success: boolean; path: string }> {
  const res = await http.put<{ success: boolean; path: string }>(
    `/skills/${encodeURIComponent(name)}/files/${encodeURIComponent(filePath)}`,
    { content },
  )
  return res.data
}

// ---- Data Import ----

export async function uploadDataFile(file: File): Promise<ImportPreview> {
  const form = new FormData()
  form.append('file', file)
  const res = await http.post<ImportPreview>('/data-import/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return res.data
}

export async function executeImport(jobId: number, mapping: ImportColumnMapping): Promise<{ job_id: number; status: string; imported_rows?: number; error_message?: string }> {
  const res = await http.post(`/data-import/${jobId}/execute`, mapping, { timeout: 300000 })
  return res.data
}

export async function getImportJobStatus(jobId: number): Promise<ImportJob> {
  const res = await http.get<ImportJob>(`/data-import/${jobId}/status`)
  return res.data
}

export async function getImportJobs(): Promise<{ jobs: ImportJob[]; total: number }> {
  const res = await http.get<{ jobs: ImportJob[]; total: number }>('/data-import/jobs')
  return res.data
}

export async function deleteImportJob(jobId: number): Promise<{ success: boolean; message: string }> {
  const res = await http.delete(`/data-import/${jobId}`)
  return res.data
}

export async function getImportJobPreview(jobId: number): Promise<ImportPreview> {
  const res = await http.get<ImportPreview>(`/data-import/${jobId}/preview`)
  return res.data
}

// ---- Auth ----

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await http.post<LoginResponse>('/auth/login', data)
  return res.data
}

export async function getMe(): Promise<UserInfo> {
  const res = await http.get<UserInfo>('/auth/me')
  return res.data
}

export async function changePassword(data: ChangePasswordRequest): Promise<{ success: boolean; message: string }> {
  const res = await http.put('/auth/me/password', data)
  return res.data
}

// ---- User Management (admin) ----

export async function getUsers(params?: { page?: number; page_size?: number; search?: string; role?: string }): Promise<UserListResponse> {
  const res = await http.get<UserListResponse>('/users', { params })
  return res.data
}

export async function createUser(data: UserCreateRequest): Promise<{ success: boolean; id: number; message: string }> {
  const res = await http.post('/users', data)
  return res.data
}

export async function updateUser(userId: number, data: Record<string, unknown>): Promise<{ success: boolean }> {
  const res = await http.put(`/users/${userId}`, data)
  return res.data
}

export async function deleteUser(userId: number): Promise<{ success: boolean }> {
  const res = await http.delete(`/users/${userId}`)
  return res.data
}

export async function resetUserPassword(userId: number, newPassword: string): Promise<{ success: boolean }> {
  const res = await http.put(`/users/${userId}/password`, { new_password: newPassword })
  return res.data
}

export async function updateUserRole(userId: number, role: string): Promise<{ success: boolean }> {
  const res = await http.put(`/users/${userId}/role`, { role })
  return res.data
}

// ---- Organization Management (admin) ----

export async function getOrgTree(): Promise<OrganizationTreeResponse> {
  const res = await http.get<OrganizationTreeResponse>('/organizations')
  return res.data
}

export async function getOrgFlat(): Promise<{ organizations: Organization[] }> {
  const res = await http.get('/organizations/flat')
  return res.data
}

export async function createOrg(data: { name: string; parent_id?: number | null; code?: string; description?: string }): Promise<{ success: boolean; id: number }> {
  const res = await http.post('/organizations', data)
  return res.data
}

export async function updateOrg(orgId: number, data: Record<string, unknown>): Promise<{ success: boolean }> {
  const res = await http.put(`/organizations/${orgId}`, data)
  return res.data
}

export async function deleteOrg(orgId: number): Promise<{ success: boolean }> {
  const res = await http.delete(`/organizations/${orgId}`)
  return res.data
}

// ---- Historical Data ----

export async function getTimeRange(unitId = 'GT-01'): Promise<TimeRangeInfo> {
  const res = await http.get<TimeRangeInfo>('/historical/range', { params: { unit_id: unitId } })
  return res.data
}

export async function queryTimeSeries(params: {
  parameter_keys: string[]
  start: string
  end: string
  unit_id?: string
  aggregation?: string
}): Promise<TimeSeriesQueryResponse> {
  const res = await http.get<TimeSeriesQueryResponse>('/historical/query', {
    params: {
      parameter_keys: params.parameter_keys.join(','),
      start: params.start,
      end: params.end,
      unit_id: params.unit_id || 'GT-01',
      aggregation: params.aggregation || 'raw',
    },
  })
  return res.data
}

export async function getParameterStats(params: {
  parameter_keys: string[]
  start: string
  end: string
  unit_id?: string
}): Promise<{ stats: ParameterStat[]; total: number }> {
  const res = await http.get<{ stats: ParameterStat[]; total: number }>('/historical/stats', {
    params: {
      parameter_keys: params.parameter_keys.join(','),
      start: params.start,
      end: params.end,
      unit_id: params.unit_id || 'GT-01',
    },
  })
  return res.data
}

export async function getParameterTrend(parameterKey: string, params: {
  start: string
  end: string
  unit_id?: string
  aggregation?: string
}): Promise<ParameterTrendResponse> {
  const res = await http.get<ParameterTrendResponse>(`/historical/parameters/${encodeURIComponent(parameterKey)}/trend`, {
    params: {
      start: params.start,
      end: params.end,
      unit_id: params.unit_id || 'GT-01',
      aggregation: params.aggregation || 'raw',
    },
  })
  return res.data
}
