<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { login, isAuthenticated } from '../stores/auth'

const route = useRoute()

const form = reactive({
  username: '',
  password: '',
  remember: false,
})
const loading = ref(false)

// 如果已经登录，跳转首页
if (isAuthenticated()) {
  window.location.href = '/'
}

async function handleLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await login(form.username, form.password)
    const redirect = (route.query.redirect as string) || '/'
    // 用硬跳转代替 router.push，避免路由守卫时序问题
    window.location.href = redirect
  } catch (e: any) {
    const msg = e.response?.data?.detail || e.message || '登录失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-container">
      <!-- 左侧品牌区域 -->
      <div class="login-brand">
        <div class="brand-content">
          <svg viewBox="0 0 48 48" width="56" height="56" class="brand-logo">
            <circle cx="24" cy="24" r="22" fill="rgba(255,255,255,0.15)" />
            <path d="M24 8 L32 20 L24 40 L16 20 Z" fill="#fff" />
            <circle cx="24" cy="20" r="4" fill="#409eff" />
          </svg>
          <h1 class="brand-title">燃气轮机运行优化智能体</h1>
          <p class="brand-desc">Gas Turbine Intelligent O&M System</p>
          <div class="brand-features">
            <div class="feature-item">
              <span class="feature-dot"></span>
              <span>能效监测与耗差分析</span>
            </div>
            <div class="feature-item">
              <span class="feature-dot"></span>
              <span>根因诊断与知识库</span>
            </div>
            <div class="feature-item">
              <span class="feature-dot"></span>
              <span>工作流编排与智能优化</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧登录表单 -->
      <div class="login-form-area">
        <div class="login-form-wrapper">
          <h2 class="form-title">用户登录</h2>
          <p class="form-subtitle">欢迎使用智能运维系统</p>

          <el-form :model="form" @submit.prevent="handleLogin" class="login-form" size="large">
            <el-form-item>
              <el-input
                v-model="form.username"
                placeholder="请输入用户名"
                :prefix-icon="User"
                clearable
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="form.password"
                type="password"
                placeholder="请输入密码"
                :prefix-icon="Lock"
                show-password
                @keyup.enter="handleLogin"
              />
            </el-form-item>

            <div class="form-options">
              <el-checkbox v-model="form.remember">记住我</el-checkbox>
            </div>

            <el-form-item>
              <el-button
                type="primary"
                :loading="loading"
                @click="handleLogin"
                style="width: 100%; height: 44px; font-size: 16px;"
              >
                {{ loading ? '登录中...' : '登 录' }}
              </el-button>
            </el-form-item>
          </el-form>

          <div class="form-footer">
            <span style="color: #909399; font-size: 12px;">
              默认管理员: admin / admin123
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  height: 100vh;
  width: 100vw;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0c1929 0%, #1a3a5c 50%, #0c1929 100%);
}

.login-container {
  display: flex;
  width: 880px;
  min-height: 480px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.login-brand {
  width: 420px;
  background: linear-gradient(135deg, #1565c0 0%, #0d47a1 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  position: relative;
  overflow: hidden;
}

.login-brand::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 60%);
}

.brand-content {
  position: relative;
  z-index: 1;
  text-align: center;
  color: #fff;
}

.brand-logo {
  margin-bottom: 20px;
}

.brand-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 8px;
  letter-spacing: 1px;
}

.brand-desc {
  font-size: 13px;
  opacity: 0.7;
  margin: 0 0 32px;
}

.brand-features {
  text-align: left;
  display: inline-block;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 14px;
  opacity: 0.9;
}

.feature-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.6);
  flex-shrink: 0;
}

.login-form-area {
  flex: 1;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.login-form-wrapper {
  width: 100%;
  max-width: 340px;
}

.form-title {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px;
}

.form-subtitle {
  font-size: 14px;
  color: #909399;
  margin: 0 0 32px;
}

.login-form {
  width: 100%;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.form-footer {
  text-align: center;
  margin-top: 24px;
}

@media (max-width: 768px) {
  .login-container {
    flex-direction: column;
    width: 90%;
    max-width: 420px;
  }
  .login-brand {
    width: 100%;
    min-height: 180px;
    padding: 24px;
  }
  .brand-features {
    display: none;
  }
}
</style>
