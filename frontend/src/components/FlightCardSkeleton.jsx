import React from 'react'
import styles from './FlightCardSkeleton.module.css'

export default function FlightCardSkeleton() {
  return (
    <div className={styles.card}>
      {/* Airline strip */}
      <div className={styles.airlineStrip}>
        <div className={`${styles.skel} ${styles.badge}`} />
        <div className={styles.metaCol}>
          <div className={`${styles.skel} ${styles.name}`} />
          <div className={`${styles.skel} ${styles.num}`} />
        </div>
        <div className={`${styles.skel} ${styles.stopBadge}`} />
      </div>

      {/* Times row */}
      <div className={styles.timesRow}>
        <div className={styles.timeBlock}>
          <div className={`${styles.skel} ${styles.time}`} />
          <div className={`${styles.skel} ${styles.label}`} />
        </div>

        <div className={styles.routeCenter}>
          <div className={`${styles.skel} ${styles.routeLine}`} />
        </div>

        <div className={styles.timeBlock}>
          <div className={`${styles.skel} ${styles.time}`} />
          <div className={`${styles.skel} ${styles.label}`} />
        </div>

        <div className={styles.priceBlock}>
          <div className={`${styles.skel} ${styles.price}`} />
          <div className={`${styles.skel} ${styles.priceLabel}`} />
        </div>
      </div>
    </div>
  )
}
