<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { fetchWarnings, fetchWarningDetail, warningStore } from '../stores'
import type { Warning, WarningDetail } from '../types'

const activeFilter = ref('all')
const selectedWarning = ref<WarningDetail | null>(null)
const detailLoading = ref(false)
const detailVisible = ref(false)

const filters = [
  { label: '全部', value: 'all' },
  { label: '活跃', value: 'active' },
  { label: '已处理', value: 'resolved' },
]

async function handleFilterChange(filter: string) {
  activeFilter.value = filter
  await fetchWarnings(filter === 'all' ? undefined : filter)
}

async function handleRowClick(row: Warning) {
  detailLoading.value = true
  detailVisible.value = true
  await fetchWarningDetail(row.id)
  selectedWarning.value = warningStore.currentDetail
  detailLoading.value = false
}

function levelColor(level: string): string {
  const map: Record<string, string> = { high: '#f56c6c', medium: '#e6a23c', low: '#409eff' }
  return map[level] ?? '#909399'
}

function levelTagType(level: string): '' | 'warning' | 'danger' {
  if (level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return ''
}

function statusTagType(status: string): '' | 'success' {
  return status === 'resolved' ? 'success' : ''
}

onMounted(() => {
  fetchWarnings()
})
</script>

<template>
  <div class="page-warning">
    <!-- Top: Filter Tabs -->
    <div class="filter-row">
      <el-radio-group v-model="activeFilter" @change="handleFilterChange">
        <el-radio-button v-for="f in filters" :key="f.value" :value="f.value">
          {{ f.label }}
        </el-radio-button>
      </el-radio-group>
      <span class="total-count">共 {{ warningStore.total }} 条预警</span>
    </div>

    <!-- Middle: Warning Table -->
    <el-card shadow="never" class="table-card">
      <el-table
        v-loading="warningStore.loading"
        :data="warningStore.list"
        stripe
        size="small"
        @row-click="handleRowClick"
        style="cursor: pointer;"
        max-height="400"
      >
        <el-table-column label="级别" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.level)" size="small" effect="dark">
              {{ row.level === 'high' ? '高' : row.level === 'medium' ? '中' : '低' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column prop="message" label="预警信息" min-width="250" show-overflow-tooltip />
        <el-table-column prop="parameter" label="参数" width="120" />
        <el-table-column label="当前值/阈值" width="140" align="center">
          <template #default="{ row }">
            <span :style="{ color: levelColor(row.level) }">{{ row.value }}</span>
            <span style="color:#c0c4cc"> / </span>
            <span>{{ row.threshold }} {{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="time" label="时间" width="170" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ row.status === 'active' ? '活跃' : '已处理' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Bottom: Detail Panel -->
    <el-dialog
      v-model="detailVisible"
      title="预警详情"
      width="600px"
      destroy-on-close
    >
      <div v-if="detailLoading" style="text-align:center;padding:40px;">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      </div>
      <div v-else-if="selectedWarning" class="detail-content">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="预警ID">{{ selectedWarning.id }}</el-descriptions-item>
          <el-descriptions-item label="级别">
            <el-tag :type="levelTagType(selectedWarning.level)" size="small" effect="dark">
              {{ selectedWarning.level }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="来源">{{ selectedWarning.source }}</el-descriptions-item>
          <el-descriptions-item label="参数">{{ selectedWarning.parameter }}</el-descriptions-item>
          <el-descriptions-item label="当前值">
            <span :style="{ color: levelColor(selectedWarning.level) }">{{ selectedWarning.value }} {{ selectedWarning.unit }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="阈值">{{ selectedWarning.threshold }} {{ selectedWarning.unit }}</el-descriptions-item>
          <el-descriptions-item label="状态" :span="2">
            <el-tag :type="statusTagType(selectedWarning.status)" size="small">
              {{ selectedWarning.status === 'active' ? '活跃' : '已处理' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="预警信息" :span="2">{{ selectedWarning.message }}</el-descriptions-item>
          <el-descriptions-item label="时间" :span="2">{{ selectedWarning.time }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="selectedWarning.suggestions?.length" class="detail-section">
          <h4>处理建议</h4>
          <ul>
            <li v-for="(s, idx) in selectedWarning.suggestions" :key="idx">{{ s }}</li>
          </ul>
        </div>

        <div v-if="selectedWarning.history?.length" class="detail-section">
          <h4>历史记录</h4>
          <el-table :data="selectedWarning.history" size="small" stripe>
            <el-table-column prop="time" label="时间" width="170" />
            <el-table-column prop="value" label="值" width="100" align="center" />
            <el-table-column prop="status" label="状态" width="100" align="center" />
          </el-table>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script lang="ts">
import { Loading } from '@element-plus/icons-vue'
export default { components: { Loading } }
</script>

<style scoped>
.page-warning {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow-y: auto;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.total-count {
  font-size: 13px;
  color: #909399;
}

.table-card {
  border-radius: 8px;
}

.detail-content {
  font-size: 14px;
}

.detail-section {
  margin-top: 16px;
}

.detail-section h4 {
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
}

.detail-section ul {
  padding-left: 20px;
  line-height: 1.8;
  color: #606266;
  font-size: 13px;
}
</style>
