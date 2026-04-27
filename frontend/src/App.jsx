import React from 'react'
import useStore from './store/useStore.js'
import Header from './components/Header.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import HistoryPanel from './components/HistoryPanel.jsx'
import LogsPanel from './components/LogsPanel.jsx'
import PassengerModal from './components/PassengerModal.jsx'
import styles from './App.module.css'

export default function App() {
  const activePanel        = useStore((s) => s.activePanel)
  const passengerFormVisible = useStore((s) => s.passengerFormVisible)

  return (
    <div className={styles.app}>
      <Header />

      <main className={styles.main}>
        {/* Chat panel is always mounted (keeps state), only hidden visually */}
        <div className={`${styles.panel} ${activePanel === 'chat' ? styles.panelVisible : styles.panelHidden}`}>
          <ChatPanel />
        </div>

        <div className={`${styles.panel} ${activePanel === 'history' ? styles.panelVisible : styles.panelHidden}`}>
          <HistoryPanel />
        </div>

        <div className={`${styles.panel} ${activePanel === 'logs' ? styles.panelVisible : styles.panelHidden}`}>
          <LogsPanel />
        </div>
      </main>

      {/* Passenger modal — rendered above everything as an overlay */}
      {passengerFormVisible && <PassengerModal />}
    </div>
  )
}
