import { onUnmounted } from 'vue'
import { useSession } from './stores/session'

// Every task owns its timer. A course change disposes the keyed view and
// invalidates responses that were already in flight.
export function useCourseScope() {
  const session = useSession(), courseId = session.courseId
  let disposed = false, timer: ReturnType<typeof setTimeout> | undefined
  const active = () => !disposed && session.courseId === courseId
  const stop = () => { if (timer) clearTimeout(timer); timer = undefined }
  const schedule = (work: () => Promise<void>, delay = 1800) => {
    stop()
    if (active()) timer = setTimeout(() => { if (active()) void work().catch(() => {}) }, delay)
  }
  onUnmounted(() => { disposed = true; stop() })
  return { courseId, active, schedule, stop }
}
