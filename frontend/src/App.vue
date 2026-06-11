<script setup lang="ts">
import { useRoute } from 'vue-router'
import AppLayout from './components/layout/AppLayout.vue'
import { computed } from 'vue'

const route = useRoute()
const isLoginPage = computed(() => route.path === '/login')
</script>

<template>
  <AppLayout v-if="!isLoginPage" />
  <router-view v-else />
</template>

<style>
/* Global reset for the O&M system layout */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  width: 100%;
  height: 100%;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* Override Element Plus defaults for consistency */
.el-main {
  --el-main-padding: 0;
}
</style>
