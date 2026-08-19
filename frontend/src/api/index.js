/**
 * Axios 实例 —— 统一配置 baseURL、自动解包 response.data、统一错误处理
 */
import axios from 'axios'

const http = axios.create({
  baseURL: 'http://localhost:8080/api',
  timeout: 10000,
})

// 响应拦截器：自动解包 response.data
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('[API Error]', error.config?.url, error.message)
    return Promise.reject(error)
  },
)

export default http
