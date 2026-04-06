import { useState, useEffect } from 'react'
import { Gauge }     from '../components/Gauge'
import { AgentRow }  from '../components/AgentRow'
import { MiniChart } from '../components/MiniChart'
import { useMetrics } from '../hooks/useMetrics'
import { api }        from '../lib/api'

export function MonitorPage() {
  const { latest, history, error } = useMetrics()
  const [channels,      setChannels]      = useState([])
  const [statuses,      setStatuses]      = useState({})
  const [pendingAgents, setPendingAgents] = useState([])
  const [hwProfile,     setHwProfile]     = useState(null)

  // Load channels + hardware profile once
  useEffect(() => {
    api.channels().then(setChannels).catch(() => {})
    fetch('/api/hardware').then(r => r.json()).then(setHwProfile).catch(() => {})
  }, [])

  // Poll stats for pending agents
  useEffect(() => {
    const t = setInterval(() => {
      api.stats()
        .then(s => setPendingAgents(s.pending_agents ?? []))
        .catch(() => {})
    }, 3000)
    return () => clearInterval(t)
  }, [])

  const cpu_hist  = history.map(m => m.cpu_pct)
  const ram_hist  = history.map(m => m.ram_pct)
  const gpu_hist  = history.map(m => m.gpus?.[0]?.utilization ?? 0)
  const vram_hist = history.map(m => m.gpus?.[0]?.vram_pct ?? 0)

  const gpu   = latest?.gpus?.[0]
  const hasGpu = !!gpu

  return (
    <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6 animate-fade-in">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-200">System Monitor</h2>
          <p className="text-xs text-muted mt-0.5">
            {error
              ? <span className="text-amber">{error}</span>
              : latest
                ? <span className="text-teal">● live · updating every 2s</span>
                : <span className="text-muted">Connecting…</span>
            }
          </p>
        </div>

        {/* Hardware tier badge */}
        {hwProfile?.hardware?.tier && (
          <div className="bg-accent-dim border border-accent/30 rounded-lg px-3 py-1.5 text-right">
            <p className="text-[10px] text-muted uppercase tracking-wider">Hardware tier</p>
            <p className="text-xs font-mono text-accent font-medium capitalize">
              {hwProfile.hardware.tier}
            </p>
          </div>
        )}
      </div>

      {/* Gauges grid */}
      <div className={`grid gap-3 ${hasGpu ? 'grid-cols-2 lg:grid-cols-4' : 'grid-cols-2'}`}>
        <Gauge
          label="CPU"
          pct={latest?.cpu_pct ?? 0}
          detail={`${latest?.cpu_cores ?? '–'} cores`}
          color="teal"
        />
        <Gauge
          label="RAM"
          pct={latest?.ram_pct ?? 0}
          detail={latest ? `${latest.ram_used_gb.toFixed(1)} / ${latest.ram_total_gb.toFixed(0)} GB` : '–'}
          color="teal"
        />
        {hasGpu && (
          <Gauge
            label="GPU"
            pct={gpu.utilization}
            detail={gpu.name.split(' ').slice(0, 3).join(' ')}
            color="purple"
          />
        )}
        {hasGpu && (
          <Gauge
            label="VRAM"
            pct={gpu.vram_pct}
            detail={`${gpu.vram_used_gb.toFixed(1)} / ${gpu.vram_total_gb.toFixed(0)} GB`}
            color="purple"
          />
        )}
      </div>

      {/* Sparklines */}
      <div className="bg-panel border border-border rounded-xl p-4 space-y-3">
        <p className="text-xs font-mono text-muted uppercase tracking-wider">
          History (last {history.length} samples)
        </p>
        <div className={`grid gap-4 ${hasGpu ? 'grid-cols-2' : 'grid-cols-1'}`}>
          <div>
            <p className="text-[10px] text-muted mb-1">CPU + RAM</p>
            <div className="relative">
              <MiniChart data={cpu_hist}  color="#10b981" height={44} />
              <div className="absolute inset-0 pointer-events-none">
                <MiniChart data={ram_hist} color="#7c6fcd" height={44} />
              </div>
            </div>
            <div className="flex gap-4 mt-1">
              <span className="text-[10px] text-teal flex items-center gap-1">
                <span className="w-2 h-0.5 bg-teal rounded inline-block" /> CPU
              </span>
              <span className="text-[10px] text-accent flex items-center gap-1">
                <span className="w-2 h-0.5 bg-accent rounded inline-block" /> RAM
              </span>
            </div>
          </div>
          {hasGpu && (
            <div>
              <p className="text-[10px] text-muted mb-1">GPU + VRAM</p>
              <div className="relative">
                <MiniChart data={gpu_hist}  color="#7c6fcd" height={44} />
                <div className="absolute inset-0 pointer-events-none">
                  <MiniChart data={vram_hist} color="#a855f7" height={44} />
                </div>
              </div>
              <div className="flex gap-4 mt-1">
                <span className="text-[10px] text-accent flex items-center gap-1">
                  <span className="w-2 h-0.5 bg-accent rounded inline-block" /> GPU
                </span>
                <span className="text-[10px] text-purple-400 flex items-center gap-1">
                  <span className="w-2 h-0.5 bg-purple-400 rounded inline-block" /> VRAM
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Ollama process */}
      {latest?.ollama_pid && (
        <div className="bg-panel border border-border rounded-xl px-4 py-3
                        flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-teal" />
            <span className="text-xs font-mono text-gray-300">Ollama</span>
          </div>
          <span className="text-[11px] text-muted font-mono">
            pid {latest.ollama_pid}
          </span>
          <span className="text-[11px] text-muted font-mono">
            cpu {latest.ollama_cpu.toFixed(1)}%
          </span>
          <span className="text-[11px] text-muted font-mono">
            ram {latest.ollama_ram_gb.toFixed(2)} GB
          </span>
        </div>
      )}

      {/* Hardware profile */}
      {hwProfile?.selected && (
        <div className="bg-panel border border-border rounded-xl p-4 space-y-2">
          <p className="text-xs font-mono text-muted uppercase tracking-wider">Model configuration</p>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(hwProfile.selected).map(([k, v]) => (
              typeof v === 'string' && (
                <div key={k} className="flex items-center gap-2">
                  <span className="text-[10px] text-muted w-28">{k.replace(/_/g, ' ')}</span>
                  <span className="font-mono text-[11px] text-gray-300">{v}</span>
                </div>
              )
            ))}
          </div>
        </div>
      )}

      {/* Agent statuses */}
      <div className="bg-panel border border-border rounded-xl p-4">
        <p className="text-xs font-mono text-muted uppercase tracking-wider mb-3">Agents</p>
        {channels.length === 0 ? (
          <p className="text-xs text-muted">No agents yet — start a build to see agents here.</p>
        ) : (
          <div className="space-y-0.5">
            {channels.map(ch => (
              <AgentRow
                key={ch.agent_id}
                channel={ch}
                statuses={statuses}
                pendingAgents={pendingAgents}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
