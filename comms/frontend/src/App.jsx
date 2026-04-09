import { Routes, Route, Navigate } from 'react-router-dom'
import { WorkspaceLayout } from './v2/components'
import { ClassicLayout } from './components'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<WorkspaceLayout />} />
      <Route path="/classic/*" element={<ClassicLayout />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
