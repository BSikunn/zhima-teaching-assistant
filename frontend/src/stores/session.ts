import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api'

export const useSession = defineStore('session', () => {
  const user = ref<any>(JSON.parse(localStorage.getItem('zhima-user') || 'null'))
  const courses = ref<any[]>([])
  const courseId = ref(Number(localStorage.getItem('zhima-course') || 1))
  const course = computed(() => courses.value.find(c => c.id === courseId.value))
  const isStudent = computed(() => user.value?.role === 'student')
  const isAdmin = computed(() => user.value?.role === 'admin')
  const roleName = computed(() => ({ student: '学生工作台', teacher: '教师工作台', admin: '管理工作台' }[user.value?.role as string] || '学习空间'))
  async function loadCourses() {
    const [profile, availableCourses] = await Promise.all([api.get('/auth/me'), api.get('/courses')])
    user.value = profile
    localStorage.setItem('zhima-user', JSON.stringify(profile))
    courses.value = availableCourses
    if (!courses.value.some(c => c.id === courseId.value)) courseId.value = courses.value[0]?.id || 1
  }
  async function login(username: string, password: string) {
    const result = await api.post('/auth/login', { username, password })
    user.value = result.user
    localStorage.setItem('zhima-token', result.access_token)
    localStorage.setItem('zhima-user', JSON.stringify(result.user))
    await loadCourses()
  }
  function logout() {
    user.value = null; courses.value = []
    localStorage.removeItem('zhima-token'); localStorage.removeItem('zhima-user')
  }
  function selectCourse(id: number) {
    courseId.value = id
    localStorage.setItem('zhima-course', String(id))
  }
  return { user, courses, courseId, course, isStudent, isAdmin, roleName, login, logout, loadCourses, selectCourse }
})
