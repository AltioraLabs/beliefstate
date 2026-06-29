import React, { useEffect, useState } from 'react';
import { ActivityEntry } from './types';
import { Select } from './Select';

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
      <div className="filter-bar">
        <Select value={filter} onChange={setFilter}
          options={[
            {value:'',label:'All events'},
            {value:'tracking_event',label:'Tracking'},
            {value:'belief_created',label:'Created'},
            {value:'belief_deleted',label:'Deleted'},
            {value:'simulation',label:'Simulation'},
            {value:'config_updated',label:'Config'},
          ]} />
      </div>

      <div className="card">
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
