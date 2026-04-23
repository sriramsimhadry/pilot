import React, { useState } from 'react'
import useStore from '../store/useStore.js'
import styles from './PassengerModal.module.css'

const INITIAL_STATE = {
  first_name: '',
  last_name: '',
  age: '',
  gender: 'male',
  email: '',
  phone: '',
}

export default function PassengerModal() {
  const [form, setForm] = useState(INITIAL_STATE)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const submitPassenger = useStore((s) => s.submitPassenger)
  const setPassengerFormVisible = useStore((s) => s.setPassengerFormVisible)

  const validate = () => {
    const errs = {}
    if (!form.first_name.trim()) errs.first_name = 'Required'
    if (!form.last_name.trim()) errs.last_name = 'Required'
    const age = parseInt(form.age)
    if (!form.age || isNaN(age) || age < 2 || age > 120) errs.age = 'Enter valid age (2–120)'
    return errs
  }

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: null }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }
    setSubmitting(true)
    await submitPassenger({ ...form, age: parseInt(form.age) })
    setSubmitting(false)
  }

  return (
    <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && setPassengerFormVisible(false)}>
      <div className={styles.modal}>
        <div className={styles.modalHeader}>
          <div className={styles.headerLeft}>
            <span className={styles.modalIcon}>👤</span>
            <div>
              <div className={styles.modalTitle}>PASSENGER DETAILS</div>
              <div className={styles.modalSub}>The agent will fill these into the booking form</div>
            </div>
          </div>
          <button className={styles.closeBtn} onClick={() => setPassengerFormVisible(false)}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {/* Name row */}
          <div className={styles.row}>
            <div className={styles.field}>
              <label className={styles.label}>FIRST NAME <span className={styles.req}>*</span></label>
              <input
                className={`${styles.input} ${errors.first_name ? styles.inputError : ''}`}
                value={form.first_name}
                onChange={(e) => handleChange('first_name', e.target.value)}
                placeholder="e.g. Arjun"
                autoFocus
              />
              {errors.first_name && <span className={styles.error}>{errors.first_name}</span>}
            </div>
            <div className={styles.field}>
              <label className={styles.label}>LAST NAME <span className={styles.req}>*</span></label>
              <input
                className={`${styles.input} ${errors.last_name ? styles.inputError : ''}`}
                value={form.last_name}
                onChange={(e) => handleChange('last_name', e.target.value)}
                placeholder="e.g. Sharma"
              />
              {errors.last_name && <span className={styles.error}>{errors.last_name}</span>}
            </div>
          </div>

          {/* Age + Gender row */}
          <div className={styles.row}>
            <div className={styles.field}>
              <label className={styles.label}>AGE <span className={styles.req}>*</span></label>
              <input
                className={`${styles.input} ${errors.age ? styles.inputError : ''}`}
                type="number"
                value={form.age}
                onChange={(e) => handleChange('age', e.target.value)}
                placeholder="e.g. 28"
                min="2"
                max="120"
              />
              {errors.age && <span className={styles.error}>{errors.age}</span>}
            </div>
            <div className={styles.field}>
              <label className={styles.label}>GENDER</label>
              <div className={styles.genderGroup}>
                {['male', 'female', 'other'].map((g) => (
                  <button
                    key={g}
                    type="button"
                    className={`${styles.genderBtn} ${form.gender === g ? styles.genderActive : ''}`}
                    onClick={() => handleChange('gender', g)}
                  >
                    {g === 'male' ? '♂' : g === 'female' ? '♀' : '⚥'} {g}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Contact info */}
          <div className={styles.row}>
            <div className={styles.field}>
              <label className={styles.label}>EMAIL <span className={styles.opt}>(optional)</span></label>
              <input
                className={styles.input}
                type="email"
                value={form.email}
                onChange={(e) => handleChange('email', e.target.value)}
                placeholder="arjun@example.com"
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label}>PHONE <span className={styles.opt}>(optional)</span></label>
              <input
                className={styles.input}
                type="tel"
                value={form.phone}
                onChange={(e) => handleChange('phone', e.target.value)}
                placeholder="9876543210"
              />
            </div>
          </div>

          {/* Warning */}
          <div className={styles.warningBox}>
            <span className={styles.warningIcon}>⚠</span>
            <span>The agent will stop before the payment page. No booking will be completed.</span>
          </div>

          {/* Actions */}
          <div className={styles.actions}>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnCancel}`}
              onClick={() => setPassengerFormVisible(false)}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={`${styles.btn} ${styles.btnSubmit}`}
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <span className={styles.btnSpinner} />
                  Sending to Agent...
                </>
              ) : (
                <>▶ SEND TO AGENT</>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
