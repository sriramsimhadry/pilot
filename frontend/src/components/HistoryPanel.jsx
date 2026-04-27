import React from 'react'
import useStore from '../store/useStore.js'
import styles from './HistoryPanel.module.css'

export default function HistoryPanel() {
  const history = useStore((s) => s.dbHistory)
  const isLoading = useStore((s) => s.isLoadingHistory)

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.icon}>🕒</span>
        <h2>Past Searches</h2>
      </div>

      <div className={styles.list}>
        {isLoading ? (
          <div className={styles.empty}>
            <p>Loading history...</p>
          </div>
        ) : history.length === 0 ? (
          <div className={styles.empty}>
            <p>No past searches found.</p>
            <span>Searches you make in Mission Control will appear here.</span>
          </div>
        ) : (
          history.map((entry) => (
            <div key={entry.id} className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.date}>
                  {new Date(entry.id).toLocaleString()}
                </span>
                <span className={`${styles.statusBadge} ${styles[entry.status]}`}>
                  {entry.status === 'done' ? '✓ Completed' : 
                   entry.status === 'error' ? '⚠ Failed' : '⏳ Searching'}
                </span>
              </div>
              <div className={styles.routeBox}>
                <span className={styles.city}>{entry.origin || '?'}</span>
                <span className={styles.arrow}>{entry.is_round_trip ? '⇄' : '→'}</span>
                <span className={styles.city}>{entry.destination || '?'}</span>
                <span className={styles.datePill}>
                  {entry.date} {entry.is_round_trip && entry.return_date ? `- ${entry.return_date}` : ''}
                </span>
              </div>

              {entry.top3 && entry.top3.length > 0 && (
                <div className={styles.topFlights}>
                  <h4>Top 3 Recommendations</h4>
                  {entry.top3.map((flight, idx) => (
                    <div key={idx} className={styles.topFlightCard}>
                      <div className={styles.flightHeader}>
                        <span className={styles.airline}>{flight.airline} {flight.flight_number || ''}</span>
                        <span className={styles.rankBadge}>#{flight.rank}</span>
                      </div>
                      <p className={styles.reason}>{flight.reason}</p>
                      {flight.best_price_tip && (
                        <p className={styles.tip}>💡 {flight.best_price_tip}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}

            </div>
          ))
        )}
      </div>
    </div>
  )
}
