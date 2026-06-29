import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Belief } from './types';

interface Props {
  sessions: string[];
  onNavigate: (tab: string, query?: string) => void;
  onClose: () => void;
}

export function GlobalSearch({ sessions, onNavigate, onClose }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<{ session: string; belief: Belief }[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    const t = setTimeout(async () => {
      setLoading(true);
      const all: { session: string; belief: Belief }[] = [];
      for (const s of sessions.slice(0, 5)) {
        try {
          const res = await fetch(`/api/sessions/${s}/beliefs?limit=200`);
          const data = await res.json();
          for (const b of (data.beliefs || [])) {
            const q = query.toLowerCase();
            if (b.subject.toLowerCase().includes(q) || b.predicate.toLowerCase().includes(q) || b.value.toLowerCase().includes(q)) {
              all.push({ session: s, belief: b });
            }
          }
        } catch {}
      }
      setResults(all.slice(0, 30));
      setLoading(false);
    }, 300);
    return () => clearTimeout(t);
  }, [query, sessions]);

  const handleSelect = useCallback((tab: string, q?: string) => {
    onNavigate(tab, q);
    onClose();
  }, [onNavigate, onClose]);

  return (
    <div className="global-search-overlay" onClick={onClose}>
      <div className="global-search-modal" onClick={e => e.stopPropagation()}>
        <div className="global-search-input-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input ref={inputRef} type="text" placeholder="Search beliefs across all sessions..." value={query} onChange={e => setQuery(e.target.value)} />
          <button className="btn-ghost btn-xs" onClick={onClose}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
        </div>
        {loading && <div className="global-search-status">Searching...</div>}
        {!loading && query && results.length === 0 && <div className="global-search-status text-muted">No results for "{query}"</div>}
        {results.length > 0 && (
          <div className="global-search-results">
            {results.map((r, i) => (
              <button key={i} className="global-search-item" onClick={() => handleSelect('beliefs', query)}>
                <div className="global-search-session">{r.session.slice(0, 16)}</div>
                <div className="global-search-subject">{r.belief.subject}</div>
                <div className="global-search-predicate">{r.belief.predicate}</div>
                <div className="global-search-value">{r.belief.value}</div>
                <span className="badge badge-assertion">{(r.belief.confidence * 100).toFixed(0)}%</span>
              </button>
            ))}
          </div>
        )}
        <div className="global-search-footer">
          <span>Press <kbd>Esc</kbd> to close</span>
          <span>Search across {sessions.length} sessions</span>
        </div>
      </div>
    </div>
  );
}
