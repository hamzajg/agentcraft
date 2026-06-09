import { Routes, Route, Navigate } from 'react-router-dom'
import { GlobalLayout } from './components'
import { LandingPage } from './pages/LandingPage'
import { HermesRouter } from './hermes/HermesRouter'
import './styles/design-system.css'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/workspace/*" element={<GlobalLayout />} />
      <Route path="/hermes/*" element={<HermesRouter />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

