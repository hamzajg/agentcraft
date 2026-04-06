export function NoChannel() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 text-muted p-8">
      <div className="w-12 h-12 rounded-xl border border-border flex items-center justify-center">
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-sm">Select an agent to start</p>
    </div>
  )
}

export function NoMessages({ agentLabel }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-2 text-muted p-8">
      <p className="text-sm">No messages from <span className="font-mono text-gray-400">{agentLabel}</span> yet.</p>
      <p className="text-xs">Messages appear here when the agent needs your input.</p>
    </div>
  )
}
