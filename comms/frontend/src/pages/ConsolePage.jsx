export function ConsolePage({ logs }) {
  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-panel">
      <div className="h-11 flex-shrink-0 border-b border-border bg-panel
                      flex items-center px-5">
        <span className="font-mono text-sm font-medium text-gray-200">
          Agent Logs
        </span>
      </div>

      <div className="flex-1 overflow-auto p-4 font-mono text-xs">
        {logs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            No logs yet. Start the bootstrap to see agent activity.
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="mb-1">
              <span className="text-gray-400">[{log.agent_id}]</span>{' '}
              <span className="text-gray-200">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}