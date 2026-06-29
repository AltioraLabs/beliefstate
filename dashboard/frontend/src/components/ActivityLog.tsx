import React, { useEffect, useState } from 'react';
import { ActivityEntry } from './types';

interface Props { sessionId: string; }

const activityIcons: Record<string, string> = {
  tracking_event: '#58a6ff', belief_created: '#3fb950', belief_deleted: '#f85149',
  simulation: '#a371f7', config_updated: '#d29922',
};

export function ActivityLog({ sessionId }: Props) {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/activity?limit=200`);
        const data = await res.json();
        setEntries(data.activity || []);
      } catch {}
      setLoading(false);
    })();
  }, [sessionId]);

  const filtered = filter ? entries.filter(e => e.type.includes(filter)) : entries;

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Activity Log</h1>
        <p className="page-subtitle">Real-time stream of tracking events</p>
      </div>

      <div className="filter-bar">
        <select value={filter} onChange={e => setFilter(e.target.value)} className="filter-select">
          <option value="">All events</option>
          <option value="tracking_event">Tracking</option>
          <option value="belief_created">Created</option>
          <option value="belief_deleted">Deleted</option>
          <option value="simulation">Simulation</option>
          <option value="config_updated">Config</option>
        </select>
      </div>

      <div className="glass-card">
        {loading ? (
          <div className="empty-small">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="empty-small">No activity yet</div>
        ) : (
          <div className="activity-list">
            {filtered.map((entry, i) => (
              <div key={i} className="activity-entry">
                <div className="activity-dot" style={{ background: activityIcons[entry.type] || '#6e7681' }} />
                <div className="activity-content">
                  <div className="activity-head">
                    <span className="activity-type">{entry.type}</span>
                    <span className="activity-time">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="activity-data font-mono text-xs text-muted">
                    {JSON.stringify(entry.data).length > 200
                      ? JSON.stringify(entry.data).slice(0, 200) + '…'
                      : JSON.stringify(entry.data)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
