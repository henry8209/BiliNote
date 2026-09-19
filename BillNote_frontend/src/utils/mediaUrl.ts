/** 把后端误写成 http://localhost:8483/static/... 的封面改成当前站点同源路径 */
export function resolveMediaUrl(url?: string, fallback = '/placeholder.png'): string {
  if (!url) return fallback
  if (url.startsWith('/static/') || url.startsWith('/uploads/')) return url
  try {
    const u = new URL(url)
    const local =
      u.hostname === 'localhost' ||
      u.hostname === '127.0.0.1' ||
      u.hostname === 'backend'
    if (local && (u.pathname.startsWith('/static/') || u.pathname.startsWith('/uploads/'))) {
      return `${u.pathname}${u.search}`
    }
  } catch {
    /* ignore */
  }
  return url
}
