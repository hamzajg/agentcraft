import { Link } from 'react-router-dom'
import '../styles/design-system.css'

export function LandingPage() {
  return (
    <div className="min-h-screen bg-primary relative overflow-hidden">
      {/* Background pattern */}
      <div 
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(100, 180, 255, 0.04) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
          maskImage: 'radial-gradient(ellipse at center, black 50%, transparent 100%)',
        }}
      />
      
      <div className="relative z-10 max-w-6xl mx-auto px-6 py-16 flex flex-col justify-center min-h-screen">
        {/* Hero */}
        <div className="text-center mb-16">
          <div 
            className="w-20 h-20 rounded-lg flex items-center justify-center mx-auto mb-8"
            style={{ background: 'var(--accent-primary)', color: 'var(--bg-primary)' }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2 4l4 4-4 4M8 12h6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          
          <h1 
            className="text-4xl md:text-5xl font-bold mb-4"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}
          >
            AgentCraft
          </h1>
          
          <p className="text-lg md:text-xl mb-8" style={{ color: 'var(--text-secondary)' }}>
            AI Agent Team Platform for Collaborative Development
          </p>
          
          <div className="flex gap-4 justify-center flex-wrap">
            <Link
              to="/workspace"
              className="inline-flex items-center gap-3 rounded font-semibold transition-all duration-200"
              style={{ 
                background: 'var(--accent-primary)', color: 'var(--bg-primary)',
                padding: '0.75rem 1.5rem', fontSize: '0.875rem', textDecoration: 'none', minHeight: '44px'
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Enter Workspace
            </Link>
            <Link
              to="/hermes"
              className="inline-flex items-center gap-3 rounded font-semibold transition-all duration-200"
              style={{ 
                background: 'transparent', color: 'var(--accent-primary)',
                border: '1px solid var(--accent-primary)', padding: '0.75rem 1.5rem',
                fontSize: '0.875rem', textDecoration: 'none', minHeight: '44px'
              }}
            >
              ⚡ Hermes Studio
            </Link>
          </div>
        </div>
        
        {/* Platform Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-16">
          {/* AgentCraft Column */}
          <div>
            <h2 
              className="text-xl font-bold mb-4 flex items-center gap-2"
              style={{ color: 'var(--text-primary)' }}
            >
              <span style={{ fontSize: '24px' }}>🤖</span> AgentCraft Workspace
            </h2>
            <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
              Multi-agent collaboration platform with specialized AI agents working together on complex development tasks.
            </p>
            <div className="space-y-2">
              {[
                '11 specialized agents (Architect, Backend Dev, Test Dev, etc.)',
                'Real-time agent communication and collaboration',
                'File explorer and code viewer',
                'Build control: pause, resume, approve iterations',
                'RAG-powered semantic code search',
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--accent-primary)' }}>✓</span>
                  {item}
                </div>
              ))}
            </div>
            <Link
              to="/workspace"
              className="inline-flex items-center gap-2 mt-4 text-sm font-medium"
              style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}
            >
              Open Workspace →
            </Link>
          </div>
          
          {/* Hermes Column */}
          <div>
            <h2 
              className="text-xl font-bold mb-4 flex items-center gap-2"
              style={{ color: 'var(--text-primary)' }}
            >
              <span style={{ fontSize: '24px' }}>⚡</span> Hermes Studio
            </h2>
            <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
              Agnostic AI Agent Factory & Runner. Build, run, and visualize AI agents with multi-LLM support.
            </p>
            <div className="space-y-2">
              {[
                'Multi-LLM: OpenAI, Anthropic, Gemini, Groq, Ollama',
                'Framework-agnostic: Raw API, LangChain, CrewAI, AutoGen',
                'Agent YAML definitions with prompt templating',
                'Sync, async, and streaming execution modes',
                'Real-time event streaming via SSE',
                'Pipeline orchestration (coming soon)',
                'Plugin marketplace (coming soon)',
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--accent-primary)' }}>✓</span>
                  {item}
                </div>
              ))}
            </div>
            <Link
              to="/hermes"
              className="inline-flex items-center gap-2 mt-4 text-sm font-medium"
              style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}
            >
              Open Hermes →
            </Link>
          </div>
        </div>
        
        {/* Hermes Features Grid */}
        <div className="mb-16">
          <h2 
            className="text-2xl font-bold text-center mb-8"
            style={{ color: 'var(--text-primary)' }}
          >
            Hermes — What You Can Do
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: '🏭',
                title: 'Agent Factory',
                desc: 'Define agents once in YAML, spawn N instances. Configure prompts, LLM providers, and skills declaratively.',
              },
              {
                icon: '🚀',
                title: 'Multi-Mode Runner',
                desc: 'Execute agents synchronously for quick tests, asynchronously for production, or stream tokens in real-time.',
              },
              {
                icon: '🔀',
                title: 'Multi-LLM Router',
                desc: 'Switch between OpenAI, Anthropic, Gemini, Groq, and Ollama. Automatic fallback chains on provider failure.',
              },
              {
                icon: '🔗',
                title: 'Framework Adapters',
                desc: 'Use Raw API for speed, LangChain for chains, or CrewAI for multi-agent crews — all under one interface.',
              },
              {
                icon: '📡',
                title: 'Event Streaming',
                desc: 'Server-Sent Events for real-time monitoring. Watch tokens flow, tool calls execute, and agents decide.',
              },
              {
                icon: '🧩',
                title: 'Skills & MCP',
                desc: 'Inject capabilities via skills. Connect to MCP servers for external tools like web search and databases.',
              },
            ].map((feature, i) => (
              <div
                key={i}
                className="rounded-lg p-6 transition-all duration-200 hover:-translate-y-0.5"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}
              >
                <div className="text-3xl mb-3">{feature.icon}</div>
                <h3 className="font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>{feature.title}</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
        
        {/* Architecture */}
        <div className="mb-16">
          <h2 
            className="text-2xl font-bold text-center mb-8"
            style={{ color: 'var(--text-primary)' }}
          >
            Architecture
          </h2>
          <div 
            className="rounded-lg p-6 font-mono text-sm overflow-x-auto"
            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}
          >
