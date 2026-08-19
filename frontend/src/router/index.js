/**
 * Vue Router 配置 —— 4 个页面，全部懒加载
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/students',
  },
  {
    path: '/students',
    name: 'Students',
    component: () => import('@/views/StudentList.vue'),
  },
  {
    path: '/subjects',
    name: 'Subjects',
    component: () => import('@/views/SubjectList.vue'),
  },
  {
    path: '/scores',
    name: 'Scores',
    component: () => import('@/views/ScoreEntry.vue'),
  },
  {
    path: '/ai',
    name: 'AI',
    component: () => import('@/views/AIQuery.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
