import React, { useState } from 'react'
import styles from './PlanView.module.css'

export default function PlanView({ plan }) {
  const [expanded, setExpanded] = useState(false)
  if (!plan) return null

  const { parsed, steps } = plan

  return (
    <div className={styles.planView}>
      <div className={styles.planHeader} onClick={() => setExpanded(!expanded)}>
        <div className={styles.planTitleRow}>
          <span className={styles.planIcon}>◈</span>
          <span className={styles.planTitle}>EXECUTION PLAN</span>
          <span className={styles.toggle}>{expanded ? '▲' : '▼'}</span>
        </div>
        <div className={styles.routeSummary}>
          <span className={styles.city}>{parsed.origin?.display || '?'}</span>
          <span className={styles.arrow}>→</span>
          <span className={styles.city}>{parsed.destination?.display || '?'}</span>
          <span className={styles.datePill}>{parsed.date}</span>
          <span className={styles.passPill}>{parsed.passengers} pax · {parsed.class}</span>
        </div>
      </div>

      {expanded && (
        <div className={styles.steps}>
          {steps.map((step, i) => (
            <div key={step.id} className={styles.step}>
              <div className={styles.stepNum}>{String(step.id).padStart(2, '0')}</div>
              <div className={styles.stepContent}>
                <span className={styles.stepName}>{step.name.replace(/_/g, ' ')}</span>
                <span className={styles.stepDesc}>{step.description}</span>
              </div>
              <div className={`${styles.agentTag} ${styles[step.agent]}`}>
                {step.agent}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
