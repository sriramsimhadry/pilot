import React from 'react'
import styles from './FlightCard.module.css'

const AIRLINE_COLORS = {
  'IndiGo': '#0047AB',
  'Air India': '#FF6B35',
  'SpiceJet': '#FF4500',
  'Vistara': '#6B3FA0',
  'Akasa Air': '#FF6B35',
  'AirAsia India': '#FF0000',
  'Go First': '#0085CA',
  'GoAir': '#0085CA',
}

const AIRLINE_CODES = {
  'IndiGo': '6E',
  'Air India': 'AI',
  'SpiceJet': 'SG',
  'Vistara': 'UK',
  'Akasa Air': 'QP',
  'AirAsia India': 'I5',
  'Go First': 'G8',
  'GoAir': 'G8',
}

export default function FlightCard({ flight, isSelected, onSelect, selectable }) {
  const accentColor = AIRLINE_COLORS[flight.airline] || '#38bdf8'
  const code = AIRLINE_CODES[flight.airline] || flight.airline?.slice(0, 2).toUpperCase() || '??'

  return (
    <div
      className={`${styles.card} ${isSelected ? styles.selected : ''} ${selectable ? styles.selectable : ''}`}
      onClick={selectable ? onSelect : undefined}
      style={{ '--airline-color': accentColor }}
    >
      {/* Airline strip */}
      <div className={styles.airlineStrip}>
        <div className={styles.airlineBadge}>
          <span className={styles.airlineCode}>{code}</span>
        </div>
        <div className={styles.airlineMeta}>
          <span className={styles.airlineName}>{flight.airline}</span>
          {flight.flight_number && (
            <span className={styles.flightNum}>{flight.flight_number}</span>
          )}
        </div>
        <div className={styles.stopsBadge} data-stops={flight.stops?.toLowerCase()}>
          {flight.stops || 'Non-stop'}
        </div>
      </div>

      {/* Times row */}
      <div className={styles.timesRow}>
        <div className={styles.timeBlock}>
          <span className={styles.time}>{flight.departure_time || '—'}</span>
          <span className={styles.timeLabel}>DEP</span>
        </div>

        <div className={styles.routeViz}>
          <div className={styles.routeLine} />
          {flight.duration && (
            <span className={styles.duration}>{flight.duration}</span>
          )}
          <span className={styles.planeIcon}>✈</span>
        </div>

        <div className={styles.timeBlock}>
          <span className={styles.time}>{flight.arrival_time || '—'}</span>
          <span className={styles.timeLabel}>ARR</span>
        </div>

        <div className={styles.priceBlock}>
          <span className={styles.price}>{flight.price}</span>
          <span className={styles.priceLabel}>per person</span>
        </div>
      </div>

      {isSelected && (
        <div className={styles.selectedBanner}>
          ✓ Selected
        </div>
      )}
    </div>
  )
}
