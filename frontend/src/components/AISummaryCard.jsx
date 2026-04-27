import React, { useState, useEffect, useRef, useCallback } from 'react'
import styles from './AISummaryCard.module.css'

const RANK_EMOJI  = ['🥇', '🥈', '🥉']
const RANK_LABEL  = ['Best Pick', '2nd Best', '3rd Best']
const RANK_ORDINAL = ['First', 'Second', 'Third']

const BOOKING_URLS = {
  'MakeMyTrip':    'https://www.makemytrip.com/flights/',
  'Cleartrip':     'https://www.cleartrip.com/flights/',
  'EaseMyTrip':    'https://www.easemytrip.com/',
  'Airline Direct': null,
  'Ixigo':         'https://www.ixigo.com/flights',
}

const AIRLINE_BOOKING_URLS = {
  'IndiGo':        'https://www.goindigo.in/',
  'Air India':     'https://www.airindia.com/',
  'SpiceJet':      'https://www.spicejet.com/',
  'Vistara':       'https://www.airvistara.com/',
  'Akasa Air':     'https://www.akasaair.com/',
  'AirAsia India': 'https://www.airasia.com/en/gb.html',
}

function getBookingUrl(site, airline) {
  if (site === 'Airline Direct') return AIRLINE_BOOKING_URLS[airline] || 'https://www.google.com/flights'
  return BOOKING_URLS[site] || '#'
}

// ── Speech synthesis helpers ─────────────────────────────────────────────────

const TTS_SUPPORTED = typeof window !== 'undefined' && 'speechSynthesis' in window

/**
 * Pick the best available English voice.
 * Priority: Google UK/US > Microsoft > Apple Alex > any en-IN > any English
 */
function pickBestVoice() {
  if (!TTS_SUPPORTED) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null

  const priority = [
    (v) => /Google UK English Female/i.test(v.name),
    (v) => /Google US English/i.test(v.name),
    (v) => /Microsoft Aria/i.test(v.name),
    (v) => /Microsoft David/i.test(v.name),
    (v) => /Alex/i.test(v.name),                      // macOS
    (v) => v.lang === 'en-IN',                         // Indian English
    (v) => v.lang.startsWith('en-'),
    (v) => v.lang.startsWith('en'),
  ]

  for (const test of priority) {
    const match = voices.find(test)
    if (match) return match
  }
  return voices[0]
}

/**
 * Build the full speech script from top3 data.
 */
function buildSpeechScript(overall_summary, top3, plan) {
  const lines = []
  if (overall_summary) lines.push(overall_summary + '. ')

  let intro = 'Here are your top 3 flight recommendations. '
  if (plan && plan.parsed && plan.parsed.origin && plan.parsed.destination) {
    intro = `For your flight from ${plan.parsed.origin.display} to ${plan.parsed.destination.display} on ${plan.parsed.date}, here are your top 3 picks. `
  }
  lines.push(intro)

  top3.forEach((pick, idx) => {
    lines.push(
      `${RANK_ORDINAL[idx]} pick: ${pick.airline}` +
      (pick.flight_number ? `, flight ${pick.flight_number}. ` : '. ')
    )
    if (pick.reason)        lines.push(pick.reason + '. ')
    if (pick.best_price_tip) lines.push('Booking tip: ' + pick.best_price_tip + '. ')
    if (pick.book_on?.length) {
      lines.push('You can book this on ' + pick.book_on.join(' or ') + '. ')
    }
  })

  lines.push('Those are your recommendations. Happy flying!')
  return lines.join(' ')
}

// ── Speech state machine ─────────────────────────────────────────────────────
const SPEECH_IDLE     = 'idle'      // not speaking
const SPEECH_SPEAKING = 'speaking'  // currently reading out
const SPEECH_PAUSED   = 'paused'    // paused mid-speech

// ── Permission states ────────────────────────────────────────────────────────
const PERM_PENDING   = 'pending'    // banner visible, awaiting choice
const PERM_ACCEPTED  = 'accepted'   // user said yes
const PERM_DECLINED  = 'declined'   // user said no — banner hidden

// ────────────────────────────────────────────────────────────────────────────

/**
 * AISummaryCard
 * Renders the structured Groq analysis result.
 * Includes TTS permission banner + offline speech playback.
 *
 * `summary` can be:
 *   - A dict: { overall_summary, top3: [...] }
 *   - A plain string (fallback)
 *   - null / undefined
 */
