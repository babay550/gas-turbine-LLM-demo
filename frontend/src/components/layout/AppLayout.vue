<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChatSidebar from './ChatSidebar.vue'
import {
  HomeFilled,
  TrendCharts,
  DataAnalysis,
  Connection,
  SetUp,
  Bell,
  Timer,
  Notebook,
  Collection,
  ChatDotSquare,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const chatVisible = ref(false)

const isCollapsed = ref(false)

const menuItems = [
  { index: '/', icon: HomeFilled, title: '首页' },
  { index: '/efficiency', icon: TrendCharts, title: '能效监测' },
  { index: '/loss', icon: DataAnalysis, title: '耗差分析' },
  { index: '/root-cause', icon: Connection, title: '根因诊断' },
  { index: '/optimization', icon: SetUp, title: '运营优化' },
  { index: '/warning', icon: Bell, title: '预警管理' },
  { index: '/schedule', icon: Timer, title: '调度管理' },
  { index: '/dictionary', icon: Notebook, title: '数据字典' },
  { index: '/knowledge', icon: Collection, title: '模型与知识库' },
]

const activeMenu = computed(() => route.path)

function handleSelect(index: string) {
  router.push(index)
}

function toggleChat() {
  chatVisible.value = !chatVisible.value
}
</script>

<template>
  <el-container class="app-layout">
    <!-- Left Sidebar -->
    <el-aside :width="isCollapsed ? '64px' : '210px'" class="layout-aside">
      <div class="logo-area">
        <svg viewBox="0 0 32 32" width="28" height="28" class="logo-icon">
          <circle cx="16" cy="16" r="14" fill="#409eff" opacity="0.15" />
          <path d="M16 6 L22 14 L16 26 L10 14 Z" fill="#409eff" />
          <circle cx="16" cy="14" r="3" fill="#fff" />
        </svg>
        <span v-show="!isCollapsed" class="logo-text">燃气轮机运行优化</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :collapse-transition="true"
        class="sidebar-menu"
        background-color="#001529"
        text-color="#ffffffb3"
        active-text-color="#409eff"
        router
        @select="handleSelect"
      >
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
      <div class="collapse-btn" @click="isCollapsed = !isCollapsed">
        <el-icon :size="16">
          <component :is="isCollapsed ? 'DArrowRight' : 'DArrowLeft'" />
        </el-icon>
      </div>
    </el-aside>

    <!-- Right Area -->
    <el-container class="layout-main-area">
      <!-- Top Header -->
      <el-header class="layout-header" height="50px">
        <div class="header-left">
          <h3 class="header-title">燃气轮机运行优化智能体</h3>
        </div>
        <div class="header-right">
          <el-badge :value="0" :hidden="true">
            <el-button :icon="Bell" circle size="small" />
          </el-badge>
          <el-button
            :type="chatVisible ? 'primary' : 'default'"
            :icon="ChatDotSquare"
            circle
            size="small"
            @click="toggleChat"
          />
        </div>
      </el-header>

      <!-- Content + Chat -->
      <el-container class="layout-content-wrapper">
        <el-main class="layout-main">
          <router-view />
        </el-main>
        <ChatSidebar :visible="chatVisible" />
      </el-container>
    </el-container>
  </el-container>
</template>

<script lang="ts">
import { DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
export default { components: { DArrowLeft, DArrowRight } }
</script>

<style scoped>
.app-layout {
  height: 100vh;
  width: 100vw;
}

.layout-aside {
  background: #001529;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.3s;
}

.logo-area {
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 12px;
  border-bottom: 1px solid #ffffff1a;
  flex-shrink: 0;
}

.logo-text {
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  overflow-y: auto;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 210px;
}

.collapse-btn {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #ffffffb3;
  border-top: 1px solid #ffffff1a;
  flex-shrink: 0;
  transition: color 0.2s;
}

.collapse-btn:hover {
  color: #409eff;
}

.layout-main-area {
  flex-direction: column;
  overflow: hidden;
}

.layout-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.layout-content-wrapper {
  overflow: hidden;
}

.layout-main {
  flex: 1;
  overflow-y: auto;
  background: #f0f2f5;
  padding: 16px;
}
</style>
