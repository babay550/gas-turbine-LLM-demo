<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus, Delete, Key } from '@element-plus/icons-vue'
import * as api from '../api'
import type { UserInfo } from '../types'

const loading = ref(false)
const users = ref<UserInfo[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const roleFilter = ref('')

// 新增/编辑对话框
const showUserDialog = ref(false)
const dialogMode = ref<'add' | 'edit'>('add')
const userForm = reactive({
  id: 0,
  username: '',
  password: '',
  display_name: '',
  email: '',
  phone: '',
  role: 'viewer',
  org_id: null as number | null,
})

// 重置密码对话框
const showResetDialog = ref(false)
const resetUserId = ref(0)
const resetUsername = ref('')
const newPassword = ref('')

// 组织列表（用于下拉）
const orgList = ref<{ id: number; name: string }[]>([])

const roleOptions = [
  { value: 'admin', label: '管理员', color: '#f56c6c' },
  { value: 'engineer', label: '工程师', color: '#409eff' },
  { value: 'viewer', label: '观察者', color: '#909399' },
]

async function loadUsers() {
  loading.value = true
  try {
    const res = await api.getUsers({
      page: page.value,
      page_size: pageSize.value,
      search: search.value || undefined,
      role: roleFilter.value || undefined,
    })
    users.value = res.users
    total.value = res.total
  } catch (e: any) {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

async function loadOrgs() {
  try {
    const res = await api.getOrgFlat()
    orgList.value = res.organizations || []
  } catch { /* ignore */ }
}

function handleSearch() {
  page.value = 1
  loadUsers()
}

function handlePageChange(val: number) {
  page.value = val
  loadUsers()
}

function openAddDialog() {
  dialogMode.value = 'add'
  Object.assign(userForm, {
    id: 0, username: '', password: '', display_name: '',
    email: '', phone: '', role: 'viewer', org_id: null,
  })
  showUserDialog.value = true
}

function openEditDialog(user: UserInfo) {
  dialogMode.value = 'edit'
  Object.assign(userForm, {
    id: user.id, username: user.username, password: '',
    display_name: user.display_name, email: user.email,
    phone: user.phone, role: user.role, org_id: user.org_id,
  })
  showUserDialog.value = true
}

async function handleSaveUser() {
  if (!userForm.username) { ElMessage.warning('请填写用户名'); return }
  if (dialogMode.value === 'add' && !userForm.password) { ElMessage.warning('请填写密码'); return }

  try {
    if (dialogMode.value === 'add') {
      await api.createUser({
        username: userForm.username,
        password: userForm.password,
        display_name: userForm.display_name,
        email: userForm.email,
        phone: userForm.phone,
        role: userForm.role,
        org_id: userForm.org_id,
      })
      ElMessage.success('用户创建成功')
    } else {
      const data: Record<string, unknown> = {
        display_name: userForm.display_name,
        email: userForm.email,
        phone: userForm.phone,
        role: userForm.role,
        org_id: userForm.org_id,
      }
      if (userForm.password) data['password'] = userForm.password
      await api.updateUser(userForm.id, data)
      ElMessage.success('用户信息已更新')
    }
    showUserDialog.value = false
    loadUsers()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleDelete(user: UserInfo) {
  try {
    await ElMessageBox.confirm(`确定禁用用户"${user.display_name || user.username}"？`, '确认', { type: 'warning' })
    await api.deleteUser(user.id)
    ElMessage.success('用户已禁用')
    loadUsers()
  } catch { /* cancelled */ }
}

function openResetDialog(user: UserInfo) {
  resetUserId.value = user.id
  resetUsername.value = user.display_name || user.username
  newPassword.value = ''
  showResetDialog.value = true
}

async function handleResetPassword() {
  if (!newPassword.value) { ElMessage.warning('请输入新密码'); return }
  try {
    await api.resetUserPassword(resetUserId.value, newPassword.value)
    ElMessage.success('密码已重置')
    showResetDialog.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '重置失败')
  }
}

async function handleToggleRole(user: UserInfo, role: string) {
  try {
    await api.updateUserRole(user.id, role)
    ElMessage.success('角色已修改')
    loadUsers()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '修改失败')
  }
}

function getRoleTag(type: string) {
  const map: Record<string, string> = { admin: 'danger', engineer: '', viewer: 'info' }
  return map[type] || 'info'
}

function getRoleLabel(role: string) {
  return roleOptions.find(r => r.value === role)?.label || role
}

onMounted(() => {
  loadUsers()
  loadOrgs()
})
</script>

<template>
  <div class="user-management-page">
    <h2 style="margin: 0 0 16px; font-size: 20px;">用户管理</h2>

    <!-- 搜索栏 -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
        <el-input v-model="search" placeholder="搜索用户名/姓名" clearable style="width: 200px;"
                  @keyup.enter="handleSearch" />
        <el-select v-model="roleFilter" placeholder="角色筛选" clearable style="width: 130px;"
                   @change="handleSearch">
          <el-option label="管理员" value="admin" />
          <el-option label="工程师" value="engineer" />
          <el-option label="观察者" value="viewer" />
        </el-select>
        <el-button type="primary" @click="handleSearch" :icon="Refresh">查询</el-button>
        <div style="flex: 1;" />
        <el-button type="primary" :icon="Plus" @click="openAddDialog">新增用户</el-button>
      </div>
    </el-card>

    <!-- 用户列表 -->
    <el-card shadow="never">
      <el-table :data="users" v-loading="loading" stripe size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="display_name" label="姓名" width="120" />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-dropdown trigger="click" @command="(cmd: string) => handleToggleRole(row, cmd)">
              <el-tag :type="getRoleTag(row.role)" size="small" style="cursor: pointer;">
                {{ getRoleLabel(row.role) }}
              </el-tag>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="r in roleOptions" :key="r.value" :command="r.value"
                                    :disabled="r.value === row.role">
                    {{ r.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
        <el-table-column prop="org_name" label="组织" width="130">
          <template #default="{ row }">{{ row.org_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
        <el-table-column prop="phone" label="电话" width="120" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="160">
          <template #default="{ row }">{{ row.last_login?.replace('T', ' ')?.slice(0, 19) || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link @click="openEditDialog(row)">编辑</el-button>
            <el-button size="small" link type="warning" @click="openResetDialog(row)">重置密码</el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row)"
                       :disabled="row.username === 'admin'">禁用</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="display: flex; justify-content: flex-end; margin-top: 16px;">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 新增/编辑用户对话框 -->
    <el-dialog v-model="showUserDialog"
               :title="dialogMode === 'add' ? '新增用户' : '编辑用户'"
               width="520px">
      <el-form :model="userForm" label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="dialogMode === 'add' ? '密码' : '新密码'">
          <el-input v-model="userForm.password" type="password" show-password
                    :placeholder="dialogMode === 'add' ? '请输入密码' : '留空则不修改'" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="userForm.display_name" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role" style="width: 100%;">
            <el-option v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="组织">
          <el-select v-model="userForm.org_id" clearable placeholder="选择组织" style="width: 100%;">
            <el-option v-for="org in orgList" :key="org.id" :label="org.name" :value="org.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="userForm.phone" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUserDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveUser">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="showResetDialog" title="重置密码" width="400px">
      <p style="margin: 0 0 16px;">为用户 <strong>{{ resetUsername }}</strong> 设置新密码：</p>
      <el-input v-model="newPassword" type="password" show-password placeholder="输入新密码" />
      <template #footer>
        <el-button @click="showResetDialog = false">取消</el-button>
        <el-button type="primary" @click="handleResetPassword">确定重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-management-page {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
