import React, { useState } from 'react'
import useStore from '../store/useStore.js'
import styles from './BrowserPanel.module.css'

export default function BrowserPanel() {
  const screenshotUrl = useStore((s) => s.screenshotUrl)
  const screenshotTimestamp = useStore((s) => s.screenshotTimestamp)
  const stage = useStore((s) => s.stage)
  const isRunning = useStore((s) => s.isRunning)
  const [zoom, setZoom] = useState(false)

  const isIdle = stage === 'idle'
  const hasScreen = Boolean(screenshotUrl)

  const formatTime = (ts) => {
    if (!ts) return ''
    return new Date(ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <div className={styles.headerLeft}>
          <span className={styles.panelTitle}>LIVE BROWSER</span>
          {isRunning && (
            <div className={styles.liveIndicator}>
              <span className={styles.liveDot} />
              <span className={styles.liveLabel}>LIVE</span>
            </div>
          )}
        </div>
        <div className={styles.headerRight}>
          {screenshotTimestamp && (
            <span className={styles.timestamp}>{formatTime(screenshotTimestamp)}</span>
          )}
          {hasScreen && (
            <button
              className={styles.zoomBtn}
              onClick={() => setZoom(!zoom)}
              title={zoom ? 'Fit screen' : 'Fill screen'}
            >
              {zoom ? '⊡' : '⊞'}
            </button>
          )}
        </div>
      </div>

      {/* Address bar simulation */}
      {hasScreen && (
        <div className={styles.addressBar}>
          <span className={styles.lockIcon}>🔒</span>
          <span className={styles.url}>makemytrip.com</span>
          <span className={styles.agentBadge}>AGENT CONTROLLED</span>
        </div>
      )}

      {/* Screen area */}
      <div className={`${styles.screenArea} ${zoom ? styles.zoomFit : ''}`}>
        {isIdle && !hasScreen && (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>◉</div>
            <div className={styles.emptyTitle}>Browser Standby</div>
            <div className={styles.emptyDesc}>
              Start a workflow to launch the browser.<br />
              You'll watch the AI operate MakeMyTrip in real time.
            </div>
            <div className={styles.featureList}>
              <div className={styles.feature}><span>✦</span> Visible Chromium browser</div>
              <div className={styles.feature}><span>✦</span> Live screenshot stream</div>
              <div className={styles.feature}><span>✦</span> Human-like interactions</div>
              <div className={styles.feature}><span>✦</span> Auto popup dismissal</div>
            </div>
          </div>
        )}

        {!isIdle && !hasScreen && (
          <div className={styles.loadingState}>
            <div className={styles.loadingSpinner} />
            <div className={styles.loadingText}>Launching browser...</div>
            <div className={styles.loadingGrid}>
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className={styles.loadingCell} style={{ animationDelay: `${i * 0.1}s` }} />
              ))}
            </div>
          </div>
        )}

        {hasScreen && (
          <div className={styles.screenshotWrapper}>
            <img
              src={screenshotUrl}
              alt="Live browser view"
              className={styles.screenshot}
            />
            {/* Scan line effect */}
            <div className={styles.scanLine} />
          </div>
        )}
      </div>

      {/* Bottom bar */}
      <div className={styles.bottomBar}>
        <div className={styles.browserInfo}>
          <span className={styles.browserBadge}>Chromium</span>
          <span className={styles.resolution}>1440 × 900</span>
        </div>
        <div className={styles.agentInfo}>
          <span className={styles.agentDot} data-active={isRunning} />
          <span className={styles.agentStatus}>
            {isRunning ? 'Agent Active' : 'Agent Idle'}
          </span>
        </div>
      </div>
    </div>
  )
}