export default function AISummaryCard({ summary, plan }) {
  const [permState,   setPermState]   = useState(PERM_PENDING)
  const [speechState, setSpeechState] = useState(SPEECH_IDLE)
  const [speakingIdx, setSpeakingIdx] = useState(-1)   // which pick is being read (-1 = intro)
  const utteranceRef = useRef(null)

  // Cancel speech when component unmounts (e.g. new search starts)
  useEffect(() => {
    return () => {
      if (TTS_SUPPORTED) window.speechSynthesis.cancel()
    }
  }, [])

  // ── Speak function ─────────────────────────────────────────────────
  const startSpeaking = useCallback((top3, overall_summary, planData) => {
    if (!TTS_SUPPORTED) return
    window.speechSynthesis.cancel()

    const fullScript = buildSpeechScript(overall_summary, top3, planData)
    const utter      = new SpeechSynthesisUtterance(fullScript)

    // Voice selection — voices may load async on some browsers
    const applyVoice = () => {
      const voice = pickBestVoice()
      if (voice) utter.voice = voice
    }
    applyVoice()
    if (!window.speechSynthesis.getVoices().length) {
      window.speechSynthesis.onvoiceschanged = applyVoice
    }

    utter.rate   = 0.92   // slightly slower for clarity
    utter.pitch  = 1.05
    utter.volume = 1.0

    // Track which pick is being spoken by word boundary events
    // We approximate: after intro segment, highlight picks sequentially
    let charOffset = 0
    const pickStartChars = []
    if (overall_summary) charOffset += overall_summary.length + 3
    
    let intro = 'Here are your top 3 flight recommendations.  '
    if (planData && planData.parsed && planData.parsed.origin && planData.parsed.destination) {
      intro = `For your flight from ${planData.parsed.origin.display} to ${planData.parsed.destination.display} on ${planData.parsed.date}, here are your top 3 picks.  `
    }
    charOffset += intro.length

    top3.forEach((pick, idx) => {
      pickStartChars.push(charOffset)
      const seg =
        `${RANK_ORDINAL[idx]} pick: ${pick.airline}` +
        (pick.flight_number ? `, flight ${pick.flight_number}.  ` : '.  ') +
        (pick.reason ? pick.reason + '.  ' : '') +
        (pick.best_price_tip ? 'Booking tip: ' + pick.best_price_tip + '.  ' : '') +
        (pick.book_on?.length ? 'You can book this on ' + pick.book_on.join(' or ') + '.  ' : '')
      charOffset += seg.length + 1
    })

    utter.onboundary = (e) => {
      if (e.name !== 'word') return
      const pos = e.charIndex
      let activeIdx = -1
      for (let i = pickStartChars.length - 1; i >= 0; i--) {
        if (pos >= pickStartChars[i]) { activeIdx = i; break }
      }
      setSpeakingIdx(activeIdx)
    }

    utter.onstart = () => setSpeechState(SPEECH_SPEAKING)
    utter.onend   = () => { setSpeechState(SPEECH_IDLE); setSpeakingIdx(-1) }
    utter.onerror = () => { setSpeechState(SPEECH_IDLE); setSpeakingIdx(-1) }

    utteranceRef.current = utter
    window.speechSynthesis.speak(utter)
    setSpeechState(SPEECH_SPEAKING)
  }, [])

  const pauseSpeech = useCallback(() => {
    if (TTS_SUPPORTED) window.speechSynthesis.pause()
    setSpeechState(SPEECH_PAUSED)
  }, [])

  const resumeSpeech = useCallback(() => {
    if (TTS_SUPPORTED) window.speechSynthesis.resume()
    setSpeechState(SPEECH_SPEAKING)
  }, [])

  const stopSpeech = useCallback(() => {
    if (TTS_SUPPORTED) window.speechSynthesis.cancel()
    setSpeechState(SPEECH_IDLE)
    setSpeakingIdx(-1)
  }, [])

  // ── Permission handlers ───────────────────────────────────────────
  const handleAccept = useCallback(() => {
    setPermState(PERM_ACCEPTED)
    if (summary && typeof summary === 'object' && summary.top3?.length) {
      startSpeaking(summary.top3, summary.overall_summary, plan)
    }
  }, [summary, plan, startSpeaking])

  const handleDecline = useCallback(() => {
    setPermState(PERM_DECLINED)
    stopSpeech()
  }, [stopSpeech])

  // ────────────────────────────────────────────────────────────────────
  if (!summary) return null

  // ── Fallback: plain string ──────────────────────────────────────────
  if (typeof summary === 'string' || summary._raw) {
    const text = typeof summary === 'string' ? summary : summary.overall_summary
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <span className={styles.sparkle}>✨</span>
          <span className={styles.headerTitle}>AI Flight Analysis</span>
        </div>
        <p className={styles.fallbackText}>{text}</p>
      </div>
    )
  }

  const { overall_summary, top3 = [] } = summary

  return (
    <div className={styles.container}>

      {/* ── TTS Permission Banner ── */}
      {TTS_SUPPORTED && permState === PERM_PENDING && top3.length > 0 && (
        <div className={styles.permBanner}>
          <div className={styles.permLeft}>
            <span className={styles.permIcon}>🔊</span>
            <div className={styles.permText}>
              <span className={styles.permTitle}>Shall I read out the top 3 picks for you?</span>
              <span className={styles.permSub}>Uses your device's offline speech — no data sent</span>
            </div>
          </div>
          <div className={styles.permActions}>
            <button className={styles.permYes} onClick={handleAccept}>Yes, read it</button>
            <button className={styles.permNo}  onClick={handleDecline}>No thanks</button>
          </div>
        </div>
      )}

      {/* ── TTS Controls (shown after accepted) ── */}
      {TTS_SUPPORTED && permState === PERM_ACCEPTED && (
        <div className={styles.ttsControls}>
          <div className={styles.ttsLeft}>
            {speechState === SPEECH_SPEAKING && (
              <>
                <span className={styles.ttsSoundwave}>
                  {[1,2,3,4,5].map(i => <span key={i} className={styles.ttsBar} style={{'--i': i}} />)}
                </span>
                <span className={styles.ttsStatus}>Reading aloud…</span>
              </>
            )}
            {speechState === SPEECH_PAUSED  && <span className={styles.ttsStatus}>Paused</span>}
            {speechState === SPEECH_IDLE    && <span className={styles.ttsStatus}>Done reading</span>}
          </div>
          <div className={styles.ttsActions}>
            {speechState === SPEECH_IDLE && (
              <button className={styles.ttsBtn} onClick={() => startSpeaking(top3, overall_summary, plan)}>
                ▶ Replay
              </button>
            )}
            {speechState === SPEECH_SPEAKING && (
              <button className={styles.ttsBtn} onClick={pauseSpeech}>⏸ Pause</button>
            )}
            {speechState === SPEECH_PAUSED && (
              <button className={styles.ttsBtn} onClick={resumeSpeech}>▶ Resume</button>
            )}
            {speechState !== SPEECH_IDLE && (
              <button className={`${styles.ttsBtn} ${styles.ttsBtnStop}`} onClick={stopSpeech}>
                ⏹ Stop
              </button>
            )}
            <button className={styles.ttsDismiss} onClick={handleDecline} title="Dismiss voice">✕</button>
          </div>
        </div>
      )}

      {/* ── Header ── */}
      <div className={styles.header}>
        <span className={styles.sparkle}>✨</span>
        <div className={styles.headerText}>
          <span className={styles.headerTitle}>AI Recommendations</span>
          <span className={styles.headerSub}>Top 3 picks from {top3.length > 0 ? '20' : 'all'} flights</span>
        </div>
        <div className={styles.liveIndicator}>
          <span className={styles.liveDot} />
          <span className={styles.liveLabel}>Groq AI</span>
        </div>
      </div>

      {/* ── Overall summary ── */}
      {overall_summary && (
        <p className={styles.overallSummary}>{overall_summary}</p>
      )}

      {/* ── Top 3 Recommendation Cards ── */}
      <div className={styles.cardsList}>
        {top3.map((pick, idx) => (
          <div
            key={idx}
            className={`
              ${styles.pickCard}
              ${styles[`rank${idx + 1}`]}
              ${speakingIdx === idx ? styles.pickCardActive : ''}
            `}
          >
            {/* Rank badge */}
            <div className={styles.rankBadge}>
              <span className={styles.rankEmoji}>{RANK_EMOJI[idx] || `#${pick.rank}`}</span>
              <span className={styles.rankLabel}>{RANK_LABEL[idx] || `Rank ${pick.rank}`}</span>
            </div>

            {/* Flight info */}
            <div className={styles.pickBody}>
              <div className={styles.pickHeader}>
                <span className={styles.pickAirline}>{pick.airline}</span>
                {pick.flight_number && (
                  <span className={styles.pickFlightNum}>{pick.flight_number}</span>
                )}
                {/* Speaking indicator badge */}
                {speakingIdx === idx && (
                  <span className={styles.speakingBadge}>
                    🔊 <span>Reading…</span>
                  </span>
                )}
              </div>

              {/* Reason */}
              <div className={styles.reasonBlock}>
                <span className={styles.reasonIcon}>💡</span>
                <p className={styles.reasonText}>{pick.reason}</p>
              </div>

              {/* Price tip */}
              {pick.best_price_tip && (
                <div className={styles.priceTipBlock}>
                  <span className={styles.priceTipIcon}>💰</span>
                  <p className={styles.priceTipText}>{pick.best_price_tip}</p>
                </div>
              )}

              {/* Booking buttons */}
              {pick.book_on?.length > 0 && (
                <div className={styles.bookingRow}>
                  <span className={styles.bookOnLabel}>Book on:</span>
                  <div className={styles.bookingBtns}>
                    {pick.book_on.map((site) => (
                      <a
                        key={site}
                        href={getBookingUrl(site, pick.airline)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.bookBtn}
                      >
                        {site}
                        <span className={styles.externalIcon}>↗</span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <p className={styles.disclaimer}>
        Prices and availability may vary. Always confirm details on the booking platform.
      </p>
    </div>
  )
}
