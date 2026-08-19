<script setup>
/**
 * App.vue —— 侧边栏布局
 * el-container(全屏) → el-aside(200px menu) + el-main(router-view)
 */
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = ref('/students')

// 菜单项与路由 path 绑定
const menuItems = [
  { path: '/students', label: '👨‍🎓 学生管理', icon: 'User' },
  { path: '/subjects', label: '📚 科目管理', icon: 'Notebook' },
  { path: '/scores',   label: '📊 成绩管理', icon: 'DataLine' },
  { path: '/ai',       label: '🤖 智能体', icon: 'MagicStick' },
]

// 路由变化时高亮当前菜单
watch(() => route.path, (path) => {
  activeMenu.value = path
})
</script>

<template>
  <el-container style="height: 100vh">
    <!-- 左侧菜单 -->
    <el-aside width="200px" style="background: #304156">
      <div style="padding: 20px; text-align: center; color: #fff; font-size: 18px; font-weight: 600; border-bottom: 1px solid #4a5568">
        🎓 成绩管理系统
      </div>
      <el-menu
        :default-active="activeMenu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 右侧内容区 -->
    <el-main style="background: #f0f2f5; padding: 24px">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </el-main>
  </el-container>
</template>
