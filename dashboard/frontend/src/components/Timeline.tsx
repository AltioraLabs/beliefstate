import React, { useEffect, useState } from 'react';
import { Belief } from './types';
import { Select } from './Select';

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
