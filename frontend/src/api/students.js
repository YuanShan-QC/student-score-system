/**
 * 学生 API —— CRUD + 分页搜索
 */
import http from './index'

export function getStudents(params = {}) {
  return http.get('/students', { params })
}

export function createStudent(data) {
  return http.post('/students', data)
}

export function updateStudent(id, data) {
  return http.put(`/students/${id}`, data)
}

export function deleteStudent(id) {
  return http.delete(`/students/${id}`)
}
