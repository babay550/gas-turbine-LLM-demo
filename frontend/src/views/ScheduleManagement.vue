<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  fetchScheduleTasks,
  fetchExecutionLogs,
  addTask,
  removeTask,
  triggerTaskNow,
  scheduleStore,
} from '../stores'
import { ElMessage, ElMessageBox } from 'element-plus'

const newTaskType = ref('efficiency')
const newInterval = ref(3600)

const taskTypeOptions = [
  { label: '能效分析', value: 'efficiency' },
  { label: '耗差分析', value: 'loss' },
  { label: '对标分析', value: 'benchmark' },
  { label: '根因推理', value: 'root_cause' },
]

const intervalOptions = [
  { label: '每10分钟', value: 600 },
  { label: '每30分钟', value: 1800 },
  { label: '每1小时', value: 3600 },
  { label: '每6小时', value: 21600 },
  { label: '每12小时', value: 43200 },
  { label: '每天', value: 86400 },
]

async function handleAddTask() {
  if (!newTaskType.value) return
  await addTask(newTaskType.value, newInterval.value)
  if (scheduleStore.error) {
    ElMessage.error(scheduleStore.error)
  } else {
    ElMessage.success('调度任务已添加')
  }
}

async function handleDelete(taskType: string) {
  try {
    await ElMessageBox.confirm(`确定删除调度任务 "${taskType}"?`, '确认', {
      type: 'warning',
    })
    await removeTask(taskType)
    if (scheduleStore.error) {
      ElMessage.error(scheduleStore.error)
    } else {
      ElMessage.success('任务已删除')
    }
  } catch {
    // cancelled
  }
}

async function handleTriggerNow(taskType: string) {
  await triggerTaskNow(taskType)
  if (scheduleStore.error) {
    ElMessage.error(scheduleStore.error)
  } else {
    ElMessage.success(`已触发: ${taskType}`)
    await fetchExecutionLogs(20)
  }
}

function formatInterval(seconds: number): string {
  if (seconds < 3600) return `每${Math.floor(seconds / 60)}分钟`
  if (seconds < 86400) return `每${Math.floor(seconds / 3600)}小时`
  return `每${Math.floor(seconds / 86400)}天`
}

function logStatusType(status: string) {
  return status === 'success' ? 'success' : 'danger'
}

onMounted(async () => {
  await fetchScheduleTasks()
  await fetchExecutionLogs(20)
})
</script>

<template>
  <div class="page-schedule">
    <!-- Top: Add Task Form -->
    <el-card shadow="never" class="form-card">
      <template #header><span style="font-weight:600">添加调度任务</span></template>
      <el-form :inline="true" size="default">
        <el-form-item label="分析类型">
          <el-select v-model="newTaskType" placeholder="选择类型" style="width: 160px;">
            <el-option
              v-for="opt in taskTypeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="执行间隔">
          <el-select v-model="newInterval" placeholder="选择间隔" style="width: 160px;">
            <el-option
              v-for="opt in intervalOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="scheduleStore.loading" @click="handleAddTask">
            添加任务
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Middle: Tasks Table -->
    <el-card shadow="never" class="table-card">
      <template #header><span style="font-weight:600">调度任务列表</span></template>
      <el-table v-loading="scheduleStore.loading" :data="scheduleStore.tasks" stripe size="small">
        <el-table-column prop="job_id" label="任务ID" width="200" show-overflow-tooltip />
        <el-table-column prop="task_type" label="分析类型" width="140">
          <template #default="{ row }">
            <el-tag size="small">{{ row.task_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="执行间隔" width="120" align="center">
          <template #default="{ row }">
            {{ formatInterval(row.interval_seconds) }}
          </template>
        </el-table-column>
        <el-table-column prop="next_run" label="下次执行" width="180" />
        <el-table-column prop="last_run" label="上次执行" width="180" />
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="handleTriggerNow(row.task_type)">
              立即执行
            </el-button>
            <el-button type="danger" link size="small" @click.stop="handleDelete(row.task_type)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Bottom: Execution Logs -->
    <el-card shadow="never" class="log-card">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-weight:600">执行日志</span>
          <el-button size="small" @click="fetchExecutionLogs(20)">刷新</el-button>
        </div>
      </template>
      <el-table :data="scheduleStore.logs" stripe size="small" max-height="300">
        <el-table-column prop="timestamp" label="时间" width="180" />
        <el-table-column prop="task_type" label="任务类型" width="140">
          <template #default="{ row }">
            <el-tag size="small">{{ row.task_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="trigger_type" label="触发方式" width="100" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="logStatusType(row.status)" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="result" label="结果" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.page-schedule {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow-y: auto;
}

.form-card, .table-card, .log-card {
  border-radius: 8px;
}
</style>
