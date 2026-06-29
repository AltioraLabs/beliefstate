import React, { useState } from 'react';

interface Props { sessionId: string; }

export function Simulator({ sessionId }: Props) {
  const [message, setMessage] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [activeView, setActiveView] = useState<'prompt'|'extracted'|'timing'>('prompt');

  const runSim = async () => {
    if (!message.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/sessions/${sessionId}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      setResult(await res.json());
      setActiveView('prompt');
    } catch {}
    setLoading(false);
  };

  const copy = (text: string) => navigator.clipboard.writeText(text);

  const RenderBelief = ({ b }: { b: any }) => (
    <div className={`extracted-card ${b.is_hypothetical ? 'extracted-hypo' : ''}`}>
      <div className="extracted-head">
        <span className="font-mono font-bold">{b.subject} {b.predicate}</span>
        <div className="extracted-tags">
          <span className={`badge badge-${b.belief_type}`}>{b.belief_type}</span>
          {b.is_hypothetical && <span className="badge badge-hypothetical">hypo</span>}
          <span className="badge badge-source badge-{b.source}">{b.source}</span>
        </div>
      </div>
      <div className="extracted-value font-mono">{b.value}</div>
      <div className="extracted-foot">
        <span className="confidence-dot" style={{ background: b.confidence >= 0.85 ? '#3fb950' : b.confidence >= 0.6 ? '#d29922' : '#f85149' }} />
        <span className="text-xs text-muted">{(b.confidence * 100).toFixed(0)}%</span>
        {b.source_quote && <span className="text-xs text-muted italic">"{b.source_quote}"</span>}
      </div>
    </div>
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Context Simulator</h1>
        <p className="page-subtitle">Test how a message would be processed</p>
      </div>

      <div className="glass-card">
        <div className="sim-input-group">
          <textarea
            value={message} onChange={e => setMessage(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), runSim())}
            placeholder="Enter a user message to simulate..."
            rows={3} className="sim-input"
          />
          <button className="btn btn-primary sim-btn" onClick={runSim} disabled={loading || !message.trim()}>
            {loading ? (
              <><span className="spinner" /> Processing...</>
            ) : (
              <><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> Simulate</>
            )}
          </button>
        </div>
      </div>

      {result && (
        <div className="grid-2col">
          <div className="glass-card col-span-2">
            <div className="sim-tabs">
              <button className={`sim-tab ${activeView === 'prompt' ? 'active' : ''}`} onClick={() => setActiveView('prompt')}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><polyline points="4 17 9 12 4 7"/><polyline points="12 19 20 19 20 5 12 5"/></svg>
                Injected Prompt
                {result.would_inject && <span className="badge badge-assertion ml-auto">{(result.token_estimate || 0)} tokens</span>}
              </button>
              <button className={`sim-tab ${activeView === 'extracted' ? 'active' : ''}`} onClick={() => setActiveView('extracted')}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                Extracted Beliefs
                <span className="badge badge-assertion ml-auto">{result.extracted_beliefs?.length || 0}</span>
              </button>
              <button className={`sim-tab ${activeView === 'timing' ? 'active' : ''}`} onClick={() => setActiveView('timing')}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                Performance
              </button>
            </div>

            <div className="sim-output">
              {activeView === 'prompt' && (
                <div className="sim-code-block">
                  <div className="sim-code-head">
                    <span>{result.would_inject ? '✓ Would inject' : '✗ Would NOT inject'}</span>
                    <button className="btn-ghost btn-xs" onClick={() => copy(result.context_prompt)}>Copy</button>
                  </div>
                  <pre className="sim-code">{result.context_prompt || '<empty — no matching beliefs>'}</pre>
                </div>
              )}

              {activeView === 'extracted' && (
                <div className="sim-extracted-list">
                  {(!result.extracted_beliefs || result.extracted_beliefs.length === 0) ? (
                    <div className="empty-small">No beliefs extracted</div>
                  ) : (
                    result.extracted_beliefs.map((b: any, i: number) => <RenderBelief key={i} b={b} />)
                  )}
                  {result.raw_llm && (
                    <details className="raw-llm">
                      <summary>Raw LLM output</summary>
                      <pre className="raw-llm-pre">{result.raw_llm}</pre>
                    </details>
                  )}
                </div>
              )}

              {activeView === 'timing' && (
                <div className="timing-grid">
                  {[
                    {label:'Context Injection', ms:result.timing_ms?.context || 0, pct: result.timing_ms?.total ? ((result.timing_ms.context / result.timing_ms.total) * 100).toFixed(1) : 0},
                    {label:'Belief Extraction', ms:result.timing_ms?.extraction || 0, pct: result.timing_ms?.total ? ((result.timing_ms.extraction / result.timing_ms.total) * 100).toFixed(1) : 0},
                    {label:'Total', ms:result.timing_ms?.total || 0, pct: 100, isTotal: true},
                  ].map((item, i) => (
                    <div key={i} className={`timing-row ${item.isTotal ? 'timing-total' : ''}`}>
                      <span className="timing-label">{item.label}</span>
                      <div className="timing-bar-track">
                        <div className="timing-bar-fill" style={{width:`${item.pct}%`}} />
                      </div>
                      <span className="timing-ms">{item.ms}ms</span>
                    </div>
                  ))}
                  <div className="timing-extra mt-3">
                    <span>Store has <strong>{result.total_beliefs_in_store}</strong> beliefs</span>
                    <span>Estimated <strong>{result.token_estimate}</strong> prompt tokens</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
