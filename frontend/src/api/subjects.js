/**
 * 科目 API —— CRUD
 */
import http from './index'

export function getSubjects() {
  return http.get('/subjects')
}

export function createSubject(data) {
  return http.post('/subjects', data)
}

export function updateSubject(id, data) {
  return http.put(`/subjects/${id}`, data)
}

export function deleteSubject(id) {
  return http.delete(`/subjects/${id}`)
}