<pre style={{ margin: 0 }}>{`
┌─────────────────────────────────────────────────────────────┐
│                    AGENTCRAFT + HERMES                       │
├────────────────────────┬────────────────────────────────────┤
│                        │                                    │
│   AgentCraft           │   Hermes Studio                    │
│   ┌──────────────┐     │   ┌──────────────┐                │
│   │ 11 Agents    │     │   │ Agent Builder│                │
│   │ Orchestrator │     │   │ Run Monitor  │                │
│   │ EventStream  │     │   │ Node Graph   │                │
│   │ RAG          │     │   │ Event Log    │                │
│   └──────────────┘     │   └──────────────┘                │
│                        │                                    │
├────────────────────────┴────────────────────────────────────┤
│                    Shared Infrastructure                     │
│   ┌─────────────┐ ┌──────────────┐ ┌─────────────────────┐ │
│   │ Comms Server │ │ Hermes API   │ │ SQLite / PostgreSQL │ │
│   │ (port 7001)  │ │ /api/hermes  │ │ hermes.db           │ │
│   └─────────────┘ └──────────────┘ └─────────────────────┘ │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │                  LLM Providers                       │  │
│   │  OpenAI │ Anthropic │ Gemini │ Groq │ Ollama │ ...  │  │
│   └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
`}</pre>
          </div>
        </div>
        
        {/* Quick Start */}
        <div className="text-center mb-16">
          <h2 className="text-2xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>Quick Start</h2>
          <div 
            className="rounded-lg p-6 font-mono text-sm text-left max-w-2xl mx-auto"
            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}
          >
<pre style={{ margin: 0 }}>{`# Start the server
cd comms && uvicorn main:app --port 7001 --reload

# Start the frontend
cd comms/frontend && npm run dev

# Open in browser
open http://localhost:5173/hermes`}</pre>
          </div>
        </div>
        
        {/* Footer */}
        <div className="text-center text-xs" style={{ color: 'var(--text-tertiary)' }}>
          <p>&copy; 2024 AgentCraft + Hermes. Built for AI-powered collaborative development.</p>
        </div>
      </div>
    </div>
  )
}
