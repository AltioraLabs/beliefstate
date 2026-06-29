import React, { useEffect, useState } from 'react';
import { CompareResult, Belief } from './types';

interface Props {
  sessionId: string;
  sessions: string[];
}

export function SessionCompare({ sessionId: currentSession, sessions }: Props) {
  const [sessionA, setSessionA] = useState(currentSession);
  const [sessionB, setSessionB] = useState(sessions.find(s => s !== currentSession) || '');
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { setSessionA(currentSession); }, [currentSession]);

  const runCompare = async () => {
    if (!sessionA || !sessionB || sessionA === sessionB) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/sessions/compare?session_a=${encodeURIComponent(sessionA)}&session_b=${encodeURIComponent(sessionB)}`);
      setResult(await res.json());
    } catch {}
    setLoading(false);
  };

  const badgeClass = (count: number, isGood: boolean) =>
    count === 0 ? 'badge badge-assertion' : isGood ? 'badge badge-update' : 'badge badge-contradiction';

  const renderBeliefs = (beliefs: Belief[], color: string) => (
    <div className="compare-beliefs">
      {beliefs.length === 0 ? (
        <div className="empty-small">None</div>
      ) : (
        beliefs.map((b, i) => (
          <div key={i} className="compare-belief" style={{ borderLeft: `3px solid ${color}` }}>
            <span className="font-mono text-sm">{b.subject}</span>
            <span className="text-muted text-xs">{b.predicate}</span>
            <span className="font-mono text-xs">{b.value}</span>
            <span className="badge badge-sm badge-assertion">{(b.confidence*100).toFixed(0)}%</span>
          </div>
        ))
      )}
    </div>
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Session Compare</h1>
        <p className="page-subtitle">Diff beliefs between two sessions</p>
      </div>

      <div className="compare-picker">
        <select value={sessionA} onChange={e => setSessionA(e.target.value)} className="filter-select">
          {sessions.map(s => <option key={s} value={s}>{s.slice(0,20)}…</option>)}
        </select>
        <span className="compare-vs">vs</span>
        <select value={sessionB} onChange={e => setSessionB(e.target.value)} className="filter-select">
          {sessions.filter(s => s !== sessionA).map(s => <option key={s} value={s}>{s.slice(0,20)}…</option>)}
        </select>
        <button className="btn btn-primary" onClick={runCompare} disabled={loading || sessionA === sessionB || !sessionB}>
          {loading ? 'Comparing...' : 'Compare'}
        </button>
      </div>

      {result && (
        <>
          <div className="compare-summary">
            <div className="compare-stat"><span className="stat-value" style={{color:'#58a6ff'}}>{result.summary.total_a}</span><span className="stat-label">{sessionA.slice(0,12)}</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#a371f7'}}>{result.summary.total_b}</span><span className="stat-label">{sessionB.slice(0,12)}</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#3fb950'}}>{result.summary.same}</span><span className="stat-label">Shared</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#d29922'}}>{result.summary.changed}</span><span className="stat-label">Changed</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#f85149'}}>{result.summary.only_in_a}</span><span className="stat-label">Only A</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#f85149'}}>{result.summary.only_in_b}</span><span className="stat-label">Only B</span></div>
          </div>

          <div className="grid-2col">
            {result.changed.length > 0 && (
              <div className="glass-card col-span-2">
                <div className="card-header"><h3>Changed Beliefs</h3><span className="card-badge">{result.changed.length}</span></div>
                <div className="card-body">
                  {result.changed.map((c, i) => (
                    <div key={i} className="changed-row">
                      <div className="changed-head"><span className="font-mono font-bold">{c.subject}</span><span className="text-muted text-xs">{c.predicate}</span></div>
                      <div className="changed-compare">
                        <div className="changed-old"><span className="text-xs text-muted">Old:</span><span className="font-mono text-sm" style={{color:'#f85149'}}>{c.old.value}</span></div>
                        <div className="changed-arrow">→</div>
                        <div className="changed-new"><span className="text-xs text-muted">New:</span><span className="font-mono text-sm" style={{color:'#3fb950'}}>{c.new.value}</span></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="glass-card">
              <div className="card-header"><h3>Only in {sessionA.slice(0,12)}</h3><span className="card-badge">{result.summary.only_in_a}</span></div>
              <div className="card-body">{renderBeliefs(result.only_in_a, '#58a6ff')}</div>
            </div>
            <div className="glass-card">
              <div className="card-header"><h3>Only in {sessionB.slice(0,12)}</h3><span className="card-badge">{result.summary.only_in_b}</span></div>
              <div className="card-body">{renderBeliefs(result.only_in_b, '#a371f7')}</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
