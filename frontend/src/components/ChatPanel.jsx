import React, { useState, useRef, useEffect, useCallback } from 'react'
import useStore from '../store/useStore.js'
import FlightCard from './FlightCard.jsx'
import FlightCardSkeleton from './FlightCardSkeleton.jsx'
import AISummaryCard from './AISummaryCard.jsx'
import styles from './ChatPanel.module.css'

const EXAMPLE_QUERIES = [
  'Book a flight from MAA to CCU on 15/05/2026',
  'Hyderabad to Delhi tomorrow',
  'Mumbai to Bangalore this Friday',
]

// Mic states
const MIC_IDLE       = 'idle'
const MIC_RECORDING  = 'recording'
const MIC_PROCESSING = 'processing'
const MIC_ERROR      = 'error'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export default function ChatPanel() {
  const [query, setQuery]               = useState('')
  const [micState, setMicState]         = useState(MIC_IDLE)
  const [micError, setMicError]         = useState(null)

  const inputRef        = useRef(null)
  const messagesEndRef  = useRef(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef        = useRef([])
  const streamRef        = useRef(null)

  const isRunning     = useStore((s) => s.isRunning)
  const stage         = useStore((s) => s.stage)
  const stageMessage  = useStore((s) => s.stageMessage)
  const chatHistory   = useStore((s) => s.chatHistory)
  const error         = useStore((s) => s.error)
  const startWorkflow = useStore((s) => s.startWorkflow)

  const canSearch   = query.trim().length > 5 && !isRunning
  const isAnalyzing = isRunning && stage === 'analyzing'

  // Scroll to bottom whenever history changes or loading state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory, isRunning, stageMessage, error])

  // Keyboard shortcut for mic (Ctrl+M)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'm') {
        e.preventDefault()
        handleMicClick()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [micState, isRunning])

  // ── Cleanup mic on unmount ───────────────────────────────────────
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  // ── Stop recording & send audio to backend ───────────────────────
  const sendAudioForTranscription = useCallback(async (chunks, mimeType) => {
    setMicState(MIC_PROCESSING)
    try {
      const blob     = new Blob(chunks, { type: mimeType })
      const formData = new FormData()
      formData.append('audio', blob, 'recording.webm')

      const res = await fetch(`${API_BASE}/api/transcribe`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Server error ${res.status}`)
      }

      const data = await res.json()
      if (data.text) {
        // Append transcription to whatever the user may have already typed
        setQuery((prev) => (prev.trim() ? prev.trim() + ' ' + data.text : data.text))
        inputRef.current?.focus()
      }
      setMicState(MIC_IDLE)
    } catch (err) {
      console.error('Transcription error:', err)
      setMicError(err.message || 'Transcription failed')
      setMicState(MIC_ERROR)
      // Auto-clear error after 3 s
      setTimeout(() => { setMicState(MIC_IDLE); setMicError(null) }, 3000)
    }
  }, [])

  // ── Start recording ──────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    setMicError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []

      // Pick best supported MIME type
      const mimeType = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
      ].find((t) => MediaRecorder.isTypeSupported(t)) || ''

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        streamRef.current = null
        sendAudioForTranscription(chunksRef.current, mimeType || 'audio/webm')
      }

      recorder.start(250) // collect chunks every 250 ms
      setMicState(MIC_RECORDING)
    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setMicError('Mic access denied — please allow microphone permission')
      } else {
        setMicError('Could not start recording')
      }
      setMicState(MIC_ERROR)
      setTimeout(() => { setMicState(MIC_IDLE); setMicError(null) }, 3000)
    }
  }, [sendAudioForTranscription])

  // ── Stop recording ───────────────────────────────────────────────
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && micState === MIC_RECORDING) {
      mediaRecorderRef.current.stop()
      // state transitions to MIC_PROCESSING inside onstop
    }
  }, [micState])

  // ── Toggle mic button ────────────────────────────────────────────
  const handleMicClick = useCallback(() => {
    if (isRunning) return
    if (micState === MIC_IDLE)      startRecording()
    else if (micState === MIC_RECORDING) stopRecording()
  }, [micState, isRunning, startRecording, stopRecording])

  // ── Form submit ──────────────────────────────────────────────────
  const handleSubmit = (e) => {
    e.preventDefault()
    if (!canSearch) return
    startWorkflow(query.trim())
    setQuery('')
  }

  const handleExample = (q) => {
    setQuery(q)
    inputRef.current?.focus()
  }

  // ── Mic button visual helpers ────────────────────────────────────
  const micLabel = {
    [MIC_IDLE]:       '🎤',
    [MIC_RECORDING]:  '⏹',
    [MIC_PROCESSING]: '⏳',
    [MIC_ERROR]:      '⚠',
  }[micState]

  const micTitle = {
    [MIC_IDLE]:       'Click to speak',
    [MIC_RECORDING]:  'Recording… click to stop',
    [MIC_PROCESSING]: 'Transcribing…',
    [MIC_ERROR]:      micError || 'Error',
  }[micState]

  return (
    <div className={styles.container}>
      <div className={styles.chatArea}>
        {chatHistory.length === 0 ? (
          <div className={styles.welcomeScreen}>
            <h2>Where do you want to fly?</h2>
            <p className={styles.welcomeSub}>Type your query below or <strong>speak</strong> using the mic 🎤 (Ctrl+M)</p>
            <div className={styles.exampleChips}>
              {EXAMPLE_QUERIES.map((q) => (
                <button key={q} className={styles.chip} onClick={() => handleExample(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className={styles.messagesList}>
            {chatHistory.map((entry, idx) => {
              const isLast = idx === chatHistory.length - 1
              const showSkeletons = isLast && entry.status === 'searching' && entry.flights.length === 0

              return (
                <React.Fragment key={entry.id}>
                  {/* ── User message ── */}
                  <div className={styles.messageRowUser}>
                    <div className={styles.userBubble}>{entry.query}</div>
                  </div>

                  {/* ── Bot message 1: Searching / Flights list ── */}
                  <div className={styles.messageRowBot}>
                    <div className={styles.botAvatar}>A</div>
                    <div className={styles.botContent}>
                      {entry.status === 'error' ? (
                        <div className={styles.errorBubble}>⚠ {isLast && error ? error : 'Search failed.'}</div>
                      ) : showSkeletons ? (
                        <div className={styles.flightsContainer}>
                          <div className={styles.statusBubble}>
                            <div className={styles.spinner} />
                            <span>{stageMessage || 'Searching for flights…'}</span>
                          </div>
                          <div className={styles.flightList}>
                            {[1, 2, 3, 4].map((i) => <FlightCardSkeleton key={i} />)}
                          </div>
                        </div>
                      ) : entry.flights.length > 0 ? (
                        <div className={styles.flightsContainer}>
                          <p className={styles.responseText}>
                            Here are the top {entry.flights.length} flights I found for you:
                          </p>
                          <div className={styles.flightList}>
                            {entry.flights.map((flight, i) => (
                              <FlightCard 
                                key={i} 
                                flight={flight} 
                                selectable={false} 
                                allFlights={entry.flights} 
                              />
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className={styles.statusBubble}>
                          <span>No flights found.</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* ── Bot message 2: AI Analysis ── */}
                  {entry.flights.length > 0 && (
                    <div className={styles.messageRowBot}>
                      <div className={styles.botAvatar}>A</div>
                      <div className={styles.botContent}>
                        {isLast && isAnalyzing && !entry.summary ? (
                          <div className={styles.analyzingBubble}>
                            <div className={styles.analyzeSpinner} />
                            <div className={styles.analyzeTextBlock}>
                              <span className={styles.analyzeTitle}>
                                AI is analysing all {entry.flights.length} flights…
                              </span>
                              <span className={styles.analyzeSubtitle}>Finding the top 3 picks for you</span>
                            </div>
                          </div>
                        ) : entry.summary ? (
                          <AISummaryCard summary={entry.summary} plan={entry.plan} />
                        ) : null}
                      </div>
                    </div>
                  )}
                </React.Fragment>
              )
            })}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* ── Input area ── */}
      <div className={styles.inputArea}>
        {/* Mic error toast */}
        {micState === MIC_ERROR && micError && (
          <div className={styles.micErrorToast}>{micError}</div>
        )}

        <form onSubmit={handleSubmit} className={styles.form}>
          {/* Mic button */}
          <button
            type="button"
            className={`${styles.micBtn} ${styles[`micBtn_${micState}`]}`}
            onClick={handleMicClick}
            disabled={isRunning || micState === MIC_PROCESSING}
            title={micTitle}
            aria-label={micTitle}
          >
            <span className={styles.micIcon}>{micLabel}</span>
            {micState === MIC_RECORDING && <span className={styles.micRipple} />}
          </button>

          <input
            ref={inputRef}
            className={styles.input}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              micState === MIC_RECORDING  ? 'Listening…' :
              micState === MIC_PROCESSING ? 'Transcribing your voice…' :
              'Type or speak your flight request…'
            }
            disabled={isRunning || micState === MIC_RECORDING}
            autoFocus
          />

          <button
            type="submit"
            className={styles.sendBtn}
            disabled={!canSearch}
          >
            ↑
          </button>
        </form>

        <div className={styles.footerNote}>
          Aeroo AI · Speak or type · Powered by Groq Whisper
        </div>
      </div>
    </div>
  )
}
