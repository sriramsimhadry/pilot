import React from 'react'
import Header from './components/Header.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import BrowserPanel from './components/BrowserPanel.jsx'
import LogsPanel from './components/LogsPanel.jsx'
import PassengerModal from './components/PassengerModal.jsx'
import StatusBar from './components/StatusBar.jsx'
import useStore from './store/useStore.js'
import styles from './App.module.css'

export default function App() {
  const activePanel = useStore((s) => s.activePanel)
  const passengerFormVisible = useStore((s) => s.passengerFormVisible)

  return (
    <div className={styles.app}>
      <Header />
      <StatusBar />

      <main className={styles.main}>
        {/* Left: Chat + Flights */}
        <section className={`${styles.panel} ${activePanel === 'chat' ? styles.active : ''}`}>
          <ChatPanel />
        </section>

        {/* Center: Live Browser */}
        <section className={`${styles.panel} ${styles.browserSection} ${activePanel === 'browser' ? styles.active : ''}`}>
          <BrowserPanel />
        </section>

        {/* Right: Agent Logs */}
        <section className={`${styles.panel} ${activePanel === 'logs' ? styles.active : ''}`}>
          <LogsPanel />
        </section>
      </main>

      {passengerFormVisible && <PassengerModal />}
    </div>
  )
}
