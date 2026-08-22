/**
 * 统计 API —— 数据看板
 */
import http from './index'

export function getStats() {
  return http.get('/stats')
}
