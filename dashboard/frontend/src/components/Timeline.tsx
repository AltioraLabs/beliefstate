import React, { useEffect, useState } from 'react';
import { Belief } from './types';
import { Select } from './Select';

interface Props { sessionId: string; refreshSignal: number; }

export function Timeline({ sessionId, refreshSignal }: Props) {
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
  }, [sessionId, refreshSignal]);

  useEffect(() => {
    if (!selectedSubject || !selectedPredicate) return;
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/timeline/${encodeURIComponent(selectedSubject)}/${encodeURIComponent(selectedPredicate)}`);
        const data = await res.json();
        setHistory(data.history || []);
      } catch {}
    })();
  }, [sessionId, selectedSubject, selectedPredicate, refreshSignal]);

  const pairs = [...new Map(beliefs.map(b => [`${b.subject}|${b.predicate}`, {subject: b.subject, predicate: b.predicate}])).values()]
    .sort((a, b) => a.subject.localeCompare(b.subject) || a.predicate.localeCompare(b.predicate));

  if (loading) return <div className="page"><div className="skeleton-card" style={{height:200}}/></div>;

  return (
    <div className="page">
      <div className="timeline-selector">
        <Select value={selectedSubject ? `${selectedSubject}|${selectedPredicate}` : ''}
          onChange={v => { const [s, p] = v.split('|'); setSelectedSubject(s); setSelectedPredicate(p); }}
          options={[
            {value:'',label:'Select a belief to inspect...'},
            ...pairs.map(({subject, predicate}) => ({
              value: `${subject}|${predicate}`,
              label: `${subject} → ${predicate}`,
            })),
          ]}
          placeholder="Select a belief to inspect..."
          width={400}
        />
      </div>

      {history.length > 0 && (
        <div className="timeline-view">
          <div className="timeline-header">
            <div className="timeline-selector-breadcrumb">
              <span className="font-mono font-bold" style={{fontSize:13}}>{selectedSubject}</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14" style={{color:'var(--gray-400)'}}><polyline points="9 18 15 12 9 6"/></svg>
              <span style={{fontSize:13,color:'var(--gray-500)'}}>{selectedPredicate}</span>
            </div>
            <span className="badge badge-primary">{history.length} changes</span>
          </div>
          <div className="timeline-list">
            {history.map((entry, i) => (
              <div key={i} className="timeline-entry">
                <div className="timeline-dot" />
                <div className="timeline-line" />
                <div className="timeline-card">
                  <div className="timeline-card-head">
                    <span className="badge badge-neutral" style={{fontFamily:'var(--font-mono)',fontSize:11}}>turn {entry.turn ?? entry.new_turn ?? '?'}</span>
                    <span className="text-xs text-muted">{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : ''}</span>
                  </div>
                  <div className="timeline-card-body">
                    <div className="timeline-old">
                      <span className="timeline-value-label">Old value:</span>
                      <span className="timeline-old-value">{entry.old_value || entry.existing_value || '(empty)'}</span>
                    </div>
                    <div className="timeline-arrow">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20"><polyline points="9 18 15 12 9 6"/></svg>
                    </div>
                    <div className="timeline-new">
                      <span className="timeline-value-label">New value:</span>
                      <span className="timeline-new-value">{entry.new_value || entry.value || '(empty)'}</span>
                    </div>
                  </div>
                  {entry.reason && <div className="timeline-reason">{entry.reason}</div>}
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
