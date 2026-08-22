<script setup>
/**
 * App.vue —— 整体布局
 * 左侧深色侧边栏 + 顶部导航栏（面包屑 + 暗色切换）+ 内容区
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Moon, Sunny, User, Notebook, DataLine, MagicStick, Monitor } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

// 菜单项：label 只保留文字，图标用矢量图标
const menuItems = [
  { path: '/dashboard', label: '数据看板', icon: Monitor },
  { path: '/students', label: '学生管理', icon: User },
  { path: '/subjects', label: '科目管理', icon: Notebook },
  { path: '/scores', label: '成绩管理', icon: DataLine },
  { path: '/ai', label: '智能体', icon: MagicStick },
]

// 当前激活菜单
const activeMenu = computed(() => route.path)

// 面包屑：由当前路由 name 映射
const titleMap = {
  Dashboard: '数据看板',
  Students: '学生管理',
  Subjects: '科目管理',
  Scores: '成绩管理',
  AI: '智能体',
}
const pageTitle = computed(() => titleMap[route.name] || '成绩管理系统')

// ===== 暗色模式 =====
const isDark = ref(false)

function toggleDark() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

onMounted(() => {
  // 恢复用户上次选择的主题（默认跟随系统）
  const saved = localStorage.getItem('theme')
  if (saved === 'dark') {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else if (!saved) {
    const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
    if (prefersDark) {
      isDark.value = true
      document.documentElement.classList.add('dark')
    }
  }
})
</script>

<template>
  <el-container class="app-container">
    <!-- 左侧菜单 -->
    <el-aside width="220px" class="app-aside">
      <div class="logo">
        <div class="logo-icon">成</div>
        <span class="logo-text">成绩管理系统</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="app-menu"
        background-color="transparent"
        text-color="#cbd5e1"
        active-text-color="#ffffff"
        router
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部导航栏 -->
      <el-header class="app-header">
        <div class="breadcrumb">
          <span class="breadcrumb-root">首页</span>
          <span class="breadcrumb-sep">/</span>
          <span class="breadcrumb-current">{{ pageTitle }}</span>
        </div>
        <div class="header-actions">
          <el-tooltip :content="isDark ? '切换到亮色模式' : '切换到暗色模式'" placement="bottom">
            <el-button circle text @click="toggleDark">
              <el-icon :size="18">
                <Sunny v-if="isDark" />
                <Moon v-else />
              </el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <keep-alive>
              <component :is="Component" />
            </keep-alive>
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-container {
  height: 100vh;
}

/* ===== 侧边栏 ===== */
.app-aside {
  background: var(--app-sidebar-bg);
  transition: background 0.3s;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 60px;
  padding: 0 20px;
  background: var(--app-sidebar-logo-bg);
}
.logo-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--el-color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
}
.logo-text {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 1px;
}

.app-menu {
  border-right: none;
  padding: 8px 0;
}
.app-menu :deep(.el-menu-item) {
  height: 48px;
  margin: 4px 12px;
  border-radius: 8px;
}
.app-menu :deep(.el-menu-item.is-active) {
  background: var(--app-sidebar-active-bg);
}
.app-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
}

/* ===== 顶部导航栏 ===== */
.app-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--app-header-bg);
  border-bottom: 1px solid var(--app-header-border);
  padding: 0 24px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
.breadcrumb-root {
  color: var(--app-text-sub);
}
.breadcrumb-sep {
  color: var(--app-text-sub);
}
.breadcrumb-current {
  color: var(--app-text-main);
  font-weight: 500;
}

/* ===== 内容区 ===== */
.app-main {
  background: var(--app-page-bg);
  padding: 24px;
  overflow-y: auto;
  transition: background 0.3s;
}

/* ===== 路由过渡动画 ===== */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
