/**
 * 成绩 API —— 按学号查 + CRUD + Excel 导入导出
 */
import http from './index'

export function getScores(studentId) {
  return http.get('/scores', { params: { student_id: studentId } })
}

export function createScore(data) {
  return http.post('/scores', data)
}

export function updateScore(id, data) {
  return http.put(`/scores/${id}`, data)
}

export function deleteScore(id) {
  return http.delete(`/scores/${id}`)
}

// Excel 导出（返回 Blob，前端触发下载）
export function downloadExcel(mode) {
  return http.get('/scores/export', { params: { mode }, responseType: 'blob' })
}

// Excel 导入（FormData 上传文件）
export function importExcel(file) {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/scores/import', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
