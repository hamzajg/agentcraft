import React, { useState, useEffect } from 'react';
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import { WorkspaceTab, RAGTab, MonitorTab, EventsTab } from './tabs';

/* ─────────────────────────────────────────────────────────
   Global Layout Component
   Features:
   • Tab-based navigation system
   • Route-based content loading
   • Persistent layout structure
   • Responsive design
   ───────────────────────────────────────────────────────── */

const TABS = [
  { id: 'workspace', label: 'Workspace', icon: '📁' },
  { id: 'rag', label: 'RAG', icon: '🔍' },
  { id: 'monitor', label: 'Monitor', icon: '📊' },
  { id: 'events', label: 'Events', icon: '📡' }
];

export function GlobalLayout() {
  const [activeTab, setActiveTab] = useState('workspace');
  const location = useLocation();
  const navigate = useNavigate();

  // Sync active tab with current route
  useEffect(() => {
    const currentPath = location.pathname;
    const tabFromPath = currentPath.split('/')[1] || 'workspace';
    if (TABS.find(tab => tab.id === tabFromPath)) {
      setActiveTab(tabFromPath);
    }
  }, [location.pathname]);

  const handleTabClick = (tabId) => {
    setActiveTab(tabId);
    navigate(`/${tabId === 'workspace' ? '' : tabId}`);
  };

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg-primary)' }}>
      {/* Tab Navigation */}
      <header className="border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-secondary)' }}>
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>AgentCraft</h1>
          </div>
          
          <nav className="flex items-center gap-1">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab.id)}
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                  flex items-center gap-2
                  ${activeTab === tab.id 
                    ? 'bg-blue-500 text-white' 
                    : 'hover:bg-gray-100 text-gray-600'
                  }
                `}
                style={{
                  background: activeTab === tab.id 
                    ? 'var(--accent-primary)' 
                    : 'transparent',
                  color: activeTab === tab.id 
                    ? 'var(--bg-primary)' 
                    : 'var(--text-secondary)',
                  border: activeTab === tab.id 
                    ? 'none' 
                    : '1px solid var(--border-subtle)'
                }}
              >
                <span className="text-base">{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Content Area */}
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<WorkspaceTab />} />
          <Route path="/workspace" element={<WorkspaceTab />} />
          <Route path="/rag" element={<RAGTab />} />
          <Route path="/monitor" element={<MonitorTab />} />
          <Route path="/events" element={<EventsTab />} />
        </Routes>
      </main>
    </div>
  );
}
