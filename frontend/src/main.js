/**
 * Vue 应用入口 —— 全局注册 Element Plus / Pinia / Vue Router
 */
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

const app = createApp(App)

app.use(ElementPlus, { locale: zhCn })  // Element Plus 中文
app.use(createPinia())                   // Pinia 状态管理
app.use(router)                          // Vue Router

app.mount('#app')
