import { useEffect, useRef } from 'react'
import { useTaskStore } from '@/store/taskStore'
import { get_task_status } from '@/services/note.ts'
import toast from 'react-hot-toast'

export const useTaskPolling = (interval = 3000) => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)
  const updateTaskStatus = useTaskStore(state => state.updateTaskStatus)
  const removeTask = useTaskStore(state => state.removeTask)

  const tasksRef = useRef(tasks)

  // 每次 tasks 更新，把最新的 tasks 同步进去
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  useEffect(() => {
    const timer = setInterval(async () => {
      const pendingTasks = tasksRef.current.filter(
        task => task.status != 'SUCCESS' && task.status != 'FAILED'
      )

      // 无活跃任务时跳过轮询
      if (pendingTasks.length === 0) return

      for (const task of pendingTasks) {
        try {
          const res = await get_task_status(task.id)
          const { status } = res
          const statusMessage = (res as any)?.message || ''
          const pipeline = (res as any)?.pipeline || ''
          const pipelineLabel = (res as any)?.pipeline_label || ''
          const etaSeconds = (res as any)?.eta_seconds
          const pipelineChanged =
            pipeline !== (task.pipeline || '') ||
            statusMessage !== (task.statusMessage || '') ||
            status !== task.status

          if (status && pipelineChanged) {
            const prevPipe = task.pipeline || ''
            const isScheme = ['youtube_subtitles', 'mlx_whisper_api', 'whisper_cpu'].includes(
              pipeline,
            )
            if (isScheme && pipeline !== prevPipe) {
              const etaMin = etaSeconds ? Math.max(1, Math.round(Number(etaSeconds) / 60)) : null
              const etaText = etaMin ? `預估約 ${etaMin} 分鐘。` : ''
              if (pipeline === 'whisper_cpu') {
                toast(`方案 C｜本機 Whisper CPU（fallback）。${etaText}請勿關閉頁面。`, {
                  duration: 12000,
                })
              } else if (pipeline === 'mlx_whisper_api') {
                toast.success(`方案 B｜內網 MLX Whisper（不出公網）。${etaText || '通常約 1–2 分鐘。'}`)
              } else {
                toast.success(`方案 A｜平台字幕。${etaText || '約 1–2 分鐘。'}`)
              }
            }
            if (status === 'SUCCESS') {
              const { markdown, transcript, audio_meta } = res.result
              toast.success('笔记生成成功')
              updateTaskContent(task.id, {
                status,
                markdown,
                transcript,
                audioMeta: audio_meta,
                statusMessage: '',
                pipeline,
                pipelineLabel,
                etaSeconds: etaSeconds != null ? Number(etaSeconds) : undefined,
              })
            } else if (status === 'FAILED') {
              const errMsg = (res as any)?.message || ''
              updateTaskContent(task.id, {
                status,
                errorMessage: errMsg,
              })
              console.warn(`⚠️ 任务 ${task.id} 失败`, errMsg)
              if (
                errMsg.includes('data_inspection_failed') ||
                errMsg.includes('inappropriate content')
              ) {
                toast.error(
                  '⚠️ 模型內容審核失敗：供應商拒絕此影片輸入（阿里雲百煉常見於政治／敏感新聞）。請改用 Agnes 等其他模型重試。',
                  { duration: 8000 },
                )
              } else if (errMsg) {
                toast.error(`筆記生成失敗：${errMsg.slice(0, 160)}`, { duration: 6000 })
              } else {
                toast.error('筆記生成失敗')
              }
            } else {
              updateTaskContent(task.id, {
                status,
                statusMessage,
                pipeline,
                pipelineLabel,
                etaSeconds: etaSeconds != null ? Number(etaSeconds) : undefined,
              })
            }
          }
        } catch (e: any) {
          console.error('❌ 任务轮询失败：', e)
          const errMsg = e?.msg || e?.message || ''
          updateTaskContent(task.id, {
            status: 'FAILED',
            errorMessage: errMsg,
          })
          if (
            errMsg.includes('data_inspection_failed') ||
            errMsg.includes('inappropriate content')
          ) {
            toast.error(
              '⚠️ 模型內容審核失敗：供應商拒絕此影片輸入。請改用 Agnes 等其他模型重試。',
              { duration: 8000 },
            )
          }
        }
      }
    }, interval)

    return () => clearInterval(timer)
  }, [interval])
}
