<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GraphChart, TreeChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import * as api from '../api'
import type { CausalGraph, CausalNode, RootCauseAnalysisResult, DiagnosisChain, TriggeredRule } from '../types'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, GraphChart, TreeChart, TitleComponent, TooltipComponent, LegendComponent])

const loading = ref(false)
const causalGraph = ref<CausalGraph | null>(null)
const analysisResult = ref<RootCauseAnalysisResult | null>(null)
const diagnosisError = ref('')

// ---- 4-level causal graph ----

const graphOption = computed(() => {
  if (!causalGraph.value) return {}
  const { nodes, edges } = causalGraph.value
  const colorMap: Record<string, string> = {
    symptom: '#e6a23c',
    subsystem: '#409eff',
    root_cause: '#f56c6c',
    trigger_rule: '#9b59b6',
  }
  const categories = [
    { name: '征兆' },
    { name: '子系统' },
    { name: '根因' },
    { name: '触发规则' },
  ]
  const catIdx = (t: string) => t === 'symptom' ? 0 : t === 'subsystem' ? 1 : t === 'root_cause' ? 2 : 3
  const symSize = (t: string) => t === 'trigger_rule' ? 28 : t === 'root_cause' ? 42 : t === 'subsystem' ? 36 : 30

  return {
    tooltip: {
      formatter(params: any) {
        if (params.dataType === 'node') {
          return `<b>${params.name}</b><br/>类型: ${categories[catIdx(params.data?.category ?? 0)].name}`
        }
        return ''
      },
    },
    legend: { data: categories.map(c => c.name), top: 0 },
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes.map((n: CausalNode) => ({
        id: n.id,
        name: n.name,
        symbolSize: symSize(n.type),
        itemStyle: { color: colorMap[n.type] ?? '#909399' },
        category: catIdx(n.type),
        label: {
          show: true,
          fontSize: n.type === 'trigger_rule' ? 9 : 11,
          position: n.type === 'trigger_rule' ? 'bottom' : 'inside',
        },
      })),
      links: edges.map(e => ({
        source: e.source,
        target: e.target,
        lineStyle: {
          width: Math.max(1, e.weight * 3),
          opacity: 0.6,
          curveness: 0.15,
          type: e.weight < 0.5 ? 'dashed' : 'solid',
        },
      })),
      categories,
      roam: true,
      draggable: true,
      force: { repulsion: 400, gravity: 0.06, edgeLength: [80, 180], friction: 0.6 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4 } },
    }],
  }
})

// ---- Evidence tree (4-level: symptom → subsystem → root_cause → trigger_rule) ----

const evidenceTreeOption = computed(() => {
  const graph = causalGraph.value
  if (!graph || !analysisResult.value) return {}

  const chains = analysisResult.value.diagnosis_chains
  if (chains.length === 0) {
    // No triggered rules — show the full graph structure without highlights
    return buildFullTreeOption(graph)
  }

  // Build highlighted tree from triggered diagnosis chains
  function buildChainTree(chain: DiagnosisChain) {
    const levels = chain.chain // [symptom, subsystem, root_cause, trigger_rule]
    let node: any = {
      name: levels[levels.length - 1] + ` (${(chain.confidence * 100).toFixed(0)}%)`,
      itemStyle: { color: chain.confidence >= 0.85 ? '#f56c6c' : chain.confidence >= 0.75 ? '#e6a23c' : '#409eff' },
      symbolSize: 10,
    }
    for (let i = levels.length - 2; i >= 0; i--) {
      node = { name: levels[i], children: [node], symbolSize: i === 0 ? 14 : 12 }
    }
    return node
  }

  const data = chains.map(c => buildChainTree(c))

  return {
    tooltip: { trigger: 'item', triggerOn: 'mousemove' },
    series: [{
      type: 'tree',
      data,
      left: '8%', right: '25%', top: '8%', bottom: '8%',
      symbol: 'circle',
      orient: 'LR',
      label: { position: 'left', verticalAlign: 'middle', align: 'right', fontSize: 12 },
      leaves: { label: { position: 'right', align: 'left' } },
      lineStyle: { width: 2, curveness: 0.5 },
      expandAndCollapse: true,
      animationDuration: 550,
      animationDurationUpdate: 750,
    }],
  }
})

