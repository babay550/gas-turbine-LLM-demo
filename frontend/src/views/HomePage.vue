<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchRealtimeData, realtimeStore } from '../stores'
import { runEfficiency, runLoss, runBenchmark, analysisStore } from '../stores'
import { fetchWarnings, warningStore } from '../stores'
import { fetchExecutionLogs, scheduleStore } from '../stores'
import {
  TrendCharts,
  DataAnalysis,
  SetUp,
  WarningFilled,
  Document,
} from '@element-plus/icons-vue'
import GasTurbineCanvas from '../components/meta2d/GasTurbineCanvas.vue'
import ComponentDetailDrawer from '../components/meta2d/ComponentDetailDrawer.vue'

const router = useRouter()

// Status metric cards
const metrics = ref([
  { label: '发电功率', unit: 'MW', key: 'power_output', value: 0, delta: 0, icon: '⚡', color: '#409eff' },
  { label: '排气温度', unit: '°C', key: 'exhaust_temperature', value: 0, delta: 0, icon: '🌡', color: '#f56c6c' },
  { label: '燃料流量', unit: '万Nm³/h', key: 'gas_flow', value: 0, delta: 0, icon: '🔥', color: '#e6a23c' },
  { label: '负荷率', unit: '%', key: 'load_rate', value: 0, delta: 0, icon: '📊', color: '#67c23a' },
])

// Component detail drawer
const drawerVisible = ref(false)
const selectedComponent = ref<string | null>(null)

function handleComponentSelect(id: string) {
  selectedComponent.value = id
  drawerVisible.value = true
}

// Analysis loading state
const efficiencyLoading = ref(false)
const lossLoading = ref(false)
const benchmarkLoading = ref(false)

async function handleRunEfficiency() {
  efficiencyLoading.value = true
  await runEfficiency()
  efficiencyLoading.value = false
  if (analysisStore.efficiency) {
    ElMessage.success('能效分析完成')
    router.push('/efficiency')
  } else if (analysisStore.error) {
    ElMessage.error(analysisStore.error)
  }
}

async function handleRunLoss() {
  lossLoading.value = true
  await runLoss()
  lossLoading.value = false
  if (analysisStore.loss) {
    ElMessage.success('耗差分析完成')
    router.push('/loss')
  } else if (analysisStore.error) {
    ElMessage.error(analysisStore.error)
  }
}

async function handleRunBenchmark() {
  benchmarkLoading.value = true
  await runBenchmark()
  benchmarkLoading.value = false
  if (analysisStore.benchmark) {
    ElMessage.success('对标分析完成')
    router.push('/optimization')
  } else if (analysisStore.error) {
    ElMessage.error(analysisStore.error)
  }
}

// Recent warnings
const recentWarnings = computed(() => warningStore.list.slice(0, 5))

// Execution logs
const recentLogs = computed(() => scheduleStore.logs.slice(0, 8))

function warningLevelColor(level: string) {
  const map: Record<string, string> = { high: '#f56c6c', medium: '#e6a23c', low: '#409eff' }
  return map[level] || '#909399'
}

function logStatusType(status: string) {
  return status === 'success' ? 'success' : 'danger'
}

onMounted(async () => {
  await fetchRealtimeData()
  if (realtimeStore.data?.parameters) {
    const params = realtimeStore.data.parameters
    metrics.value[0].value = params['发电机有功功率'] ?? 0
    metrics.value[0].delta = params['发电机有功功率'] ? params['发电机有功功率'] - 210 : 0
    metrics.value[1].value = params['透平出口温度_T4'] ?? 0
    metrics.value[1].delta = params['透平出口温度_T4'] ? params['透平出口温度_T4'] - 550 : 0
    metrics.value[2].value = params['天然气瞬时流量'] ?? 0
    metrics.value[2].delta = params['天然气瞬时流量'] ? params['天然气瞬时流量'] - 5.0 : 0
    metrics.value[3].value = params['发电机有功功率'] ? Math.round(params['发电机有功功率'] / 220 * 1000) / 10 : 0
    metrics.value[3].delta = params['发电机有功功率'] ? Math.round((params['发电机有功功率'] / 220 - 1) * 100) / 1 : 0
  }
  await fetchWarnings()
  await fetchExecutionLogs(10)
})
</script>

