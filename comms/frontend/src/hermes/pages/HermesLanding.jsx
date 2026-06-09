import React from 'react'
import { Link } from 'react-router-dom'
import hermesLogo from '../assets/hermes_logo.png'
import '../styles/hermes-design-system.css'

export function HermesLanding() {
  // Coordinates for our cosmetic constellation of 11 agent nodes
  const agentNodes = [
    { name: 'Architect', x: 120, y: 100, role: 'spec' },
    { name: 'Coder', x: 280, y: 80, role: 'code' },
    { name: 'Tester', x: 380, y: 150, role: 'test' },
    { name: 'Reviewer', x: 350, y: 260, role: 'review' },
    { name: 'Git Manager', x: 250, y: 320, role: 'git' },
    { name: 'Terminal', x: 100, y: 280, role: 'exec' },
    { name: 'RAG Search', x: 60, y: 180, role: 'rag' },
    { name: 'Orchestrator', x: 220, y: 200, role: 'orchestration', isHub: true },
  ]

  // Connections between nodes to make it look like a network
  const connections = [
    { from: 7, to: 0 },
    { from: 7, to: 1 },
    { from: 7, to: 2 },
    { from: 7, to: 3 },
    { from: 7, to: 4 },
    { from: 7, to: 5 },
    { from: 7, to: 6 },
    { from: 0, to: 1 },
    { from: 1, to: 2 },
    { from: 2, to: 3 },
    { from: 3, to: 4 },
    { from: 4, to: 5 },
    { from: 5, to: 6 },
    { from: 6, to: 0 },
  ]

  return (
    <div className="min-h-screen bg-[#07090f] text-slate-100 relative overflow-hidden flex flex-col justify-between font-sans">
      {/* Background stardust particles (CSS radial gradients) */}
      <div 
        className="absolute inset-0 pointer-events-none opacity-40"
        style={{
          backgroundImage: `
            radial-gradient(circle at 20% 30%, rgba(255, 184, 48, 0.08) 1px, transparent 120px),
            radial-gradient(circle at 80% 70%, rgba(0, 212, 255, 0.08) 1px, transparent 150px),
            radial-gradient(circle, rgba(100, 180, 255, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: '100% 100%, 100% 100%, 40px 40px',
          maskImage: 'radial-gradient(ellipse at center, black 60%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse at center, black 60%, transparent 100%)',
        }}
      />

      {/* Header / Brand top bar */}
      <header className="relative z-10 max-w-7xl mx-auto w-full px-6 py-6 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <img src={hermesLogo} alt="Hermes Logo" className="w-9 h-9 object-contain rounded-md border border-amber-500/20 shadow-md shadow-amber-500/10" />
          <div>
            <span className="text-xl font-bold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-cyan-400 font-serif" style={{ fontFamily: 'var(--font-hermes)' }}>
              HERMES
            </span>
            <span className="text-[9px] uppercase tracking-[0.25em] text-slate-500 block">
              STUDIO
            </span>
          </div>
        </div>
        <Link 
          to="/hermes/workspace" 
          className="px-4 py-1.5 text-xs font-semibold rounded border border-amber-500/40 text-amber-400 hover:bg-amber-500/10 transition-all duration-200"
        >
          Launch Studio
        </Link>
      </header>

      {/* Main Hero & Constellation Section */}
      <main className="relative z-10 max-w-7xl mx-auto w-full px-6 py-12 flex-1 flex flex-col lg:flex-row items-center justify-center gap-12 lg:gap-16">
        
        {/* Left Column: Core Value Proposition */}
        <div className="flex-1 text-center lg:text-left space-y-6 max-w-xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            Next-Gen Autonomous Workspace
          </div>
          
          <h1 
            className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight tracking-tight text-white font-serif"
            style={{ fontFamily: 'var(--font-hermes)', textShadow: '0 0 20px rgba(255, 184, 48, 0.15)' }}
          >
            Swift as thought,<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 via-amber-200 to-cyan-400">
              precise as fate.
            </span>
          </h1>

          <p className="text-slate-400 text-base md:text-lg leading-relaxed">
            Welcome to Hermes Studio. Coordinate a divine fleet of 11 specialized AI developer agents communicating at lightning speed over a shared event bus, directed by a central coordinator.
          </p>

          <div className="pt-4 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
            <Link
              to="/hermes/workspace"
              className="px-8 py-3.5 rounded-lg font-bold text-slate-950 bg-amber-400 hover:bg-amber-300 transition-all duration-200 shadow-lg shadow-amber-500/15 hover:shadow-amber-500/30 flex items-center gap-2 group text-sm"
              style={{ animation: 'hermes-glow 3s infinite ease-in-out' }}
            >
              Enter Hermes Workspace
              <svg className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
              </svg>
            </Link>
            <a
              href="#features"
              className="px-6 py-3.5 rounded-lg font-semibold text-slate-300 hover:text-white bg-slate-900/50 hover:bg-slate-800/50 border border-slate-800 hover:border-slate-700 transition-all duration-200 text-sm"
            >
              Explore Features
            </a>
          </div>
        </div>

        {/* Right Column: Cosmetic Agent Constellation Preview */}
        <div className="flex-1 w-full max-w-lg aspect-square flex items-center justify-center relative">
          <div className="absolute inset-0 bg-gradient-to-tr from-amber-500/5 to-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
          
          <div className="w-full h-full border border-slate-800/40 rounded-3xl bg-[#090d16]/30 backdrop-blur-md p-6 relative overflow-hidden shadow-2xl shadow-black/50">
            {/* SVG Constellation */}
            <svg viewBox="0 0 440 380" className="w-full h-full relative z-10 select-none">
              <defs>
                <linearGradient id="edge-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="rgba(255, 184, 48, 0.4)" />
                  <stop offset="100%" stopColor="rgba(0, 212, 255, 0.4)" />
                </linearGradient>
              </defs>

              {/* Draw Connection Edges */}
              {connections.map((c, i) => {
                const fromNode = agentNodes[c.from]
                const toNode = agentNodes[c.to]
                return (
                  <line
                    key={i}
                    x1={fromNode.x}
                    y1={fromNode.y}
                    x2={toNode.x}
                    y2={toNode.y}
                    stroke="url(#edge-grad)"
                    strokeWidth={fromNode.isHub || toNode.isHub ? 1.5 : 0.8}
                    className="stream-line"
                    style={{
                      animationDuration: `${12 + (i % 3) * 6}s`,
                      strokeDashoffset: (i * 10)
                    }}
                  />
                )
              })}

              {/* Draw Nodes */}
              {agentNodes.map((n, i) => (
                <g key={i} className={n.isHub ? 'constellation-node' : ''}>
                  {/* Outer pulsing ring */}
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r={n.isHub ? 18 : 10}
                    fill={n.isHub ? 'rgba(255, 184, 48, 0.15)' : 'rgba(0, 212, 255, 0.1)'}
                    stroke={n.isHub ? '#FFB830' : '#00d4ff'}
                    strokeWidth={n.isHub ? 2 : 1}
                    className="transition-all duration-300"
                  />
                  {/* Central solid dot */}
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r={n.isHub ? 8 : 4}
                    fill={n.isHub ? '#FFB830' : '#00d4ff'}
                  />
                  {/* Text Label */}
                  <text
                    x={n.x}
                    y={n.y + (n.isHub ? 32 : 22)}
                    fill={n.isHub ? '#FFB830' : '#a8b8c8'}
                    fontSize={n.isHub ? '11px' : '9px'}
                    fontWeight={n.isHub ? 'bold' : 'normal'}
                    textAnchor="middle"
                    className="font-mono tracking-wide"
                  >
                    {n.name}
                  </text>
                </g>
              ))}
            </svg>
          </div>
        </div>
      </main>

      {/* Features Pillars Section */}
      <section id="features" className="relative z-10 max-w-7xl mx-auto w-full px-6 py-16 border-t border-slate-900 bg-[#090d16]/20">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Pillar 1 */}
          <div className="bg-[#0b111e]/40 border border-slate-800/60 rounded-xl p-6 hover:border-amber-500/30 hover:bg-[#0c1322]/60 transition-all duration-300 group">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-4 group-hover:scale-105 transition-transform">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="text-white font-bold text-base mb-2 font-serif" style={{ fontFamily: 'var(--font-hermes)' }}>
              ⚡ Instant Delegation
            </h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Hermes acts as your divine intermediary. Describe your software goals, and Hermes automatically translates and routes commands to our 11 specialized agent workers in milliseconds.
            </p>
          </div>

          {/* Pillar 2 */}
          <div className="bg-[#0b111e]/40 border border-slate-800/60 rounded-xl p-6 hover:border-cyan-500/30 hover:bg-[#0c1322]/60 transition-all duration-300 group">
            <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4 group-hover:scale-105 transition-transform">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h3 className="text-white font-bold text-base mb-2 font-serif" style={{ fontFamily: 'var(--font-hermes)' }}>
              🧠 Shared Intelligence
            </h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Every specialized agent has concurrent access to your project workspace files, RAG knowledge bases, and terminal output. No silos, only synchronized intelligence.
            </p>
          </div>

          {/* Pillar 3 */}
          <div className="bg-[#0b111e]/40 border border-slate-800/60 rounded-xl p-6 hover:border-amber-500/30 hover:bg-[#0c1322]/60 transition-all duration-300 group">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-4 group-hover:scale-105 transition-transform">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            </div>
            <h3 className="text-white font-bold text-base mb-2 font-serif" style={{ fontFamily: 'var(--font-hermes)' }}>
              👁 Full Observability
            </h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Observe status transitions, event streams, and agent discussions in real time. Pause, step-verify, or reply to clarification prompts to keep agents moving in the right direction.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 py-8 text-center text-xs text-slate-600 border-t border-slate-950 max-w-7xl mx-auto w-full px-6">
        <p>&copy; {new Date().getFullYear()} AgentCraft Hermes Studio. All rights reserved. Swift as thought, precise as fate.</p>
      </footer>
    </div>
  )
}
