import React, { useEffect, useState } from 'react';
import { ActivityEntry } from './types';
import { Select } from './Select';

interface Props { sessionId: string; refreshSignal: number; }

const activityIcons: Record<string, string> = {
  tracking_event: '#58a6ff', belief_created: '#3fb950', belief_deleted: '#f85149',
  simulation: '#a371f7', config_updated: '#d29922',
};

function ActivityDetailModal({ entry, onClose }: { entry: ActivityEntry; onClose: () => void }) {
  const [copyLabel, setCopyLabel] = useState('Copy');
  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(entry, null, 2));
    setCopyLabel('Copied!');
    setTimeout(() => setCopyLabel('Copy'), 1500);
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 640 }}>
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 className="modal-title">{entry.type.replace(/_/g,' ')}</h2>
            <span className="modal-badge">{new Date(entry.timestamp).toLocaleString()}</span>
          </div>
          <button className="btn-icon modal-close" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div className="modal-body">
          <div className="detail-section">
            <span className="detail-label">Session</span>
            <span className="detail-value font-mono">{entry.session_id}</span>
          </div>
          <div className="detail-section">
            <span className="detail-label">Timestamp</span>
            <span className="detail-value">{new Date(entry.timestamp).toLocaleString()}</span>
          </div>
          {entry.data && Object.keys(entry.data).length > 0 && (
            <div className="detail-section" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 4 }}>
              <span className="detail-label">Data</span>
              <pre className="detail-json" style={{color:'var(--gray-600)',whiteSpace:'pre',tabSize:2}}>{JSON.stringify(entry.data, null, 2)}</pre>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary btn-sm" onClick={handleCopy}>{copyLabel}</button>
          <button className="btn btn-primary btn-sm" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

export function ActivityLog({ sessionId, refreshSignal }: Props) {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [selectedEntry, setSelectedEntry] = useState<ActivityEntry | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/activity?limit=200`);
        const data = await res.json();
        setEntries(data.activity || []);
      } catch {}
      setLoading(false);
    })();
  }, [sessionId, refreshSignal]);

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
              <div key={i} className={`activity-entry event-${entry.type}`} style={{ cursor: 'pointer' }} onClick={() => setSelectedEntry(entry)}>
                <div className="activity-dot" style={{ background: activityIcons[entry.type] || '#6e7681' }} />
                <div className="activity-content">
                  <div className="activity-head">
                    <span className="activity-type">{entry.type.replace(/_/g,' ')}</span>
                    <span className="activity-time">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <pre style={{fontFamily:'var(--font-mono)',fontSize:12.5,color:'var(--gray-400)',lineHeight:1.7,whiteSpace:'pre-wrap',wordBreak:'break-all',margin:0,background:'#fafafa',border:'1px solid var(--gray-100)',borderRadius:8,padding:'10px 12px',marginTop:6}}>
                    {JSON.stringify(entry.data, null, 2).length > 300
                      ? <><span>{JSON.stringify(entry.data, null, 2).slice(0, 300)}</span><br/><button className="btn-ghost btn-xs" style={{color:'var(--accent)',marginTop:4}} onClick={(e) => { e.stopPropagation(); setSelectedEntry(entry); }}>Show more</button></>
                      : JSON.stringify(entry.data, null, 2)}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedEntry && (
        <ActivityDetailModal entry={selectedEntry} onClose={() => setSelectedEntry(null)} />
      )}
    </div>
  );
}