<template>
  <div class="page-home">
    <!-- Top: Status Metric Cards -->
    <el-row :gutter="16" class="metrics-row">
      <el-col :span="6" v-for="m in metrics" :key="m.key">
        <el-card shadow="hover" class="metric-card" :body-style="{ padding: '16px' }">
          <div class="metric-header">
            <span class="metric-icon">{{ m.icon }}</span>
            <span class="metric-label">{{ m.label }}</span>
          </div>
          <div class="metric-value-row">
            <span class="metric-value" :style="{ color: m.color }">
              {{ m.value.toFixed(1) }}
            </span>
            <span class="metric-unit">{{ m.unit }}</span>
          </div>
          <div class="metric-delta" :style="{ color: m.delta >= 0 ? '#67c23a' : '#f56c6c' }">
            {{ m.delta >= 0 ? '↑' : '↓' }} {{ Math.abs(m.delta).toFixed(1) }} {{ m.unit }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Middle: Meta2d Schematic -->
    <el-card shadow="never" class="schematic-card">
      <template #header>
        <div style="display:flex;align-items:center;justify-content:space-between">
          <span style="font-weight: 600">燃机机组示意图</span>
          <span style="font-size:12px;color:#909399">点击组件查看详情</span>
        </div>
      </template>
      <GasTurbineCanvas @select="handleComponentSelect" />
    </el-card>

    <ComponentDetailDrawer
      v-model:visible="drawerVisible"
      :component-id="selectedComponent"
    />

    <!-- Bottom Row -->
    <el-row :gutter="16" class="bottom-row">
      <!-- Left: Quick Triggers -->
      <el-col :span="10">
        <el-card shadow="never" class="trigger-card">
          <template #header>
            <span style="font-weight: 600">快捷操作</span>
          </template>
          <div class="trigger-buttons">
            <el-button
              type="primary"
              :icon="TrendCharts"
              :loading="efficiencyLoading"
              @click="handleRunEfficiency"
              size="large"
            >
              执行能效分析
            </el-button>
            <el-button
              type="warning"
              :icon="DataAnalysis"
              :loading="lossLoading"
              @click="handleRunLoss"
              size="large"
            >
              执行耗差分析
            </el-button>
            <el-button
              type="success"
              :icon="SetUp"
              :loading="benchmarkLoading"
              @click="handleRunBenchmark"
              size="large"
            >
              执行对标分析
            </el-button>
          </div>
        </el-card>
      </el-col>

      <!-- Right: Warnings + Logs -->
      <el-col :span="14">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card shadow="never" class="info-card">
              <template #header>
                <div class="card-header-row">
                  <span style="font-weight: 600">最近预警</span>
                  <el-button link type="primary" @click="router.push('/warning')">查看全部</el-button>
                </div>
              </template>
              <div v-if="recentWarnings.length === 0" class="empty-tip">暂无预警</div>
              <div v-for="w in recentWarnings" :key="w.id" class="warning-item">
                <el-tag :color="warningLevelColor(w.level)" effect="dark" size="small" style="color:#fff;border:none;">
                  {{ w.level }}
                </el-tag>
                <span class="warning-text">{{ w.message }}</span>
              </div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never" class="info-card">
              <template #header>
                <span style="font-weight: 600">执行日志</span>
              </template>
              <div v-if="recentLogs.length === 0" class="empty-tip">暂无日志</div>
              <div v-for="(log, idx) in recentLogs" :key="idx" class="log-item">
                <el-tag :type="logStatusType(log.status)" size="small">{{ log.status }}</el-tag>
                <span class="log-task">{{ log.task_type }}</span>
                <span class="log-time">{{ log.timestamp?.slice(11, 19) }}</span>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.page-home {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

.metrics-row {
  flex-shrink: 0;
}

.metric-card {
  border-radius: 8px;
}

.metric-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.metric-icon {
  font-size: 18px;
}

.metric-label {
  font-size: 13px;
  color: #909399;
}

.metric-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.metric-unit {
  font-size: 13px;
  color: #909399;
}

.metric-delta {
  font-size: 12px;
  margin-top: 4px;
}

.schematic-card {
  flex-shrink: 0;
  border-radius: 8px;
}

.bottom-row {
  flex: 1;
  min-height: 0;
}

.trigger-card {
  border-radius: 8px;
  height: 100%;
}

.trigger-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.trigger-buttons .el-button {
  width: 100%;
}

.info-card {
  border-radius: 8px;
  height: 100%;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-tip {
  text-align: center;
  color: #c0c4cc;
  padding: 20px 0;
  font-size: 13px;
}

.warning-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid #f2f3f5;
}

.warning-item:last-child {
  border-bottom: none;
}

.warning-text {
  font-size: 12px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 0;
  border-bottom: 1px solid #f2f3f5;
  font-size: 12px;
}

.log-item:last-child {
  border-bottom: none;
}

.log-task {
  flex: 1;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-time {
  color: #c0c4cc;
  flex-shrink: 0;
}
</style>
