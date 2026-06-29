import React, { useEffect, useState } from 'react';
import { CompareResult, Belief } from './types';
import { Select } from './Select';

interface Props { sessionId: string; sessions: string[]; }

export function SessionCompare({ sessionId: currentSession, sessions }: Props) {
  const [sessionA, setSessionA] = useState(currentSession);
  const [sessionB, setSessionB] = useState(sessions.find(s => s !== currentSession) || '');
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [diffView, setDiffView] = useState<'summary' | 'split' | 'unified'>('summary');

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

  const renderBeliefRow = (b: Belief, color: string, showBadge = true) => (
    <div className="diff-belief" style={{ borderLeft: `3px solid ${color}` }}>
      <div className="diff-belief-head"><span className="font-mono font-bold">{b.subject}</span><span className="text-muted text-xs">{b.predicate}</span></div>
      <div className="diff-belief-value">{b.value}</div>
      {showBadge && <span className="badge badge-assertion">{(b.confidence*100).toFixed(0)}%</span>}
    </div>
  );

  return (
    <div className="page">
      <div className="compare-picker">
        <Select value={sessionA} onChange={setSessionA} options={sessions.map(s => ({value:s, label:s.slice(0,20)+'…'}))} />
        <span className="compare-vs">vs</span>
        <Select value={sessionB} onChange={setSessionB} options={sessions.filter(s => s !== sessionA).map(s => ({value:s, label:s.slice(0,20)+'…'}))} />
        <button className="btn btn-primary" onClick={runCompare} disabled={loading || sessionA === sessionB || !sessionB}>
          {loading ? 'Comparing...' : 'Compare'}
        </button>
        <div className="diff-view-toggle">
          <button className={`btn btn-sm ${diffView === 'summary' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setDiffView('summary')}>Summary</button>
          <button className={`btn btn-sm ${diffView === 'split' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setDiffView('split')}>Split</button>
          <button className={`btn btn-sm ${diffView === 'unified' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setDiffView('unified')}>Unified</button>
        </div>
      </div>

      {result && diffView === 'summary' && (
        <>
          <div className="compare-summary">
            <div className="compare-stat"><span className="stat-value" style={{color:'#2563eb'}}>{result.summary.total_a}</span><span className="stat-label">{sessionA.slice(0,12)}</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#8b5cf6'}}>{result.summary.total_b}</span><span className="stat-label">{sessionB.slice(0,12)}</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#22c55e'}}>{result.summary.same}</span><span className="stat-label">Shared</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#f59e0b'}}>{result.summary.changed}</span><span className="stat-label">Changed</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#ef4444'}}>{result.summary.only_in_a}</span><span className="stat-label">Only A</span></div>
            <div className="compare-stat"><span className="stat-value" style={{color:'#ef4444'}}>{result.summary.only_in_b}</span><span className="stat-label">Only B</span></div>
          </div>
          <div className="grid-2col">
            {result.changed.length > 0 && (
              <div className="card col-span-2">
                <div className="card-header"><h3>Changed Beliefs</h3><span className="card-badge">{result.changed.length}</span></div>
                <div className="card-body">
                  {result.changed.map((c, i) => (
                    <div key={i} className="changed-row">
                      <div className="changed-head"><span className="font-mono font-bold">{c.subject}</span><span className="text-muted text-xs">{c.predicate}</span></div>
                      <div className="changed-compare">
                        <div className="changed-old"><span className="text-xs text-muted">Old:</span><span className="font-mono text-sm" style={{color:'#ef4444'}}>{c.old.value}</span></div>
                        <div className="changed-arrow">→</div>
                        <div className="changed-new"><span className="text-xs text-muted">New:</span><span className="font-mono text-sm" style={{color:'#22c55e'}}>{c.new.value}</span></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="card"><div className="card-header"><h3>Only in {sessionA.slice(0,12)}</h3><span className="card-badge">{result.summary.only_in_a}</span></div><div className="card-body">{result.only_in_a.length === 0 ? <div className="empty-small">None</div> : result.only_in_a.map((b, i) => <React.Fragment key={i}>{renderBeliefRow(b, '#2563eb')}</React.Fragment>)}</div></div>
            <div className="card"><div className="card-header"><h3>Only in {sessionB.slice(0,12)}</h3><span className="card-badge">{result.summary.only_in_b}</span></div><div className="card-body">{result.only_in_b.length === 0 ? <div className="empty-small">None</div> : result.only_in_b.map((b, i) => <React.Fragment key={i}>{renderBeliefRow(b, '#8b5cf6')}</React.Fragment>)}</div></div>
          </div>
        </>
      )}

      {result && diffView === 'split' && (
        <div className="diff-split">
          <div className="diff-pane">
            <div className="diff-pane-head">{sessionA.slice(0,20)}</div>
            <div className="diff-pane-body">
              {result.only_in_a.map((b, i) => <React.Fragment key={i}>{renderBeliefRow(b, '#ef4444')}</React.Fragment>)}
              {result.changed.map((c, i) => <React.Fragment key={i}>{renderBeliefRow(c.old, '#f59e0b')}</React.Fragment>)}
              {result.same.map((b, i) => <React.Fragment key={i}>{renderBeliefRow(b, '#22c55e')}</React.Fragment>)}
            </div>
          </div>
          <div className="diff-divider" />
          <div className="diff-pane">
            <div className="diff-pane-head">{sessionB.slice(0,20)}</div>
            <div className="diff-pane-body">
              {result.only_in_b.map((b, i) => <React.Fragment key={i}>{renderBeliefRow(b, '#ef4444')}</React.Fragment>)}
              {result.changed.map((c, i) => <React.Fragment key={i}>{renderBeliefRow(c.new, '#22c55e')}</React.Fragment>)}
              {result.same.map((b, i) => <React.Fragment key={i}>{renderBeliefRow(b, '#22c55e')}</React.Fragment>)}
            </div>
          </div>
        </div>
      )}

      {result && diffView === 'unified' && (
        <div className="diff-unified">
          <div className="diff-unified-head">
            <span>{sessionA.slice(0,16)} ← → {sessionB.slice(0,16)}</span>
            <span className="badge badge-assertion">{result.summary.total_a + result.summary.total_b} beliefs</span>
          </div>
          <div className="diff-unified-body">
            {result.changed.map((c, i) => (
              <div key={i} className="diff-hunk">
                <div className="diff-hunk-head">{c.subject} {c.predicate}</div>
                <div className="diff-hunk-old">- {c.old.value}</div>
                <div className="diff-hunk-new">+ {c.new.value}</div>
              </div>
            ))}
            {result.only_in_a.map((b, i) => (
              <div key={`a-${i}`} className="diff-hunk">
                <div className="diff-hunk-head">{b.subject} {b.predicate}</div>
                <div className="diff-hunk-old">- {b.value}</div>
              </div>
            ))}
            {result.only_in_b.map((b, i) => (
              <div key={`b-${i}`} className="diff-hunk">
                <div className="diff-hunk-head">{b.subject} {b.predicate}</div>
                <div className="diff-hunk-new">+ {b.value}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
