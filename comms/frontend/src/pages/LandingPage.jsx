import { Link } from 'react-router-dom'
import '../styles/design-system.css'

export function LandingPage() {
  return (
    <div className="min-h-screen bg-primary relative overflow-hidden">
      {/* Background pattern - subtle grid */}
      <div 
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(100, 180, 255, 0.04) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
          maskImage: 'radial-gradient(ellipse at center, black 50%, transparent 100%)',
        }}
      />
      
      {/* Main content */}
      <div className="relative z-10 max-w-5xl mx-auto px-6 py-16 flex flex-col justify-center min-h-screen">
        {/* Hero Section */}
        <div className="text-center mb-16">
          {/* Logo */}
          <div 
            className="w-20 h-20 rounded-lg flex items-center justify-center mx-auto mb-8"
            style={{ 
              background: 'var(--accent-primary)',
              color: 'var(--bg-primary)'
            }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2 4l4 4-4 4M8 12h6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          
          {/* Title */}
          <h1 
            className="text-4xl md:text-5xl font-bold mb-4"
            style={{ 
              fontFamily: 'var(--font-display)',
              color: 'var(--text-primary)',
              letterSpacing: '-0.02em'
            }}
          >
            AgentCraft
          </h1>
          
          {/* Tagline */}
          <p 
            className="text-lg md:text-xl mb-8"
            style={{ color: 'var(--text-secondary)' }}
          >
            AI Agent Team Platform for Collaborative Development
          </p>
        </div>
        
        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {/* Feature 1 */}
          <div 
            className="rounded-lg p-6 transition-all duration-200 hover:-translate-y-0.5"
            style={{ 
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)'
            }}
          >
            <div 
              className="w-12 h-12 rounded-lg flex items-center justify-center mb-4"
              style={{ 
                background: 'var(--accent-primary)',
                color: 'var(--bg-primary)'
              }}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="9" r="2"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
            </div>
            <h3 
              className="text-lg font-semibold mb-2"
              style={{ color: 'var(--text-primary)' }}
            >
              Multi-Agent Collaboration
            </h3>
            <p 
              className="text-sm leading-relaxed"
              style={{ color: 'var(--text-secondary)' }}
            >
              Coordinate specialized AI agents working together on complex development tasks with real-time communication and collaboration.
            </p>
          </div>
          
          {/* Feature 2 */}
          <div 
            className="rounded-lg p-6 transition-all duration-200 hover:-translate-y-0.5"
            style={{ 
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)'
            }}
          >
            <div 
              className="w-12 h-12 rounded-lg flex items-center justify-center mb-4"
              style={{ 
                background: 'var(--accent-primary)',
                color: 'var(--bg-primary)'
              }}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                <line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
            </div>
            <h3 
              className="text-lg font-semibold mb-2"
              style={{ color: 'var(--text-primary)' }}
            >
              Workspace Management
            </h3>
            <p 
              className="text-sm leading-relaxed"
              style={{ color: 'var(--text-secondary)' }}
            >
              Three-column workspace layout with file explorer, code viewer, and agent communication panels for seamless development.
            </p>
          </div>
          
          {/* Feature 3 */}
          <div 
            className="rounded-lg p-6 transition-all duration-200 hover:-translate-y-0.5"
            style={{ 
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)'
            }}
          >
            <div 
              className="w-12 h-12 rounded-lg flex items-center justify-center mb-4"
              style={{ 
                background: 'var(--accent-primary)',
                color: 'var(--bg-primary)'
              }}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
            </div>
            <h3 
              className="text-lg font-semibold mb-2"
              style={{ color: 'var(--text-primary)' }}
            >
              Real-time Activity
            </h3>
            <p 
              className="text-sm leading-relaxed"
              style={{ color: 'var(--text-secondary)' }}
            >
              Monitor agent progress, build status, and system events through floating activity pane with live updates.
            </p>
          </div>
        </div>
        
        {/* CTA Button */}
        <div className="text-center">
          <Link
            to="/workspace"
            className="inline-flex items-center gap-3 rounded font-semibold transition-all duration-200"
            style={{ 
              background: 'var(--accent-primary)',
              color: 'var(--bg-primary)',
              padding: '0.75rem 1.5rem',
              fontSize: '0.875rem',
              letterSpacing: '0.02em',
              minHeight: '44px'
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Enter Workspace
          </Link>
        </div>
        
        {/* Footer */}
        <div 
          className="text-center mt-16 text-xs"
          style={{ color: 'var(--text-tertiary)' }}
        >
          <p>&copy; 2024 AgentCraft. Built for AI-powered collaborative development.</p>
        </div>
      </div>
    </div>
  )
}
