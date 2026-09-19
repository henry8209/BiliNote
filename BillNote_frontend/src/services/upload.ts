/**
 * 本地视频上传。
 * Cloudflare 免费版单次 POST 约 100MB 会 413，所以 >8MB 自动分块。
 */
export type UploadResult = { url: string }

const CHUNK_SIZE = 8 * 1024 * 1024

function apiBase(): string {
  return String(import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
}

function postForm(url: string, form: FormData, onProgress?: (loaded: number, total: number) => void) {
  return new Promise<any>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    xhr.timeout = 10 * 60 * 1000
    xhr.upload.onprogress = ev => {
      if (ev.lengthComputable && onProgress) onProgress(ev.loaded, ev.total)
    }
    xhr.onload = () => {
      if (xhr.status === 413) {
        reject({
          code: 413,
          msg: '檔案超過閘道上限（Cloudflare 約 100MB）。請用分塊上傳或較小檔。',
          data: null,
        })
        return
      }
      let json: any = null
      try {
        json = JSON.parse(xhr.responseText || '{}')
      } catch {
        reject({
          code: xhr.status,
          msg: `上傳失敗 HTTP ${xhr.status}（回應不是 JSON）`,
          data: null,
        })
        return
      }
      if (xhr.status >= 200 && xhr.status < 300 && json.code === 0) {
        resolve(json.data)
        return
      }
      reject({
        code: json.code ?? xhr.status,
        msg: json.msg || `上傳失敗 HTTP ${xhr.status}`,
        data: json.data ?? null,
      })
    }
    xhr.onerror = () =>
      reject({ code: -1, msg: '上傳失敗：連線被中斷', data: null })
    xhr.ontimeout = () =>
      reject({ code: -1, msg: '上傳超時', data: null })
    xhr.send(form)
  })
}

export async function uploadFile(
  formData: FormData,
  onProgress?: (percent: number) => void,
): Promise<UploadResult> {
  const file = formData.get('file')
  if (!(file instanceof File)) {
    throw { code: -1, msg: '沒有檔案', data: null }
  }
  const base = apiBase()

  if (file.size <= CHUNK_SIZE) {
    const data = await postForm(`${base}/upload`, formData, (loaded, total) => {
      if (onProgress && total) onProgress(Math.round((loaded / total) * 100))
    })
    if (!data?.url) throw { code: -1, msg: '上傳成功但沒有返回路徑', data: null }
    return data as UploadResult
  }

  const total = Math.ceil(file.size / CHUNK_SIZE)
  const uploadId =
    (globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`).replace(/-/g, '')

  let sent = 0
  for (let i = 0; i < total; i++) {
    const blob = file.slice(i * CHUNK_SIZE, Math.min(file.size, (i + 1) * CHUNK_SIZE))
    const chunk = new FormData()
    chunk.append('file', blob, `${file.name}.part${i}`)
    chunk.append('upload_id', uploadId)
    chunk.append('index', String(i))
    chunk.append('total', String(total))
    chunk.append('filename', file.name)
    await postForm(`${base}/upload/chunk`, chunk)
    sent += blob.size
    if (onProgress) onProgress(Math.min(99, Math.round((sent / file.size) * 100)))
  }

  const finish = new FormData()
  finish.append('upload_id', uploadId)
  finish.append('filename', file.name)
  finish.append('total', String(total))
  const data = await postForm(`${base}/upload/complete`, finish)
  if (onProgress) onProgress(100)
  if (!data?.url) throw { code: -1, msg: '合併分塊失敗', data: null }
  return data as UploadResult
}
