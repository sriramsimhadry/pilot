import React, { useEffect, useRef, useState } from 'react'
import useStore from '../store/useStore.js'
import styles from './LogsPanel.module.css'

const AGENT_CONFIG = {
  orchestrator: { color: '#a855f7', icon: '◈' },
  planner: { color: '#38bdf8', icon: '◎' },
  browser: { color: '#0ea5e9', icon: '◉' },
  extraction: { color: '#f59e0b', icon: '◆' },
  analysis: { color: '#a78bfa', icon: '✦' },
  form_filling: { color: '#22c55e', icon: '◇' },
  vision: { color: '#f97316', icon: '◐' },
  system: { color: '#64748b', icon: '○' },
  user: { color: '#e2e8f0', icon: '●' },
}

const LEVEL_STYLES = {
  info: { color: 'var(--text-secondary)', prefix: '  ' },
  success: { color: 'var(--text-success)', prefix: '✓ ' },
  warning: { color: 'var(--text-warning)', prefix: '⚠ ' },
  error: { color: 'var(--text-error)', prefix: '✗ ' },
}

export default function LogsPanel() {
  const logs = useStore((s) => s.logs)
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState('all')
  const bottomRef = useRef(null)
  const containerRef = useRef(null)

  const AGENTS = ['all', ...Object.keys(AGENT_CONFIG)]

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    setAutoScroll(isAtBottom)
  }

  const filteredLogs = filter === 'all'
    ? logs
    : logs.filter((l) => l.agent === filter)

  const formatTime = (ts) => {
    if (!ts) return ''
    try {
      return new Date(ts).toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      })
    } catch {
      return ''
    }
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>AGENT LOGS</span>
        <div className={styles.controls}>
          <span className={styles.logCount}>{logs.length}</span>
          <button
            className={`${styles.scrollBtn} ${autoScroll ? styles.active : ''}`}
            onClick={() => setAutoScroll(!autoScroll)}
            title="Auto-scroll"
          >
            ↓
          </button>
        </div>
      </div>

      {/* Agent filter chips */}
      <div className={styles.filters}>
        {AGENTS.map((agent) => (
          <button
            key={agent}
            className={`${styles.filterChip} ${filter === agent ? styles.filterActive : ''}`}
            onClick={() => setFilter(agent)}
            style={
              filter === agent && agent !== 'all'
                ? { '--chip-color': AGENT_CONFIG[agent]?.color || 'var(--accent)' }
                : {}
            }
          >
            {agent !== 'all' && (
              <span style={{ color: AGENT_CONFIG[agent]?.color }}>{AGENT_CONFIG[agent]?.icon}</span>
            )}
            {agent}
          </button>
        ))}
      </div>

      {/* Log stream */}
      <div className={styles.logStream} ref={containerRef} onScroll={handleScroll}>
        {filteredLogs.length === 0 && (
          <div className={styles.emptyLogs}>
            <span className={styles.emptyIcon}>◎</span>
            <span>No logs yet. Start a workflow to see agent activity.</span>
          </div>
        )}

        {filteredLogs.map((log) => {
          const agentCfg = AGENT_CONFIG[log.agent] || AGENT_CONFIG.system
          const levelStyle = LEVEL_STYLES[log.level] || LEVEL_STYLES.info

          return (
            <div key={log.id} className={`${styles.logEntry} ${styles[log.level]}`}>
              <span className={styles.logTime}>{formatTime(log.timestamp)}</span>
              <span className={styles.logAgent} style={{ color: agentCfg.color }}>
                {agentCfg.icon} {log.agent}
              </span>
              <span className={styles.logMessage} style={{ color: levelStyle.color }}>
                {levelStyle.prefix}{log.message}
              </span>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>

      {/* Legend */}
      <div className={styles.legend}>
        {Object.entries(AGENT_CONFIG).slice(0, 5).map(([name, cfg]) => (
          <div key={name} className={styles.legendItem}>
            <span style={{ color: cfg.color }}>{cfg.icon}</span>
            <span className={styles.legendLabel}>{name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
