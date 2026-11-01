import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({ baseURL: '/api', timeout: 180000 })
client.interceptors.request.use(config => {
  const token = localStorage.getItem('zhima-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
client.interceptors.response.use(response => response, error => {
  const detail = error.response?.data?.detail
  const text = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: any) => d.msg).join('；') : '连接失败，请检查后端服务后重试'
  ElMessage.error(text)
  if (error.response?.status === 401 && !location.pathname.startsWith('/login')) {
    localStorage.removeItem('zhima-token')
    localStorage.removeItem('zhima-user')
    location.assign('/login')
  }
  return Promise.reject(error)
})
export const api = {
  get: async <T = any>(path: string) => (await client.get<T>(path)).data,
  post: async <T = any>(path: string, body?: any) => (await client.post<T>(path, body)).data,
  put: async <T = any>(path: string, body?: any) => (await client.put<T>(path, body)).data,
  patch: async <T = any>(path: string, body?: any) => (await client.patch<T>(path, body)).data,
  delete: async (path: string) => (await client.delete(path)).data,
  download: async (id: number, filename: string) => {
    const { data } = await client.get(`/materials/${id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const link = document.createElement('a'); link.href = url; link.download = filename; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
  downloadReport: async (id: number, filename: string) => {
    const { data } = await client.get(`/reports/${id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(data), link = document.createElement('a')
    link.href = url; link.download = filename; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
}
export function dateText(value: string | null, withTime = false) {
  if (!value) return '未设置'
  const normalized = value.trim().replace(' ', 'T')
  const zoned = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized.length === 10 ? normalized + 'T00:00:00' : normalized}+08:00`
  const date = new Date(zoned)
  if (Number.isNaN(date.getTime())) return '时间未知'
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', ...(withTime ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' } as const : {}) }).format(date)
}
export const statusText: Record<string, string> = { pending_grade: '等待评阅', graded: '评阅完成', completed: '已完成', generating: '生成中', needs_review: '待教师评阅', failed: '处理失败', grading: '评阅中', pending: '等待处理', draft: '草稿', published: '已发布', ready: '已就绪', processing: '解析中', indexing: '索引中', mastered: '已复习' }
