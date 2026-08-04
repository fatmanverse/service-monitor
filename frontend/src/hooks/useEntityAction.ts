import { useCallback, useEffect, useRef, useState } from 'react'
import { api, isAbortError } from '../api'
import { trackAction, type ActionPhase } from '../lib/commandTracking'
import type { ProbeResult } from '../types'

/**
 * Tracks per-entity action state for row-level buttons (probe, restart, test).
 * Concurrent clicks on the same entity reuse the in-flight promise instead of
 * stacking a second poller, and results are dropped after unmount.
 */
export function useEntityAction() {
  const [phases, setPhases] = useState<Record<number, ActionPhase>>({})
  const inFlight = useRef(new Map<number, Promise<ProbeResult | null>>())
  const abortRef = useRef(new AbortController())
  const mounted = useRef(true)

  useEffect(() => {
    const controller = abortRef.current
    return () => {
      mounted.current = false
      controller.abort()
    }
  }, [])

  const setPhase = useCallback((entityId: number, phase: ActionPhase) => {
    if (!mounted.current) return
    setPhases((current) => {
      if (phase === 'idle') {
        const { [entityId]: _removed, ...rest } = current
        return rest
      }
      return { ...current, [entityId]: phase }
    })
  }, [])

  /**
   * Runs `start` for the entity and resolves with the settled result, or null
   * when the component unmounted mid-flight. Errors propagate so the caller can
   * surface them next to the row that triggered the action.
   */
  const run = useCallback(
    (entityId: number, start: () => Promise<ProbeResult>): Promise<ProbeResult | null> => {
      const existing = inFlight.current.get(entityId)
      if (existing) return existing

      setPhase(entityId, 'running')

      const promise = trackAction(
        start,
        (commandId, signal) => api.agentCommand(commandId, { signal }),
        {
          onQueued: () => setPhase(entityId, 'queued'),
          signal: abortRef.current.signal,
        },
      )
        .then((result) => (mounted.current ? result : null))
        .catch((error: unknown) => {
          if (isAbortError(error)) return null
          throw error
        })
        .finally(() => {
          inFlight.current.delete(entityId)
          setPhase(entityId, 'idle')
        })

      inFlight.current.set(entityId, promise)
      return promise
    },
    [setPhase],
  )

  const phaseOf = useCallback(
    (entityId: number): ActionPhase => phases[entityId] ?? 'idle',
    [phases],
  )

  return { run, phaseOf }
}
