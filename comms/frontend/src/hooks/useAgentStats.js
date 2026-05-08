import { useMemo } from 'react'

export function useAgentStats(statuses, channels) {
  return useMemo(() => {
    const agentCount = channels?.length || 0
    const entries = Object.entries(statuses)
    
    const activeAgents = entries.filter(([, s]) => s === 'running').length
    const blockedAgents = entries.filter(([, s]) => s === 'blocked').length
    const idleAgents = agentCount - activeAgents - blockedAgents
    
    return {
      agentCount,
      activeAgents,
      blockedAgents,
      idleAgents,
    }
  }, [statuses, channels])
}

export function useAgentStatusBreakdown(statuses) {
  return useMemo(() => {
    const entries = Object.entries(statuses)
    const byStatus = {}
    
    entries.forEach(([agentId, status]) => {
      byStatus[status] = (byStatus[status] || 0) + 1
    })
    
    return byStatus
  }, [statuses])
}
