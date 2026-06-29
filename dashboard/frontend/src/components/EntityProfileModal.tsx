import React, { useEffect, useState } from 'react';
import { Belief } from './types';

interface Props {
  sessionId: string;
  subject: string;
  onClose: () => void;
}

export function EntityProfileModal({ sessionId, subject, onClose }: Props) {
  const [beliefs, setBeliefs] = useState<Belief[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/entity/${encodeURIComponent(subject)}`);
        const data = await res.json();
        setBeliefs(data.beliefs || []);
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, [sessionId, subject]);

  const turnRange = beliefs.length > 0
    ? { min: Math.min(...beliefs.map(b => b.turn)), max: Math.max(...beliefs.map(b => b.turn)) }
    : null;

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 className="modal-title">{subject}</h2>
            <span className="modal-badge">{beliefs.length} beliefs</span>
          </div>
          <button className="btn-icon modal-close" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div className="modal-body">
          {turnRange && (
            <div className="entity-meta">
              <span className="chip">Turns {turnRange.min}–{turnRange.max}</span>
              <span className="chip">Avg: {(beliefs.reduce((s, b) => s + b.confidence, 0) / beliefs.length * 100).toFixed(0)}%</span>
            </div>
          )}
          {loading ? (
            <div className="flex items-center justify-center p-8 text-muted">Loading...</div>
          ) : beliefs.length === 0 ? (
            <div className="empty-small">No beliefs found for this entity</div>
          ) : (
            <div className="entity-list">
              {beliefs.map((b, i) => (
                <div key={i} className="entity-belief-row" style={{
                  borderLeft: `3px solid ${b.confidence >= 0.85 ? '#3fb950' : b.confidence >= 0.6 ? '#d29922' : '#f85149'}`,
                }}>
                  <div className="entity-belief-head">
                    <span className="font-mono text-sm">{b.predicate}</span>
                    <span className={`badge badge-sm ${b.belief_type === 'update' ? 'badge-update' : 'badge-assertion'}`}>{b.belief_type}</span>
                    <span className="font-mono text-xs text-muted ml-auto">turn {b.turn}</span>
                  </div>
                  <div className="entity-belief-value font-mono">{b.value}</div>
                  <div className="entity-belief-foot">
                    <span className="confidence-dot" style={{ background: b.confidence >= 0.85 ? '#3fb950' : b.confidence >= 0.6 ? '#d29922' : '#f85149' }} />
                    <span className="text-xs text-muted">{(b.confidence * 100).toFixed(0)}%</span>
                    {b.source_quote && <span className="text-xs text-muted italic ml-3 truncate max-w-[300px]">"{b.source_quote}"</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
