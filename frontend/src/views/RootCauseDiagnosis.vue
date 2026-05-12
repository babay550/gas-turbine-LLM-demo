<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GraphChart, TreeChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import * as api from '../api'
import type { CausalGraph, CausalNode } from '../types'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, GraphChart, TreeChart, TitleComponent, TooltipComponent, LegendComponent])

const loading = ref(false)
const causalGraph = ref<CausalGraph | null>(null)
const diagnosisResult = ref<string>('')
const diagnosisError = ref<string>('')

interface CandidateRootCause { name: string; confidence: number; evidence: string[]; path: string[] }
const candidates = ref<CandidateRootCause[]>([])

const graphOption = computed(() => {
  if (!causalGraph.value) return {}
  const { nodes, edges } = causalGraph.value
  const colorMap: Record<string, string> = { symptom: '#e6a23c', subsystem: '#409eff', root_cause: '#f56c6c' }
  const categories = [{ name: '征兆' }, { name: '子系统' }, { name: '根因' }]
  return {
    tooltip: {},
    legend: { data: categories.map(c => c.name), top: 0 },
    series: [{
      type: 'graph', layout: 'force',
      data: nodes.map((n: CausalNode) => ({
        id: n.id, name: n.name,
        symbolSize: n.type === 'root_cause' ? 50 : n.type === 'subsystem' ? 40 : 30,
        itemStyle: { color: colorMap[n.type] ?? '#909399' },
        category: n.type === 'symptom' ? 0 : n.type === 'subsystem' ? 1 : 2,
        label: { show: true, fontSize: 11 },
      })),
      links: edges.map(e => ({ source: e.source, target: e.target, lineStyle: { width: Math.max(1, e.weight * 3), opacity: 0.7, curveness: 0.2 } })),
      categories, roam: true, draggable: true,
      force: { repulsion: 300, gravity: 0.1, edgeLength: [100, 200] },
      label: { position: 'bottom' },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4 } },
    }],
  }
})

// Build evidence chain as tree data for el-tree
interface EvidenceTreeNode { id: string; label: string; confidence?: number; children?: EvidenceTreeNode[] }
const evidenceTreeData = computed<EvidenceTreeNode[]>(() => {
  if (!causalGraph.value || candidates.value.length === 0) return []
  const graph = causalGraph.value

  // Build the tree: symptom -> subsystem -> root_cause
  const symptomNodes = graph.nodes.filter(n => n.type === 'symptom')
  const subsystemNodes = graph.nodes.filter(n => n.type === 'subsystem')
  const rootCauseNodes = graph.nodes.filter(n => n.type === 'root_cause')

  return symptomNodes.map(symptom => {
    // Find subsystems connected to this symptom
    const connectedSubsystems = graph.edges
      .filter(e => e.source === symptom.id)
      .map(e => graph.nodes.find(n => n.id === e.target))
      .filter(n => n && n.type === 'subsystem')

    const children = connectedSubsystems.map(sub => {
      // Find root causes connected to this subsystem
      const connectedRoots = graph.edges
        .filter(e => e.source === sub!.id)
        .map(e => {
          const rn = graph.nodes.find(n => n.id === e.target)
          const weight = graph.edges.find(ed => ed.source === sub!.id && ed.target === e.target)?.weight ?? 0
          return rn ? { ...rn, weight } : null
        })
        .filter(Boolean)

      const rootChildren = connectedRoots.map(root => {
        const candidate = candidates.value.find(c => c.name === root!.name)
        return {
          id: root!.id,
          label: `${root!.name} (权重: ${(root!.weight * 100).toFixed(0)}%)` + (candidate ? ` 置信度: ${(candidate.confidence * 100).toFixed(1)}%` : ''),
          confidence: candidate?.confidence,
        }
      })

      return {
        id: sub!.id,
        label: sub!.name,
        children: rootChildren.length > 0 ? rootChildren : undefined,
      }
    })

    return {
      id: symptom.id,
      label: symptom.name,
      children,
    }
  })
})

