// ============================================================
// Vue Router — 路由配置 + 认证守卫
// ============================================================

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { isAuthenticated, fetchCurrentUser } from '../stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/HomePage.vue'),
    meta: { title: '首页' },
  },
  {
    path: '/efficiency',
    name: 'EfficiencyMonitor',
    component: () => import('../views/EfficiencyMonitor.vue'),
    meta: { title: '能效监测' },
  },
  {
    path: '/loss',
    name: 'LossAnalysis',
    component: () => import('../views/LossAnalysis.vue'),
    meta: { title: '耗差分析' },
  },
  {
    path: '/root-cause',
    name: 'RootCauseDiagnosis',
    component: () => import('../views/RootCauseDiagnosis.vue'),
    meta: { title: '根因诊断' },
  },
  {
    path: '/optimization',
    name: 'OperationOptimization',
    component: () => import('../views/OperationOptimization.vue'),
    meta: { title: '运营优化' },
  },
  {
    path: '/warning',
    name: 'WarningManagement',
    component: () => import('../views/WarningManagement.vue'),
    meta: { title: '预警管理' },
  },
  {
    path: '/schedule',
    name: 'ScheduleManagement',
    component: () => import('../views/ScheduleManagement.vue'),
    meta: { title: '调度管理' },
  },
  {
    path: '/data-import',
    name: 'DataImport',
    component: () => import('../views/DataImport.vue'),
    meta: { title: '数据导入', roles: ['admin', 'engineer'] },
  },
  {
    path: '/historical',
    name: 'HistoricalData',
    component: () => import('../views/HistoricalData.vue'),
    meta: { title: '历史分析' },
  },
  {
    path: '/dictionary',
    name: 'DataDictionary',
    component: () => import('../views/DataDictionary.vue'),
    meta: { title: '数据字典', roles: ['admin', 'engineer'] },
  },
  {
    path: '/knowledge',
    name: 'ModelKnowledge',
    component: () => import('../views/ModelKnowledge.vue'),
    meta: { title: '模型与知识库' },
  },
  {
    path: '/workflow',
    name: 'WorkflowEditor',
    component: () => import('../views/WorkflowEditor.vue'),
    meta: { title: '工作流编排', roles: ['admin', 'engineer'] },
  },
  {
    path: '/skills',
    name: 'SkillManagement',
    component: () => import('../views/SkillManagement.vue'),
    meta: { title: '技能管理', roles: ['admin', 'engineer'] },
  },
  {
    path: '/users',
    name: 'UserManagement',
    component: () => import('../views/UserManagement.vue'),
    meta: { title: '用户管理', roles: ['admin'] },
  },
  {
    path: '/organizations',
    name: 'OrganizationManagement',
    component: () => import('../views/OrganizationManagement.vue'),
    meta: { title: '组织管理', roles: ['admin'] },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 认证守卫
let userFetched = false

router.beforeEach(async (to) => {
  const title = (to.meta.title as string) ?? '燃气轮机运行优化智能体'
  document.title = `${title} - 燃气轮机运行优化智能体`

  // 公开路由直接放行
  if (to.meta.public) {
    // 已登录用户访问登录页 → 跳转首页
    if (to.path === '/login' && isAuthenticated()) {
      return { path: '/' }
    }
    return true
  }

  // 未认证 → 跳转登录
  if (!isAuthenticated()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 首次进入获取用户信息
  if (!userFetched) {
    const user = await fetchCurrentUser()
    userFetched = true
    if (!user) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  return true
})

export default router
