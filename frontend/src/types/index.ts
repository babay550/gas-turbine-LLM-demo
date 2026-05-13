// ============================================================
// TypeScript interfaces for the Gas Turbine Intelligent O&M System
// ============================================================

// ---- Realtime Monitoring ----

export interface RealtimeData {
  timestamp: string
  unit_id: string
  parameters: Record<string, number>
  status: string
  warnings: string[]
}

// ---- Efficiency Trend ----

export interface EfficiencyTrendData {
  '日期': string[]
  '热耗率_kJ/kWh': number[]
  '发电效率_%': number[]
  '厂用电率_%': number[]
  '综合厂用电率_%': number[]
}

export interface EfficiencyTrendResponse {
  data: EfficiencyTrendData
  period_days: number
}

// ---- Efficiency Analysis ----

export interface EfficiencyIndicator {
  value: number
  design: number
  unit: string
  best: number
}

export interface EfficiencyAnalysisResult {
  analysis_time: string
  unit_id: string
  indicators: Record<string, EfficiencyIndicator>
  scada: Record<string, number>
  suggestions: string[]
}

export interface AnalysisResponse<T = unknown> {
  tool: string
  result: T
}

// ---- Loss Analysis ----

export interface LossItem {
  name: string
  value: number
  design: number
}

export interface LossAnalysisResult {
  analysis_time: string
  unit_id: string
  total_loss: number
  total_design_loss: number
  items: LossItem[]
  major_losses: LossItem[]
}

// ---- Benchmark Analysis ----

export interface BenchmarkGap {
  indicator: string
  this_unit: number
  peer_avg: number
  gap: number
  unit: string
}

export interface BenchmarkAnalysisResult {
  analysis_time: string
  unit_id: string
  peer_group: string
  period: string
  gaps: BenchmarkGap[]
  strengths: BenchmarkGap[]
  weaknesses: BenchmarkGap[]
}

// ---- Decomposition Analysis ----

export interface DecompositionComponent {
  name: string
  value: number
  design: number
}

export interface DecompositionSubsystem {
  contribution: number
  components: DecompositionComponent[]
}

export interface DecompositionResult {
  total_loss: number
  total_design_loss: number
  subsystems: Record<string, DecompositionSubsystem>
}

// ---- Root Cause Analysis ----

export interface RootCauseResult {
  tool: string
  result: string
  error?: string
}

// ---- Warnings ----

export interface Warning {
  id: string
  level: string
  source: string
  message: string
  parameter: string
  value: number
  threshold: number
  unit: string
  time: string
  status: 'active' | 'resolved'
}

export interface WarningDetail extends Warning {
  suggestions: string[]
  history: WarningHistoryEntry[]
}

export interface WarningHistoryEntry {
  time: string
  value: number
  status: string
}

export interface WarningListResponse {
  warnings: Warning[]
  total: number
}

// ---- Schedule Tasks ----

export interface ScheduleTask {
  job_id: string
  task_type: string
  interval_seconds: number
  next_run?: string
  last_run?: string
}

export interface ExecutionLog {
  timestamp: string
  trigger_type: string
  task_type: string
  status: 'success' | 'error'
  result?: string
}

export interface TriggerRequest {
  task_type: string
}

export interface AddTaskRequest {
  task_type: string
  interval_seconds: number
}

// ---- Chat ----

export interface DebugLogEntry {
  step: string
  status: string
  elapsed_ms?: number
  tool?: string
  detail?: string
  model?: string
  provider?: string
  tools_registered?: string[]
  tool_calls_requested?: string[]
  result_size?: number
  truncated?: boolean
  args?: Record<string, unknown>
  total_ms?: number
  tools_used?: number
  answer_length?: number
  direct_answer?: boolean
  response_preview?: string
}

export interface ChatCitation {
  tool: string
  label: string
  summary: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  citations?: ChatCitation[]
  debug_logs?: DebugLogEntry[]
}

export interface ChatRequest {
  message: string
}

export interface ChatResponse {
  answer: string
  citations: ChatCitation[]
  tool_results: ToolResult[]
  debug_logs: DebugLogEntry[]
}

export interface ToolResult {
  tool: string
  result: string
}

// ---- WebSocket Chat ----

export interface WsChatMessage {
  message: string
}

export interface WsChatResponse {
  type: 'answer' | 'error'
  content: string
  tool_results?: ToolResult[]
}

// ---- Dictionary: Parameters ----

export interface ParameterDefinition {
  id: string
  name: string
  unit: string
  location: string
  normal_range: [number, number]
  source: string
  update_freq: string
}

export interface ParameterListResponse {
  parameters: ParameterDefinition[]
  total: number
}

// ---- Dictionary: Baselines ----

export interface BaselineConfig {
  parameter_id: string
  parameter_name: string
  model_type: string
  features: string[]
  accuracy: number
}

export interface BaselineListResponse {
  baselines: BaselineConfig[]
  total: number
}

// ---- Dictionary: Benchmark Indicators ----

export interface BenchmarkIndicator {
  id: string
  name: string
  unit: string
  source: string
  peer_avg: number
}

export interface BenchmarkIndicatorListResponse {
  indicators: BenchmarkIndicator[]
  total: number
}

// ---- Knowledge: Models ----

export interface ModelEntry {
  id: string
  name: string
  url: string
  method: string
  input_params: string[]
  output_format: string
  status: 'online' | 'offline'
  last_check: string
}

export interface ModelListResponse {
  models: ModelEntry[]
  total: number
}

export interface ModelHealthResponse {
  id: string
  status: string
  last_check: string
}

