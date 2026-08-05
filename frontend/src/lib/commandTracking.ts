import type { AgentCommandState, AgentCommandStatus, ProbeResult, Status } from '../types'

/**
 * Visible phase of a probe/restart action. `queued` means the host runs in agent
 * mode and the command is waiting to be claimed and executed, which can take
 * noticeably longer than a synchronous SSH check.
 */
export type ActionPhase = 'idle' | 'running' | 'queued'

const TERMINAL_STATES = new Set<AgentCommandState>(['succeeded', 'failed', 'expired'])

function isTerminalState(state: AgentCommandState): boolean {
  return TERMINAL_STATES.has(state)
}

const POLL_INTERVAL_MS = 1_500

/** Backend commands expire after 5 minutes; polling stops well before that. */
const MAX_POLL_DURATION_MS = 5 * 60_000

function toStatus(value: unknown): Status {
  return value === 'online' || value === 'offline' ? value : 'unknown'
}

/** Collapses a finished agent command into the same shape a sync action returns. */
function resultFromCommand(command: AgentCommandStatus): ProbeResult {
  const report = command.result

  if (command.status === 'expired') {
    return {
      mode: 'immediate',
      success: false,
      status: 'unknown',
      message: 'Agent 未在有效期内执行该命令，请确认 Agent 是否在线。',
      restarted: false,
      command_id: command.command_id,
      command_status: command.status,
    }
  }

  return {
    mode: 'immediate',
    success: command.status === 'succeeded',
    status: toStatus(command.status === 'succeeded' ? 'online' : 'offline'),
    message: report?.message || (command.status === 'succeeded' ? '执行成功' : '执行失败'),
    response_ms: report?.response_ms ?? null,
    restarted: report?.restarted ?? false,
    command_id: command.command_id,
    command_status: command.status,
  }
}

interface TrackActionCallbacks {
  /** Fires once when the action turns out to be asynchronous. */
  onQueued?: () => void
  signal?: AbortSignal
}

interface TrackActionDeps {
  pollIntervalMs?: number
  maxDurationMs?: number
  now?: () => number
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>
}

function defaultSleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }
    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    function onAbort() {
      window.clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

/**
 * Runs an action and resolves with its final result, transparently polling agent
 * commands when the backend answers `mode: 'queued'`. Immediate results return
 * untouched, so callers handle a single code path.
 */
export async function trackAction(
  startAction: () => Promise<ProbeResult>,
  getCommand: (commandId: string, signal?: AbortSignal) => Promise<AgentCommandStatus>,
  callbacks: TrackActionCallbacks = {},
  deps: TrackActionDeps = {},
): Promise<ProbeResult> {
  const pollIntervalMs = deps.pollIntervalMs ?? POLL_INTERVAL_MS
  const maxDurationMs = deps.maxDurationMs ?? MAX_POLL_DURATION_MS
  const now = deps.now ?? Date.now
  const sleep = deps.sleep ?? defaultSleep

  const started = await startAction()
  if (started.mode !== 'queued') return started

  const commandId = started.command_id
  if (!commandId) {
    return {
      ...started,
      mode: 'immediate',
      success: false,
      message: '服务端返回了排队状态但未提供命令编号，无法跟踪执行结果。',
    }
  }

  callbacks.onQueued?.()

  const deadline = now() + maxDurationMs
  while (now() < deadline) {
    await sleep(pollIntervalMs, callbacks.signal)
    const command = await getCommand(commandId, callbacks.signal)
    if (isTerminalState(command.status)) return resultFromCommand(command)
  }

  return {
    ...started,
    mode: 'immediate',
    success: false,
    message: '命令仍在执行，界面已停止等待。稍后刷新可查看最新状态。',
    command_id: commandId,
  }
}