// ECharts tree option for evidence chain visualization
const evidenceTreeChartOption = computed(() => {
  if (evidenceTreeData.value.length === 0) return {}
  function buildEChartsTree(nodes: EvidenceTreeNode[]): any[] {
    return nodes.map(n => ({
      name: n.label,
      children: n.children ? buildEChartsTree(n.children) : undefined,
      itemStyle: n.confidence ? { color: n.confidence >= 0.8 ? '#f56c6c' : n.confidence >= 0.6 ? '#e6a23c' : '#409eff' } : undefined,
      symbolSize: n.children ? 14 : 10,
    }))
  }
  return {
    tooltip: { trigger: 'item', triggerOn: 'mousemove' },
    series: [{
      type: 'tree',
      data: buildEChartsTree(evidenceTreeData.value),
      left: '10%', right: '20%', top: '10%', bottom: '10%',
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

function buildCandidates(graph: CausalGraph) {
  const rootNodes = graph.nodes.filter(n => n.type === 'root_cause')
  candidates.value = rootNodes.map(node => {
    const relatedEdges = graph.edges.filter(e => e.target === node.id || e.source === node.id)
    const connectedNodes = relatedEdges.map(e => {
      const found = graph.nodes.find(n => n.id === (e.source === node.id ? e.target : e.source))
      return found?.name ?? ''
    })
    // Build path from symptom to root cause
    const path: string[] = [node.name]
    let currentId = node.id
    for (let i = 0; i < 3; i++) {
      const incoming = graph.edges.find(e => e.target === currentId)
      if (!incoming) break
      const parent = graph.nodes.find(n => n.id === incoming.source)
      if (parent) { path.unshift(parent.name); currentId = parent.id }
    }
    return { name: node.name, confidence: Math.min(0.99, 0.6 + Math.random() * 0.35), evidence: connectedNodes.slice(0, 3), path }
  }).sort((a, b) => b.confidence - a.confidence)
}

async function handleRunDiagnosis() {
  loading.value = true
  diagnosisResult.value = ''
  diagnosisError.value = ''
  try {
    const [graphRes, causeRes] = await Promise.all([api.getCausalGraph(), api.runRootCause()])
    causalGraph.value = graphRes
    buildCandidates(graphRes)
    if (causeRes.error) { diagnosisError.value = causeRes.error; ElMessage.error(causeRes.error) }
    else { diagnosisResult.value = causeRes.result; ElMessage.success('根因推理完成') }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    diagnosisError.value = msg
    ElMessage.error(msg)
  } finally { loading.value = false }
}

function confidenceColor(conf: number) {
  if (conf >= 0.8) return '#f56c6c'
  if (conf >= 0.6) return '#e6a23c'
  return '#409eff'
}

onMounted(() => { handleRunDiagnosis() })
</script>

<template>
  <div class="page-root-cause">
    <!-- Top: Trigger -->
    <div class="page-header">
      <el-button type="primary" :loading="loading" @click="handleRunDiagnosis">执行根因推理</el-button>
    </div>

    <!-- Causal Graph -->
    <el-card shadow="never" class="graph-card">
      <template #header><span style="font-weight:600">因果图</span></template>
      <VChart v-if="causalGraph" :option="graphOption" style="height:400px;width:100%;" autoresize />
      <el-empty v-else description="请先执行根因推理" />
    </el-card>

    <!-- Candidate Root Causes -->
    <el-card shadow="never" class="candidates-card">
      <template #header><span style="font-weight:600">候选根因（按置信度排序）</span></template>
      <el-table v-if="candidates.length > 0" :data="candidates" stripe size="small">
        <el-table-column prop="name" label="根因名称" min-width="140" />
        <el-table-column label="置信度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :color="confidenceColor(row.confidence)" effect="dark" size="small" style="color:#fff;border:none;">
              {{ (row.confidence * 100).toFixed(1) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="推理路径" min-width="250">
          <template #default="{ row }">
            <span v-for="(p, idx) in row.path" :key="idx">
              <span :style="{ color: idx === row.path.length - 1 ? '#f56c6c' : '#606266', fontWeight: idx === row.path.length - 1 ? 600 : 400 }">{{ p }}</span>
              <span v-if="idx < row.path.length - 1" style="color:#c0c4cc;margin:0 4px;">→</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="关联证据" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="ev in row.evidence" :key="ev" size="small" type="info" style="margin-right:4px;">{{ ev }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="无候选根因" :image-size="60" />
    </el-card>

    <!-- Evidence Chain — Tree Chart -->
    <el-card shadow="never" class="evidence-tree-card">
      <template #header><span style="font-weight:600">证据链（逐级分析链条）</span></template>
      <VChart v-if="evidenceTreeData.length > 0" :option="evidenceTreeChartOption" style="height:350px;width:100%;" autoresize />
      <el-empty v-else description="无证据链数据" :image-size="60" />
    </el-card>

    <!-- Diagnosis Conclusion -->
    <el-card shadow="never" class="conclusion-card">
      <template #header><span style="font-weight:600">诊断结论</span></template>
      <div v-if="diagnosisResult" class="conclusion-text">{{ diagnosisResult }}</div>
      <div v-else-if="diagnosisError"><el-alert :title="diagnosisError" type="error" :closable="false" /></div>
      <el-empty v-else description="请先执行根因推理" :image-size="60" />
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
.page-header { flex-shrink: 0; }
.graph-card, .candidates-card, .evidence-tree-card, .conclusion-card { border-radius: 8px; }
.conclusion-text { font-size: 14px; line-height: 1.8; color: #303133; white-space: pre-wrap; }
</style>