// ---- Knowledge: Maintenance ----

export interface MaintenanceKnowledge {
  id: string
  title: string
  category: string
  type: string
  equipment?: string
  severity?: string
  keywords: string[]
  symptoms?: string
  analysis?: string
  solution?: string
  prevention?: string
  updated: string
  source?: 'manual' | 'upload' | 'vector'
  content_type?: 'text' | 'document' | 'image'
}

export interface MaintenanceListResponse {
  items: MaintenanceKnowledge[]
  total: number
}

// ---- Knowledge: Vector KB Sources ----

// ---- Knowledge: Wiki 技术知识库 ----

export type WikiEntryType = 'content_summary' | 'entity' | 'concept' | 'comparative' | 'overview'

export interface WikiEntryMeta {
  id: string
  title: string
  type: WikiEntryType
  category: string
  tags: string[]
  equipment?: string
  severity?: string
  source_file?: string
  concept_subcategory?: string
  related_entries?: string[]
  created: string
  updated: string
}

export interface WikiEntry extends WikiEntryMeta {
  content: string
}

export interface WikiEntryListResponse {
  entries: WikiEntryMeta[]
  total: number
  page: number
  page_size: number
}

export interface WikiStatsResponse {
  total_entries: number
  by_type: Record<string, number>
  by_category: Record<string, number>
  recent_updates: WikiEntryMeta[]
}

export interface WikiUploadResult {
  success: boolean
  source_file: string
  entries_created: number
  entry_ids: string[]
  processing_time_ms: number
  message: string
}

export interface WikiQAResponse {
  answer: string
  citations: WikiCitation[]
  processing_time_ms?: number
}

export interface WikiCitation {
  entry_id: string
  title: string
  type: WikiEntryType
  category: string
  relevance_score?: number
  snippet: string
}

export interface RawFileInfo {
  name: string
  size: number
  modified: string
  type: string
}

export interface WikiGraphNode {
  id: string
  name: string
  type: WikiEntryType
  category: string
  color: string
  label: string
  degree: number
}

export interface WikiGraphEdge {
  source: string
  target: string
  weight: number
}

export interface WikiGraphData {
  nodes: WikiGraphNode[]
  edges: WikiGraphEdge[]
}

// ---- Knowledge: Vector KB Sources ----

export interface VectorKBSource {
  id: string
  name: string
  url: string
  embedding_model: string
  doc_count: number
  status: 'connected' | 'disconnected'
}

export interface VectorKBSourceListResponse {
  sources: VectorKBSource[]
  total: number
}

// ---- Model connectivity test ----

export interface ModelTestResult {
  success: boolean
  status_code?: number
  latency_ms?: number
  last_check?: string
  message?: string
  error?: string
}

// ---- Knowledge: Expert Rules ----

export interface ExpertRule {
  id: string
  name: string
  condition: string
  conclusion: string
  confidence: number
  severity?: string
  related_params?: string[]
  recommended_actions?: string
  symptom_tag?: string
  subsystem_tag?: string
  root_cause_tag?: string
  trigger_rule_id?: string
}

export interface ExpertRuleListResponse {
  rules: ExpertRule[]
  total: number
}

// ---- Knowledge: Causal Graph ----

export interface CausalNode {
  id: string
  name: string
  type: 'symptom' | 'subsystem' | 'root_cause' | 'trigger_rule'
}

export interface CausalEdge {
  source: string
  target: string
  weight: number
}

export interface CausalGraph {
  nodes: CausalNode[]
  edges: CausalEdge[]
}

// ---- Workflow ----

export interface WorkflowNode {
  id: string
  type: string
  label: string
  position: { x: number; y: number }
  config: Record<string, unknown>
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
}

export interface WorkflowDefinition {
  id: string
  name: string
  description: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  updated_at?: string
}

export interface NodeConfigField {
  key: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'multiselect' | 'number'
  default?: unknown
  options?: string[]
}

export interface NodeTypeDef {
  type: string
  label: string
  category: string
  icon: string
  color: string
  description: string
  config_fields: NodeConfigField[]
}

export interface ExecutionLogEntry {
  node: string
  type: string
  label: string
  status: 'ok' | 'error' | 'skipped'
  elapsed_ms: number
  detail?: string
}

export interface ExecutionResult {
  status: string
  total_ms: number
  logs: ExecutionLogEntry[]
  final_output: unknown
  state_keys: string[]
}

// ---- Root Cause Analysis ----

export interface AnomalyItem {
  param: string
  value: number
  threshold: number
  direction: string
}

export interface TriggeredRule {
  rule_id: string
  rule_name: string
  confidence: number
  conclusion: string
  severity: string
  symptom_tag: string
  subsystem_tag: string
  root_cause_tag: string
  trigger_rule_id: string
  matched_params: Record<string, { value: number; threshold: number; op: string }>
  recommended_actions: string
}

export interface DiagnosisChain {
  chain: string[]
  confidence: number
  severity: string
  rule_id: string
  rule_name: string
  conclusion: string
  recommended_actions: string
}

export interface WikiRef {
  id: string
  title: string
  snippet: string
  relevance_score?: number
}

export interface RootCauseAnalysisResult {
  status: 'triggered' | 'no_rule_matched'
  anomalies: AnomalyItem[]
  triggered_rules: TriggeredRule[]
  diagnosis_chains: DiagnosisChain[]
  wiki_references: WikiRef[]
  suggestions: string[]
  elapsed_ms: number
}

// ---- Generic API Response ----

export interface ApiErrorResponse {
  error: string
}

export interface ApiSuccessResponse {
  success: boolean
  message?: string
}