function buildFullTreeOption(graph: CausalGraph) {
  // Show full 4-level tree when no rules triggered
  const symptomNodes = graph.nodes.filter(n => n.type === 'symptom')

  function getChildren(parentId: string): any[] {
    return graph.edges
      .filter(e => e.source === parentId)
      .map(e => {
        const child = graph.nodes.find(n => n.id === e.target)
        if (!child) return null
        const colorMap: Record<string, string> = { symptom: '#e6a23c', subsystem: '#409eff', root_cause: '#f56c6c', trigger_rule: '#9b59b6' }
        return {
          name: child.name,
          itemStyle: { color: colorMap[child.type] || '#909399' },
          symbolSize: child.type === 'trigger_rule' ? 6 : child.type === 'root_cause' ? 10 : 8,
          children: getChildren(child.id),
        }
      })
      .filter(Boolean)
  }

  const data = symptomNodes.map(s => ({
    name: s.name,
    symbolSize: 14,
    children: getChildren(s.id),
  }))

  return {
    tooltip: { trigger: 'item', triggerOn: 'mousemove' },
    series: [{
      type: 'tree',
      data,
      left: '8%', right: '25%', top: '8%', bottom: '8%',
      symbol: 'circle',
      orient: 'LR',
      label: { position: 'left', verticalAlign: 'middle', align: 'right', fontSize: 12 },
      leaves: { label: { position: 'right', align: 'left' } },
      lineStyle: { width: 1.5, curveness: 0.5 },
      expandAndCollapse: true,
      initialTreeDepth: 3,
      animationDuration: 550,
    }],
  }
}

// ---- Run diagnosis ----

