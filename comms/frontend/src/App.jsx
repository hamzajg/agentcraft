import { Routes, Route, Navigate } from 'react-router-dom'
import { GlobalLayout } from './components'
import { LandingPage } from './pages/LandingPage'
import HermesLayout from './hermes/components/HermesLayout'
import './styles/design-system.css'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/workspace/*" element={<GlobalLayout />} />
      <Route path="/hermes/*" element={<HermesLayout />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
