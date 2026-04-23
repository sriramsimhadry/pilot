import React from 'react'
import useStore from '../store/useStore.js'
import styles from './StatusBar.module.css'

const STEPS = [
  { stage: 'planning', label: 'Plan' },
  { stage: 'opening_browser', label: 'Launch' },
  { stage: 'navigating', label: 'Navigate' },
  { stage: 'searching', label: 'Search' },
  { stage: 'extracting', label: 'Extract' },
  { stage: 'awaiting_selection', label: 'Select' },
  { stage: 'filling_form', label: 'Fill' },
  { stage: 'stopped_before_payment', label: 'Done' },
]

const STAGE_ORDER = STEPS.map((s) => s.stage)

export default function StatusBar() {
  const stage = useStore((s) => s.stage)
  const stageMessage = useStore((s) => s.stageMessage)
  const isRunning = useStore((s) => s.isRunning)

  if (stage === 'idle') return null

  const currentIndex = STAGE_ORDER.indexOf(stage)

  return (
    <div className={styles.bar}>
      <div className={styles.steps}>
        {STEPS.map((step, i) => {
          const isDone = currentIndex > i
          const isActive = currentIndex === i
          return (
            <React.Fragment key={step.stage}>
              <div className={`${styles.step} ${isDone ? styles.done : ''} ${isActive ? styles.active : ''}`}>
                <span className={styles.stepDot}>
                  {isDone ? '✓' : isActive ? '●' : '○'}
                </span>
                <span className={styles.stepLabel}>{step.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`${styles.connector} ${isDone ? styles.connectorDone : ''}`} />
              )}
            </React.Fragment>
          )
        })}
      </div>
      {stageMessage && (
        <div className={styles.message}>
          {isRunning && <span className={styles.spinner} />}
          <span>{stageMessage}</span>
        </div>
      )}
    </div>
  )
}