async function handleRunDiagnosis() {
  loading.value = true
  diagnosisError.value = ''
  analysisResult.value = null
  try {
    const [graphRes, diagRes] = await Promise.all([api.getCausalGraph(), api.runRootCause()])
    causalGraph.value = graphRes
    analysisResult.value = diagRes
    ElMessage.success(diagRes.status === 'triggered' ? `根因推理完成，触发 ${diagRes.triggered_rules.length} 条专家规则` : '根因推理完成，未触发专家规则')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    diagnosisError.value = msg
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function confidenceColor(conf: number) {
  if (conf >= 0.85) return '#f56c6c'
  if (conf >= 0.75) return '#e6a23c'
  return '#409eff'
}

function severityTagType(sev: string) {
  return sev === '高' ? 'danger' : sev === '中' ? 'warning' : 'info'
}

onMounted(() => { handleRunDiagnosis() })
</script>

<template>
  <div class="page-root-cause">
    <!-- Top: Trigger -->
    <div class="page-header">
      <el-button type="primary" :loading="loading" @click="handleRunDiagnosis">执行根因推理</el-button>
      <el-tag v-if="analysisResult" :type="analysisResult.status === 'triggered' ? 'danger' : 'info'" style="margin-left:12px;">
        {{ analysisResult.status === 'triggered' ? `触发 ${analysisResult.triggered_rules.length} 条专家规则` : '未触发专家规则' }}
        · 耗时 {{ analysisResult.elapsed_ms }} ms
      </el-tag>
    </div>

    <!-- 4-level Causal Graph -->
    <el-card shadow="never" class="graph-card">
      <template #header>
        <span style="font-weight:600">因果图（4级：征兆 → 子系统 → 根因 → 触发规则）</span>
      </template>
      <VChart v-if="causalGraph" :option="graphOption" style="height:420px;width:100%;" autoresize />
      <el-empty v-else description="请先执行根因推理" />
    </el-card>

    <!-- Triggered Rules (from actual analysis, not random) -->
    <el-card shadow="never" class="rules-card">
      <template #header><span style="font-weight:600">触发的专家规则（按置信度排序）</span></template>
      <el-table v-if="analysisResult && analysisResult.triggered_rules.length > 0" :data="analysisResult.triggered_rules" stripe size="small">
        <el-table-column prop="rule_name" label="规则名称" min-width="180" />
        <el-table-column label="置信度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :color="confidenceColor(row.confidence)" effect="dark" size="small" style="color:#fff;border:none;">
              {{ (row.confidence * 100).toFixed(1) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="严重度" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="severityTagType(row.severity)" size="small">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="诊断链路" min-width="250">
          <template #default="{ row }">
            <span style="color:#909399;font-size:12px;">
              {{ row.symptom_tag }} → {{ row.subsystem_tag }} → {{ row.root_cause_tag }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="conclusion" label="诊断结论" min-width="260" show-overflow-tooltip />
        <el-table-column label="异常参数" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="(info, param) in row.matched_params" :key="param" size="small" type="warning" style="margin:2px;">
              {{ param }} {{ info.op }} {{ info.threshold }} ({{ info.value }})
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="analysisResult" description="未触发任何专家规则" :image-size="60" />
      <el-empty v-else description="请先执行根因推理" :image-size="60" />
    </el-card>

    <!-- Evidence Chain — Tree Chart -->
    <el-card shadow="never" class="evidence-tree-card">
      <template #header><span style="font-weight:600">证据链（4级推理链条）</span></template>
      <VChart v-if="causalGraph && (analysisResult?.diagnosis_chains?.length || causalGraph)" :option="evidenceTreeOption" style="height:380px;width:100%;" autoresize />
      <el-empty v-else description="请先执行根因推理" :image-size="60" />
    </el-card>

    <!-- Diagnosis Chains Detail -->
    <el-card v-if="analysisResult && analysisResult.diagnosis_chains.length > 0" shadow="never" class="chains-card">
      <template #header><span style="font-weight:600">诊断链路详情</span></template>
      <el-timeline>
        <el-timeline-item
          v-for="chain in analysisResult.diagnosis_chains"
          :key="chain.rule_id"
          :type="chain.severity === '高' ? 'danger' : 'warning'"
          :timestamp="`置信度 ${(chain.confidence * 100).toFixed(1)}%`"
          placement="top"
        >
          <div style="margin-bottom:6px;">
            <span v-for="(step, idx) in chain.chain" :key="idx">
              <span :style="{ fontWeight: idx === chain.chain.length - 1 ? 600 : 400, color: idx === 0 ? '#e6a23c' : idx === 1 ? '#409eff' : idx === 2 ? '#f56c6c' : '#9b59b6' }">
                {{ step }}
              </span>
              <span v-if="idx < chain.chain.length - 1" style="color:#c0c4cc;margin:0 6px;">→</span>
            </span>
          </div>
          <div style="font-size:13px;color:#606266;">{{ chain.conclusion }}</div>
          <div v-if="chain.recommended_actions" style="margin-top:6px;font-size:12px;color:#909399;white-space:pre-line;">{{ chain.recommended_actions }}</div>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- Anomalies -->
    <el-card v-if="analysisResult && analysisResult.anomalies.length > 0" shadow="never" class="anomalies-card">
      <template #header><span style="font-weight:600">检测到的参数异常</span></template>
      <el-table :data="analysisResult.anomalies" stripe size="small">
        <el-table-column prop="param" label="参数" min-width="160" />
        <el-table-column label="当前值" width="120" align="center">
          <template #default="{ row }">
            <span style="color:#f56c6c;font-weight:600;">{{ row.value }}</span>
          </template>
        </el-table-column>
        <el-table-column label="阈值" width="120" align="center">
          <template #default="{ row }">
            {{ row.direction }} {{ row.threshold }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Wiki References -->
    <el-card v-if="analysisResult && analysisResult.wiki_references.length > 0" shadow="never" class="wiki-card">
      <template #header><span style="font-weight:600">相关技术知识</span></template>
      <el-table :data="analysisResult.wiki_references" stripe size="small">
        <el-table-column prop="title" label="词条标题" min-width="180" />
        <el-table-column prop="snippet" label="内容摘要" min-width="360" show-overflow-tooltip />
        <el-table-column label="相关度" width="90" align="center">
          <template #default="{ row }">
            {{ row.relevance_score ? (row.relevance_score).toFixed(1) : '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Suggestions -->
    <el-card v-if="analysisResult && analysisResult.suggestions.length > 0" shadow="never" class="suggestions-card">
      <template #header><span style="font-weight:600">诊断建议</span></template>
      <div class="suggestions-text">
        <div v-for="(s, idx) in analysisResult.suggestions" :key="idx" style="margin-bottom:4px;">{{ s }}</div>
      </div>
    </el-card>

    <!-- Error -->
    <el-card v-if="diagnosisError" shadow="never">
      <el-alert :title="diagnosisError" type="error" :closable="false" />
    </el-card>
  </div>
</template>

<style scoped>
.page-root-cause {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}
.page-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}
.graph-card,
.rules-card,
.evidence-tree-card,
.chains-card,
.anomalies-card,
.wiki-card,
.suggestions-card {
  border-radius: 8px;
}
.suggestions-text {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
}
</style>
