import { create } from 'zustand'

// Use Vite proxy in dev (relative `/api` and `/ws`) and allow override via env.
const API_BASE = import.meta.env.VITE_API_BASE || ''
const WS_BASE = import.meta.env.VITE_WS_BASE || ''

const useStore = create((set, get) => ({
  // ── Workflow State ─────────────────────────────────────────────
  workflowId: null,
  stage: 'idle',
  stageMessage: '',
  isRunning: false,
  error: null,

  // ── Agent Data ─────────────────────────────────────────────────
  plan: null,
  flights: [],
  selectedFlightIndex: null,
  logs: [],

  // ── Live Browser Stream ────────────────────────────────────────
  screenshotUrl: null,
  screenshotTimestamp: null,

  // ── UI State ───────────────────────────────────────────────────
  activePanel: 'chat', // 'chat' | 'browser' | 'logs'
  passengerFormVisible: false,
  ws: null,
  wsReconnectAttempt: 0,

  // ── Actions ────────────────────────────────────────────────────

  startWorkflow: async (query) => {
    // Prevent overlapping workflows (stale timeouts/logs) by stopping any previous one.
    const { workflowId: prevWorkflowId, ws: prevWs } = get()
    if (prevWs) {
      try {
        prevWs.close()
      } catch (_) {}
      set({ ws: null })
    }
    if (prevWorkflowId) {
      try {
        await fetch(`${API_BASE}/api/workflow/${prevWorkflowId}/stop`, { method: 'POST' })
      } catch (_) {}
    }

    set({ isRunning: true, error: null, logs: [], flights: [], plan: null, screenshotUrl: null, selectedFlightIndex: null })

    try {
      const res = await fetch(`${API_BASE}/api/workflow/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })
      const data = await res.json()
      const workflowId = data.workflow_id

      set({ workflowId })
      get().connectWebSocket(workflowId)
    } catch (err) {
      set({ error: err.message, isRunning: false })
    }
  },

  stopWorkflow: async () => {
    const { workflowId, ws } = get()
    if (!workflowId) return

    if (ws) {
      ws.close()
      set({ ws: null })
    }

    try {
      await fetch(`${API_BASE}/api/workflow/${workflowId}/stop`, { method: 'POST' })
    } catch (_) {}

    set({ isRunning: false, workflowId: null, stage: 'idle', stageMessage: '', passengerFormVisible: false })
  },

  selectFlight: async (index) => {
    const { workflowId } = get()
    set({ selectedFlightIndex: index })

    try {
      await fetch(`${API_BASE}/api/workflow/${workflowId}/select-flight?flight_index=${index}`, {
        method: 'POST',
      })
      get().addLog({ level: 'info', agent: 'user', message: `Flight #${index + 1} selected` })
    } catch (err) {
      get().addLog({ level: 'error', agent: 'system', message: `Failed to select flight: ${err.message}` })
    }
  },

  submitPassenger: async (passengerData) => {
    const { workflowId } = get()
    if (!workflowId) return

    try {
      const res = await fetch(`${API_BASE}/api/workflow/${workflowId}/passenger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(passengerData),
      })
      const data = await res.json()
      set({ passengerFormVisible: false })
      get().addLog({ level: 'success', agent: 'user', message: 'Passenger details submitted' })
    } catch (err) {
      get().addLog({ level: 'error', agent: 'system', message: `Failed to submit passenger: ${err.message}` })
    }
  },

  connectWebSocket: (workflowId) => {
    const current = get()
    if (current.ws) {
      try {
        current.ws.close()
      } catch (_) {}
    }

    const wsUrl =
      WS_BASE
        ? `${WS_BASE.replace(/\/$/, '')}/ws/${workflowId}`
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/${workflowId}`
    const ws = new WebSocket(wsUrl)
    const myWorkflowId = workflowId
    set({ ws, wsReconnectAttempt: 0 })

    ws.onopen = () => {
      get().addLog({ level: 'info', agent: 'system', message: 'WebSocket connected — live updates active' })
      set({ wsReconnectAttempt: 0 })
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        get().handleWsMessage(msg)
      } catch (_) {}
    }

    ws.onerror = () => {
      get().addLog({ level: 'error', agent: 'system', message: 'WebSocket connection error' })
    }

    ws.onclose = () => {
      get().addLog({ level: 'info', agent: 'system', message: 'WebSocket disconnected' })
      set({ ws: null })

      const { isRunning, workflowId: stillWorkflowId, wsReconnectAttempt } = get()
      if (!isRunning || stillWorkflowId !== myWorkflowId) return

      const nextAttempt = Math.min(wsReconnectAttempt + 1, 8)
      set({ wsReconnectAttempt: nextAttempt })
      const delayMs = Math.min(1000 * 2 ** (nextAttempt - 1), 15000)
      setTimeout(() => {
        const { isRunning: r2, workflowId: wid2, ws: existingWs } = get()
        if (!r2 || wid2 !== myWorkflowId || existingWs) return
        get().connectWebSocket(myWorkflowId)
      }, delayMs)
    }

    // Keepalive ping
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      } else {
        clearInterval(pingInterval)
      }
    }, 15000)
  },

  handleWsMessage: (msg) => {
    switch (msg.type) {
      case 'log':
        get().addLog(msg.payload)
        break
      case 'screenshot':
        if (msg.payload?.data) {
          const url = `data:image/jpeg;base64,${msg.payload.data}`
          set({ screenshotUrl: url, screenshotTimestamp: msg.payload.timestamp })
        }
        break
      case 'stage':
        set({ stage: msg.payload.stage, stageMessage: msg.payload.message || '' })
        if (['opening_browser', 'navigating', 'searching', 'extracting'].includes(msg.payload.stage)) {
          set({ activePanel: 'browser' })
        }
        if (msg.payload.stage === 'awaiting_selection') {
          set({ activePanel: 'chat' })
        }
        if (msg.payload.stage === 'filling_form') {
          set({ passengerFormVisible: true, activePanel: 'browser' })
        }
        if (['stopped_before_payment', 'completed', 'error'].includes(msg.payload.stage)) {
          set({ isRunning: false })
        }
        break
      case 'flights':
        set({ flights: msg.payload })
        get().addLog({
          level: 'success',
          agent: 'extraction',
          message: `${msg.payload.length} flights extracted and ready`,
        })
        break
      case 'plan':
        set({ plan: msg.payload })
        break
      case 'error':
        set({ error: msg.payload.error, isRunning: false })
        get().addLog({ level: 'error', agent: msg.payload.agent, message: msg.payload.error })
        break
    }
  },

  addLog: (entry) => {
    const log = {
      id: Date.now() + Math.random(),
      timestamp: entry.timestamp || new Date().toISOString(),
      level: entry.level || 'info',
      agent: entry.agent || 'system',
      message: entry.message,
      details: entry.details || {},
    }
    set((state) => ({ logs: [...state.logs.slice(-200), log] }))
  },

  setActivePanel: (panel) => set({ activePanel: panel }),
  setPassengerFormVisible: (v) => set({ passengerFormVisible: v }),
  clearError: () => set({ error: null }),
}))

export default useStore
