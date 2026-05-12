// ============================================================
// Vue Router Configuration — 9 routes for the O&M system
// ============================================================

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
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
    path: '/dictionary',
    name: 'DataDictionary',
    component: () => import('../views/DataDictionary.vue'),
    meta: { title: '数据字典' },
  },
  {
    path: '/knowledge',
    name: 'ModelKnowledge',
    component: () => import('../views/ModelKnowledge.vue'),
    meta: { title: '模型与知识库' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const title = (to.meta.title as string) ?? '燃气轮机运行优化智能体'
  document.title = `${title} - 燃气轮机运行优化智能体`
})

export default router
