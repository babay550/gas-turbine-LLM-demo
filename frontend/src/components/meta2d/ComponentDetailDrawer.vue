<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { realtimeStore, warningStore } from '../../stores'
import { COMPONENTS } from './config'
import type { ComponentDef, ScadaParamDef } from './config'
import type { Warning } from '../../types'

const props = defineProps<{
  visible: boolean
  componentId: string | null
}>()

const emit = defineEmits<{ 'update:visible': [val: boolean] }>()

const router = useRouter()

const compDef = computed<ComponentDef | undefined>(() =>
  COMPONENTS.find(c => c.id === props.componentId),
)

interface ParamRow {
  key: string
  label: string
  value: number | null
  unit: string
  normalRange: [number, number]
  outOfRange: boolean
}

const paramRows = computed<ParamRow[]>(() => {
  const comp = compDef.value
  if (!comp) return []
  const params = realtimeStore.data?.parameters ?? {}

  return comp.scadaParams.map((p: ScadaParamDef) => {
    const val = params[p.key] ?? null
    const outOfRange =
      val != null && (val < p.normalRange[0] || val > p.normalRange[1])
    return { key: p.key, label: p.label, value: val, unit: p.unit, normalRange: p.normalRange, outOfRange }
  })
})

const relatedWarnings = computed<Warning[]>(() => {
  const comp = compDef.value
  if (!comp) return []
  const keys = comp.scadaParams.map(p => p.key)
  return (warningStore.list as Warning[]).filter(w =>
    keys.some(k => w.parameter === k || w.message?.includes(comp.label)),
  )
})

function formatRange(range: [number, number]) {
  return `${range[0]} ~ ${range[1]}`
}

function navigateTo(path: string) {
  emit('update:visible', false)
  router.push(path)
}
</script>

<template>
  <el-drawer
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    direction="rtl"
    size="380px"
    :title="compDef ? `${compDef.label} / ${compDef.subtitle}` : ''"
  >
    <template v-if="compDef">
      <!-- SCADA Parameters -->
      <h4 class="section-title">实时参数</h4>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item
          v-for="row in paramRows"
          :key="row.key"
          :label="row.label"
        >
          <span :style="{ color: row.outOfRange ? '#f56c6c' : '#303133', fontWeight: row.outOfRange ? '600' : '400' }">
            {{ row.value != null ? row.value.toFixed(1) : '--' }}
          </span>
          <span class="param-unit">{{ row.unit }}</span>
          <el-tag v-if="row.outOfRange" type="danger" size="small" class="out-tag">偏离</el-tag>
          <div class="range-hint">{{ formatRange(row.normalRange) }}</div>
        </el-descriptions-item>
      </el-descriptions>

      <!-- Related Warnings -->
      <template v-if="relatedWarnings.length > 0">
        <h4 class="section-title" style="margin-top: 20px">关联预警</h4>
        <div
          v-for="w in relatedWarnings"
          :key="w.id"
          class="warning-row"
        >
          <el-tag
            :type="w.level === 'high' ? 'danger' : w.level === 'medium' ? 'warning' : 'info'"
            size="small"
          >
            {{ w.level }}
          </el-tag>
          <span class="warning-msg">{{ w.message }}</span>
        </div>
      </template>

      <!-- Quick Navigation -->
      <h4 class="section-title" style="margin-top: 20px">快捷操作</h4>
      <div class="nav-buttons">
        <el-button type="primary" @click="navigateTo('/efficiency')">能效分析</el-button>
        <el-button type="warning" @click="navigateTo('/loss')">耗差分析</el-button>
        <el-button type="danger" @click="navigateTo('/root-cause')">根因诊断</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 10px;
}

.param-unit {
  font-size: 12px;
  color: #909399;
  margin-left: 4px;
}

.out-tag {
  margin-left: 6px;
}

.range-hint {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 2px;
}

.warning-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid #f2f3f5;
}

.warning-row:last-child {
  border-bottom: none;
}

.warning-msg {
  font-size: 12px;
  color: #606266;
  flex: 1;
}

.nav-buttons {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.nav-buttons .el-button {
  width: 100%;
}
</style>
