import React, { useEffect, useState } from 'react';
import { Belief } from './types';

interface Props { sessionId: string; }

export function Timeline({ sessionId }: Props) {
  const [beliefs, setBeliefs] = useState<Belief[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string>('');
  const [selectedPredicate, setSelectedPredicate] = useState<string>('');
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/beliefs?include_hypothetical=true&limit=1000`);
        const data = await res.json();
        setBeliefs(data.beliefs || []);
      } catch {}
      setLoading(false);
    })();
  }, [sessionId]);

  useEffect(() => {
    if (!selectedSubject || !selectedPredicate) return;
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/timeline/${encodeURIComponent(selectedSubject)}/${encodeURIComponent(selectedPredicate)}`);
        const data = await res.json();
        setHistory(data.history || []);
      } catch {}
    })();
  }, [sessionId, selectedSubject, selectedPredicate]);

  const pairs = [...new Map(beliefs.map(b => [`${b.subject}|${b.predicate}`, {subject: b.subject, predicate: b.predicate}])).values()]
    .sort((a, b) => a.subject.localeCompare(b.subject) || a.predicate.localeCompare(b.predicate));

  if (loading) return <div className="page"><div className="skeleton-card" style={{height:200}}/></div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Belief Timeline</h1>
        <p className="page-subtitle">Track how a specific belief evolved across turns</p>
      </div>

      <div className="timeline-selector">
        <select value={selectedSubject ? `${selectedSubject}|${selectedPredicate}` : ''} onChange={e => {
          const [s, p] = e.target.value.split('|');
          setSelectedSubject(s); setSelectedPredicate(p);
        }} className="filter-select" style={{maxWidth:400}}>
          <option value="">Select a belief to inspect...</option>
          {pairs.map(({subject, predicate}) => (
            <option key={`${subject}|${predicate}`} value={`${subject}|${predicate}`}>{subject} → {predicate}</option>
          ))}
        </select>
      </div>

      {history.length > 0 && (
        <div className="timeline-view">
          <div className="timeline-header">
            <span className="font-mono font-bold">{selectedSubject}</span>
            <span className="text-muted">{selectedPredicate}</span>
            <span className="badge badge-assertion">{history.length} changes</span>
          </div>
          <div className="timeline-list">
            {history.map((entry, i) => (
              <div key={i} className="timeline-entry">
                <div className="timeline-dot" />
                <div className="timeline-line" />
                <div className="timeline-card">
                  <div className="timeline-card-head">
                    <span className="badge badge-update">turn {entry.turn ?? entry.new_turn ?? '?'}</span>
                    <span className="text-xs text-muted">{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : ''}</span>
                  </div>
                  <div className="timeline-card-body">
                    <div className="timeline-old">
                      <span className="text-xs text-muted">Old value:</span>
                      <span className="font-mono text-sm" style={{color:'#f85149'}}>{entry.old_value || entry.existing_value || '(empty)'}</span>
                    </div>
                    <div className="timeline-arrow">→</div>
                    <div className="timeline-new">
                      <span className="text-xs text-muted">New value:</span>
                      <span className="font-mono text-sm" style={{color:'#3fb950'}}>{entry.new_value || entry.value || '(empty)'}</span>
                    </div>
                  </div>
                  {entry.reason && <div className="timeline-reason text-xs text-muted">{entry.reason}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedSubject && history.length === 0 && (
        <div className="empty-small mt-4">No history available for this belief</div>
      )}
    </div>
  );
}
