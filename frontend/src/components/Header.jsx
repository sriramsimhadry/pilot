import React from 'react'
import useStore from '../store/useStore.js'
import styles from './Header.module.css'

const PANELS = [
  { id: 'chat', label: 'Mission Control', icon: '◈' },
  { id: 'browser', label: 'Live Browser', icon: '◉' },
  { id: 'logs', label: 'Agent Logs', icon: '◎' },
]

const STAGE_LABELS = {
  idle: { label: 'STANDBY', color: 'muted' },
  planning: { label: 'PLANNING', color: 'accent' },
  opening_browser: { label: 'LAUNCHING', color: 'accent' },
  navigating: { label: 'NAVIGATING', color: 'accent' },
  searching: { label: 'SEARCHING', color: 'accent' },
  extracting: { label: 'EXTRACTING', color: 'amber' },
  awaiting_selection: { label: 'AWAITING INPUT', color: 'amber' },
  filling_form: { label: 'FILLING FORM', color: 'accent' },
  stopped_before_payment: { label: 'MISSION COMPLETE', color: 'green' },
  completed: { label: 'COMPLETED', color: 'green' },
  error: { label: 'ERROR', color: 'error' },
}

export default function Header() {
  const activePanel = useStore((s) => s.activePanel)
  const setActivePanel = useStore((s) => s.setActivePanel)
  const stage = useStore((s) => s.stage)
  const isRunning = useStore((s) => s.isRunning)

  const stageInfo = STAGE_LABELS[stage] || STAGE_LABELS.idle

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <span className={styles.logo}>✈</span>
        <div className={styles.brandText}>
          <span className={styles.brandName}>AGENTIC AI</span>
          <span className={styles.brandSub}>FLIGHT AUTOMATION SYSTEM</span>
        </div>
      </div>

      <nav className={styles.nav}>
        {PANELS.map((p) => (
          <button
            key={p.id}
            className={`${styles.navBtn} ${activePanel === p.id ? styles.navBtnActive : ''}`}
            onClick={() => setActivePanel(p.id)}
          >
            <span className={styles.navIcon}>{p.icon}</span>
            <span>{p.label}</span>
          </button>
        ))}
      </nav>

      <div className={styles.status}>
        <span className={`${styles.statusDot} ${styles[stageInfo.color]} ${isRunning ? styles.pulsing : ''}`} />
        <span className={`${styles.statusLabel} ${styles[stageInfo.color]}`}>
          {stageInfo.label}
        </span>
      </div>
    </header>
  )
}
