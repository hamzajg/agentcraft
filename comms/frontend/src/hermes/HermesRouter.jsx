import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { HermesShell } from './layout/HermesShell'
import { HermesLanding } from './pages/HermesLanding'
import { HermesWorkspace } from './pages/HermesWorkspace'
import { ConstellationPage } from './pages/ConstellationPage'
import { RAGPanel } from '../components/RAGPanel'
import { MonitorPanel } from '../components/MonitorPanel'
import { EventsBusPanel } from '../components/EventsBusPanel'

export function HermesRouter() {
  return (
    <Routes>
      {/* Landing / Hero at /hermes */}
      <Route path="/" element={<HermesLanding />} />
      
      {/* Shell Layout for inner tabs */}
      <Route path="/*" element={<HermesShell />}>
        <Route path="workspace" element={<HermesWorkspace />} />
        <Route path="agents" element={<ConstellationPage />} />
        <Route path="rag" element={<RAGPanel />} />
        <Route path="monitor" element={<MonitorPanel />} />
        <Route path="events" element={<EventsBusPanel />} />
        
        {/* Redirect unknown routes inside shell to workspace */}
        <Route path="*" element={<Navigate to="workspace" replace />} />
      </Route>
    </Routes>
  )
}
