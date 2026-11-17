import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ToastProvider } from './components/Toast'
import { LightboxProvider } from './components/Lightbox'
import { Auth } from './features/auth/Auth'
import { Dashboard } from './features/dashboard/Dashboard'
import { MemoryVault } from './features/memory/MemoryVault'
import { MediaGallery } from './features/media/MediaGallery'
import { StoryStudio } from './features/story/StoryStudio'
import { VoiceStudio } from './features/story/VoiceStudio'
import { LifeGraph } from './features/graph/LifeGraph'
import { FamilyCircle } from './features/family/FamilyCircle'
import { LegacyBook } from './features/book/LegacyBook'
import { DigitalLegacy } from './features/legacy/DigitalLegacy'
import { getToken } from './services/api'

function Protected({ children }: { children: React.ReactNode }) {
  return getToken() ? <Layout>{children}</Layout> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <ToastProvider>
      <LightboxProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Auth />} />
          <Route path="/" element={<Protected><Dashboard /></Protected>} />
          <Route path="/memories" element={<Protected><MemoryVault /></Protected>} />
          <Route path="/media" element={<Protected><MediaGallery /></Protected>} />
          <Route path="/story" element={<Protected><StoryStudio /></Protected>} />
          <Route path="/voice" element={<Protected><VoiceStudio /></Protected>} />
          <Route path="/graph" element={<Protected><LifeGraph /></Protected>} />
          <Route path="/family" element={<Protected><FamilyCircle /></Protected>} />
          <Route path="/book" element={<Protected><LegacyBook /></Protected>} />
          <Route path="/legacy" element={<Protected><DigitalLegacy /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      </LightboxProvider>
    </ToastProvider>
  )
}
