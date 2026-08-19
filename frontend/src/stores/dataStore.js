/**
 * dataStore.js — 全局数据变更通知
 * AI 智能体修改数据后，递增 refreshKey，列表页 watch 后自动重新加载
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useDataStore = defineStore('data', () => {
  const refreshKey = ref(0)

  /** AI 写操作成功后调用，通知所有列表页刷新 */
  function notifyChange() {
    refreshKey.value++
  }

  return { refreshKey, notifyChange }
})
