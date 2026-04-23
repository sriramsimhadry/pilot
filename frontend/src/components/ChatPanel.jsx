import React, { useState, useRef, useEffect } from 'react'
import useStore from '../store/useStore.js'
import FlightCard from './FlightCard.jsx'
import PlanView from './PlanView.jsx'
import styles from './ChatPanel.module.css'

const EXAMPLE_QUERIES = [
  'Hyderabad to Delhi tomorrow',
  'Mumbai to Bangalore this Friday',
  'Delhi to Goa next Monday morning',
  'Chennai to Kolkata day after tomorrow',
]

export default function ChatPanel() {
  const [query, setQuery] = useState('')
  const inputRef = useRef(null)

  const isRunning = useStore((s) => s.isRunning)
  const stage = useStore((s) => s.stage)
  const plan = useStore((s) => s.plan)
  const flights = useStore((s) => s.flights)
  const selectedFlightIndex = useStore((s) => s.selectedFlightIndex)
  const error = useStore((s) => s.error)
  const startWorkflow = useStore((s) => s.startWorkflow)
  const stopWorkflow = useStore((s) => s.stopWorkflow)
  const selectFlight = useStore((s) => s.selectFlight)
  const setPassengerFormVisible = useStore((s) => s.setPassengerFormVisible)

  const canSearch = query.trim().length > 5 && !isRunning

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!canSearch) return
    startWorkflow(query.trim())
  }

  const handleExample = (q) => {
    setQuery(q)
    inputRef.current?.focus()
  }

  const handleSelectFlight = (index) => {
    selectFlight(index)
  }

  const showFlightList = flights.length > 0
  const showPassengerBtn = stage === 'filling_form' || (showFlightList && selectedFlightIndex !== null && stage !== 'stopped_before_payment')
  const isMissionComplete = stage === 'stopped_before_payment'

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>MISSION CONTROL</span>
        <span className={styles.panelSub}>Enter your travel query</span>
      </div>

      {/* Query Input */}
      <div className={styles.inputSection}>
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.inputWrapper}>
            <span className={styles.inputPrefix}>›</span>
            <input
              ref={inputRef}
              className={styles.input}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Hyderabad to Delhi tomorrow"
              disabled={isRunning}
              autoFocus
            />
          </div>
          <div className={styles.formActions}>
            {!isRunning ? (
              <button
                type="submit"
                className={`${styles.btn} ${styles.btnPrimary}`}
                disabled={!canSearch}
              >
                <span>▶ LAUNCH AGENT</span>
              </button>
            ) : (
              <button
                type="button"
                className={`${styles.btn} ${styles.btnDanger}`}
                onClick={stopWorkflow}
              >
                <span>■ ABORT</span>
              </button>
            )}
          </div>
        </form>

        {/* Example queries */}
        {!isRunning && stage === 'idle' && (
          <div className={styles.examples}>
            <span className={styles.examplesLabel}>TRY:</span>
            <div className={styles.exampleChips}>
              {EXAMPLE_QUERIES.map((q) => (
                <button key={q} className={styles.chip} onClick={() => handleExample(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className={styles.errorBanner}>
          <span className={styles.errorIcon}>⚠</span>
          <span>{error}</span>
        </div>
      )}

      {/* Scrollable content area */}
      <div className={styles.content}>
        {/* Plan display */}
        {plan && !showFlightList && <PlanView plan={plan} />}

        {/* Mission complete banner */}
        {isMissionComplete && (
          <div className={styles.successBanner}>
            <div className={styles.successIcon}>✓</div>
            <div>
              <div className={styles.successTitle}>Mission Complete</div>
              <div className={styles.successSub}>Stopped before payment as instructed. Browser is ready for your review.</div>
            </div>
          </div>
        )}

        {/* Flight results */}
        {showFlightList && (
          <div className={styles.flightsSection}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionTitle}>
                FLIGHT RESULTS
                <span className={styles.badge}>{flights.length}</span>
              </span>
              {stage === 'awaiting_selection' && (
                <span className={styles.selectPrompt}>← Select a flight</span>
              )}
            </div>

            <div className={styles.flightList}>
              {flights.map((flight, i) => (
                <FlightCard
                  key={i}
                  flight={flight}
                  isSelected={selectedFlightIndex === i}
                  onSelect={() => handleSelectFlight(i)}
                  selectable={stage === 'awaiting_selection'}
                />
              ))}
            </div>
          </div>
        )}

        {/* Passenger form trigger */}
        {stage === 'filling_form' && selectedFlightIndex !== null && (
          <div className={styles.passengerPrompt}>
            <div className={styles.passengerIcon}>👤</div>
            <div>
              <div className={styles.passengerTitle}>Passenger Details Required</div>
              <div className={styles.passengerSub}>The agent is ready to fill the booking form.</div>
            </div>
            <button
              className={`${styles.btn} ${styles.btnAccent}`}
              onClick={() => setPassengerFormVisible(true)}
            >
              Enter Details
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
