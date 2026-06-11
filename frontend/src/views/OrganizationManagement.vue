<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import * as api from '../api'
import type { Organization } from '../types'

const loading = ref(false)
const orgTree = ref<Organization[]>([])
const orgFlat = ref<Organization[]>([])
const selectedOrg = ref<Organization | null>(null)

// 新增/编辑对话框
const showOrgDialog = ref(false)
const dialogMode = ref<'add' | 'edit'>('add')
const orgForm = reactive({
  id: 0,
  name: '',
  parent_id: null as number | null,
  code: '',
  description: '',
  sort_order: 0,
})

async function loadOrgTree() {
  loading.value = true
  try {
    const res = await api.getOrgTree()
    orgTree.value = res.organizations || []
  } catch { ElMessage.error('加载组织树失败') }
  finally { loading.value = false }
}

async function loadOrgFlat() {
  try {
    const res = await api.getOrgFlat()
    orgFlat.value = res.organizations || []
  } catch { /* ignore */ }
}

function handleNodeClick(data: Organization) {
  selectedOrg.value = data
}

function openAddDialog(parentId: number | null = null) {
  dialogMode.value = 'add'
  Object.assign(orgForm, {
    id: 0, name: '', parent_id: parentId, code: '',
    description: '', sort_order: 0,
  })
  showOrgDialog.value = true
}

function openEditDialog() {
  if (!selectedOrg.value) { ElMessage.warning('请先选择一个组织'); return }
  const org = selectedOrg.value
  dialogMode.value = 'edit'
  Object.assign(orgForm, {
    id: org.id, name: org.name, parent_id: org.parent_id,
    code: org.code, description: org.description, sort_order: org.sort_order,
  })
  showOrgDialog.value = true
}

async function handleSaveOrg() {
  if (!orgForm.name) { ElMessage.warning('请填写组织名称'); return }
  try {
    if (dialogMode.value === 'add') {
      await api.createOrg({
        name: orgForm.name,
        parent_id: orgForm.parent_id,
        code: orgForm.code,
        description: orgForm.description,
      })
      ElMessage.success('组织创建成功')
    } else {
      await api.updateOrg(orgForm.id, {
        name: orgForm.name,
        parent_id: orgForm.parent_id,
        code: orgForm.code,
        description: orgForm.description,
        sort_order: orgForm.sort_order,
      })
      ElMessage.success('组织信息已更新')
    }
    showOrgDialog.value = false
    selectedOrg.value = null
    await loadOrgTree()
    await loadOrgFlat()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleDelete() {
  if (!selectedOrg.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除组织"${selectedOrg.value.name}"？该组织下不能有子组织或用户。`,
      '确认删除', { type: 'warning' }
    )
    await api.deleteOrg(selectedOrg.value!.id)
    ElMessage.success('组织已删除')
    selectedOrg.value = null
    await loadOrgTree()
    await loadOrgFlat()
  } catch { /* cancelled */ }
}

// el-tree props
const treeProps = {
  children: 'children',
  label: 'name',
}

onMounted(() => {
  loadOrgTree()
  loadOrgFlat()
})
</script>

<template>
  <div class="org-management-page">
    <h2 style="margin: 0 0 16px; font-size: 20px;">组织管理</h2>

    <div style="display: flex; gap: 16px;">
      <!-- 左侧：组织树 -->
      <el-card shadow="never" style="width: 360px; flex-shrink: 0;">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>组织架构</span>
            <el-button type="primary" size="small" :icon="Plus" @click="openAddDialog()">新增根组织</el-button>
          </div>
        </template>
        <el-tree
          :data="orgTree"
          :props="treeProps"
          node-key="id"
          highlight-current
          default-expand-all
          @node-click="handleNodeClick"
          v-loading="loading"
        >
          <template #default="{ node, data }">
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
              <span>{{ data.name }}</span>
              <el-button size="small" link type="primary" :icon="Plus"
                         @click.stop="openAddDialog(data.id)" title="新增子组织" />
            </div>
          </template>
        </el-tree>
      </el-card>

      <!-- 右侧：组织详情 -->
      <el-card shadow="never" style="flex: 1;">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>{{ selectedOrg ? selectedOrg.name : '组织详情' }}</span>
            <div v-if="selectedOrg">
              <el-button size="small" :icon="Plus" @click="openAddDialog(selectedOrg.id)">新增子组织</el-button>
              <el-button size="small" :icon="Edit" @click="openEditDialog">编辑</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="handleDelete">删除</el-button>
            </div>
          </div>
        </template>

        <div v-if="selectedOrg">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="组织名称">{{ selectedOrg.name }}</el-descriptions-item>
            <el-descriptions-item label="组织编码">{{ selectedOrg.code || '-' }}</el-descriptions-item>
            <el-descriptions-item label="上级组织">
              {{ selectedOrg.parent_id ? orgFlat.find(o => o.id === selectedOrg!.parent_id)?.name || '-' : '（顶级）' }}
            </el-descriptions-item>
            <el-descriptions-item label="排序">{{ selectedOrg.sort_order }}</el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{ selectedOrg.description || '-' }}</el-descriptions-item>
          </el-descriptions>

          <!-- 子组织列表 -->
          <div v-if="selectedOrg.children && selectedOrg.children.length > 0" style="margin-top: 20px;">
            <h4 style="margin: 0 0 8px;">下级组织 ({{ selectedOrg.children.length }})</h4>
            <el-table :data="selectedOrg.children" size="small" stripe>
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="code" label="编码" width="120" />
              <el-table-column label="子组织数" width="100">
                <template #default="{ row }">{{ row.children?.length || 0 }}</template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <el-empty v-else description="请在左侧选择一个组织" />
      </el-card>
    </div>

    <!-- 新增/编辑组织对话框 -->
    <el-dialog v-model="showOrgDialog"
               :title="dialogMode === 'add' ? '新增组织' : '编辑组织'"
               width="480px">
      <el-form :model="orgForm" label-width="90px">
        <el-form-item label="组织名称">
          <el-input v-model="orgForm.name" placeholder="如 运维部" />
        </el-form-item>
        <el-form-item label="上级组织">
          <el-select v-model="orgForm.parent_id" clearable placeholder="无（顶级组织）" style="width: 100%;">
            <el-option v-for="org in orgFlat" :key="org.id" :label="org.name" :value="org.id"
                       :disabled="dialogMode === 'edit' && org.id === orgForm.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="组织编码">
          <el-input v-model="orgForm.code" placeholder="如 OPS" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="orgForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showOrgDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveOrg">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.org-management-page {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
