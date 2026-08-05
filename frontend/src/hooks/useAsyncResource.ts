import { useCallback, useEffect, useRef, useState } from 'react'
import { isAbortError } from '../api'

interface UseAsyncResourceOptions {
  /** Base polling period. Omit to load once and refresh only on demand. */
  pollIntervalMs?: number
  maxBackoffMs?: number
  enabled?: boolean
}

interface AsyncResource<T> {
  data: T | null
  /** True only before the first successful load, so pages can show a skeleton. */
  initialLoading: boolean
  /** True while a background refresh runs; existing data stays on screen. */
  refreshing: boolean
  error: Error | null
  lastUpdatedAt: number | null
  refresh: () => Promise<void>
}

const DEFAULT_MAX_BACKOFF_MS = 300_000

function toError(error: unknown) {
  return error instanceof Error ? error : new Error('请求失败')
}

/**
 * Loads one resource with optional polling. Deliberately narrow: it owns
 * "fetch, refresh, poll" and nothing else — pages compose it per dataset rather
 * than routing every request through one generic store.
 *
 * `load` is read through a ref, so callers may pass an inline closure without
 * restarting the poll timer on every render.
 */
export function useAsyncResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  options: UseAsyncResourceOptions = {},
): AsyncResource<T> {
  const { pollIntervalMs, maxBackoffMs = DEFAULT_MAX_BACKOFF_MS, enabled = true } = options

  const [data, setData] = useState<T | null>(null)
  const [initialLoading, setInitialLoading] = useState(enabled)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null)

  const loadRef = useRef(load)
  loadRef.current = load

  const mounted = useRef(true)
  const sequence = useRef(0)
  const active = useRef<AbortController | null>(null)
  const hasData = useRef(false)
  const backoff = useRef(pollIntervalMs ?? 0)

  const fetchOnce = useCallback(async () => {
    // A refresh already in flight owns this cycle; a second one would only race.
    if (!mounted.current || active.current) return

    const current = ++sequence.current
    const controller = new AbortController()
    active.current = controller

    if (hasData.current) setRefreshing(true)
    else setInitialLoading(true)

    try {
      const next = await loadRef.current(controller.signal)
      if (!mounted.current || current !== sequence.current) return
      setData(next)
      setError(null)
      setLastUpdatedAt(Date.now())
      hasData.current = true
      backoff.current = pollIntervalMs ?? 0
    } catch (requestError) {
      if (!mounted.current || current !== sequence.current || isAbortError(requestError)) return
      setError(toError(requestError))
      if (pollIntervalMs) {
        backoff.current = Math.min(Math.max(backoff.current, pollIntervalMs) * 2, maxBackoffMs)
      }
    } finally {
      if (active.current === controller) active.current = null
      if (mounted.current && current === sequence.current) {
        setInitialLoading(false)
        setRefreshing(false)
      }
    }
  }, [maxBackoffMs, pollIntervalMs])

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      sequence.current += 1
      active.current?.abort()
      active.current = null
    }
  }, [])

  useEffect(() => {
    if (!enabled) return

    let timer: number | null = null
    let stopped = false

    function clearTimer() {
      if (timer !== null) {
        window.clearTimeout(timer)
        timer = null
      }
    }

    /**
     * Polls only while the tab is visible: a background tab would otherwise keep
     * hammering `/services`, which returns every probe and rule tree.
     */
    function schedule() {
      clearTimer()
      if (stopped || !pollIntervalMs || document.visibilityState !== 'visible') return
      timer = window.setTimeout(async () => {
        timer = null
        if (stopped || document.visibilityState !== 'visible') return
        await fetchOnce()
        schedule()
      }, backoff.current || pollIntervalMs)
    }

    function onVisibilityChange() {
      if (stopped) return
      if (document.visibilityState === 'visible') void fetchOnce().then(schedule)
      else clearTimer()
    }

    void fetchOnce().then(schedule)
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      stopped = true
      clearTimer()
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [enabled, fetchOnce, pollIntervalMs])

  return { data, initialLoading, refreshing, error, lastUpdatedAt, refresh: fetchOnce }
}
