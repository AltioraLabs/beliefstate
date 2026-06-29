import React, { useEffect, useState } from 'react';
import { Belief } from './types';
import { EntityProfileModal } from './EntityProfileModal';

interface Props { sessionId: string; onRefresh: () => void; }

export function BeliefsTable({ sessionId, onRefresh }: Props) {
  const [beliefs, setBeliefs] = useState<Belief[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [sortKey, setSortKey] = useState<keyof Belief>('turn');
  const [sortDir, setSortDir] = useState<'asc'|'desc'>('desc');
  const [showHypothetical, setShowHypothetical] = useState(false);
  const [minConfidence, setMinConfidence] = useState(0);
  const [entitySubject, setEntitySubject] = useState<string | null>(null);

  const fetchBeliefs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        include_hypothetical: String(showHypothetical),
        min_confidence: String(minConfidence),
        limit: '1000',
      });
      const res = await fetch(`/api/sessions/${sessionId}/beliefs?${params}`);
      const data = await res.json();
      setBeliefs(data.beliefs || []);
    } catch { }
    setLoading(false);
  };

  useEffect(() => { fetchBeliefs(); }, [sessionId, showHypothetical, minConfidence]);

  const filtered = beliefs
    .filter(b => {
      if (search) {
        const s = search.toLowerCase();
        if (!b.subject.toLowerCase().includes(s) && !b.predicate.toLowerCase().includes(s) && !b.value.toLowerCase().includes(s)) return false;
      }
      if (categoryFilter !== 'all' && (b.category || 'general') !== categoryFilter) return false;
      if (sourceFilter !== 'all' && b.source !== sourceFilter) return false;
      if (typeFilter !== 'all' && b.belief_type !== typeFilter) return false;
      return true;
    })
    .sort((a, b) => {
      const aVal = a[sortKey]; const bVal = b[sortKey];
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });

  const handleSort = (key: keyof Belief) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const exportCSV = () => {
    const headers = ['subject','predicate','value','confidence','belief_type','category','source','turn','is_hypothetical','resolution_note'];
    const rows = filtered.map(b => [
      b.subject, b.predicate, b.value, b.confidence, b.belief_type,
      b.category || 'general', b.source, b.turn, b.is_hypothetical, b.resolution_note,
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${String(v).replace(/"/g,'""')}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `beliefs-${sessionId}.csv`; a.click();
    URL.revokeObjectURL(blob);
  };

  const categories = [...new Set(beliefs.map(b => b.category || 'general'))].sort();
  const sources = [...new Set(beliefs.map(b => b.source))].sort();
  const types = [...new Set(beliefs.map(b => b.belief_type))].sort();

  const SortIcon = ({ col }: { col: keyof Belief }) => (
    sortKey === col
      ? <span className="sort-arrow">{sortDir === 'asc' ? ' ▲' : ' ▼'}</span>
      : <span className="sort-arrow-muted"> ⇅</span>
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Beliefs Explorer</h1>
          <p className="page-subtitle">{filtered.length} of {beliefs.length} beliefs</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={exportCSV} disabled={filtered.length === 0}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Export CSV
          </button>
          <button className="btn btn-secondary" onClick={fetchBeliefs}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
            Refresh
          </button>
        </div>
      </div>

      <div className="filter-bar">
        <div className="search-input-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16" className="search-icon"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input type="text" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} className="search-input" />
        </div>
        <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} className="filter-select">
          <option value="all">Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)} className="filter-select">
          <option value="all">Sources</option>
          {sources.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className="filter-select">
          <option value="all">Types</option>
          {types.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <label className="toggle-label">
          <input type="checkbox" checked={showHypothetical} onChange={e => setShowHypothetical(e.target.checked)} />
          <span>Hypo</span>
        </label>
        <div className="range-slider">
          <span className="range-label">Min</span>
          <input type="range" min="0" max="1" step="0.05" value={minConfidence} onChange={e => setMinConfidence(Number(e.target.value))} />
          <span className="range-value">{(minConfidence * 100).toFixed(0)}%</span>
        </div>
      </div>

      <div className="glass-card table-wrap">
        {loading ? (
          <div className="empty-small">Loading...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('subject')}>Subject<SortIcon col="subject"/></th>
                <th onClick={() => handleSort('predicate')}>Predicate<SortIcon col="predicate"/></th>
                <th onClick={() => handleSort('value')}>Value<SortIcon col="value"/></th>
                <th onClick={() => handleSort('confidence')} style={{width:'150px'}}>Conf<SortIcon col="confidence"/></th>
                <th onClick={() => handleSort('belief_type')}>Type<SortIcon col="belief_type"/></th>
                <th onClick={() => handleSort('category')}>Cat<SortIcon col="category"/></th>
                <th onClick={() => handleSort('source')}>Src<SortIcon col="source"/></th>
                <th onClick={() => handleSort('turn')} style={{width:'65px'}}>Turn<SortIcon col="turn"/></th>
                <th style={{width:'70px'}}>Act</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={9} className="empty-cell">No beliefs match filters</td></tr>
              ) : filtered.map((b, i) => {
                const confClass = b.confidence >= 0.85 ? 'high' : b.confidence >= 0.6 ? 'medium' : 'low';
                return (
                  <tr key={`${b.subject}-${b.predicate}-${b.turn}-${i}`}>
                    <td><button className="entity-link" onClick={() => setEntitySubject(b.subject)}>{b.subject}</button></td>
                    <td className="text-muted">{b.predicate}</td>
                    <td className="mono-value" title={b.value}>{b.value.length > 60 ? b.value.slice(0,60)+'…' : b.value}</td>
                    <td>
                      <div className="conf-bar-wrap">
                        <div className={`conf-bar conf-${confClass}`} style={{width:`${b.confidence*100}%`}} />
                        <span className="conf-text">{(b.confidence*100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td><span className={`badge badge-${b.belief_type}`}>{b.belief_type}</span></td>
                    <td><span className="badge badge-category" data-cat={b.category || 'general'}>{b.category || 'gen'}</span></td>
                    <td><span className={`badge badge-source badge-${b.source}`}>{b.source}</span></td>
                    <td className="font-mono text-xs text-muted">{b.turn}</td>
                    <td>
                      <div className="action-btns">
                        <button className="btn-icon-sm" title="Edit" onClick={() => {
                          const newVal = prompt('Edit value:', b.value);
                          if (newVal && newVal !== b.value) {
                            fetch(`/api/sessions/${sessionId}/beliefs`, {
                              method:'POST', headers:{'Content-Type':'application/json'},
                              body: JSON.stringify({...b, value: newVal}),
                            }).then(() => { fetchBeliefs(); onRefresh(); });
                          }
                        }}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        </button>
                        <button className="btn-icon-sm text-danger" title="Delete" onClick={() => {
                          if (confirm(`Delete: ${b.subject} ${b.predicate}?`)) {
                            fetch(`/api/sessions/${sessionId}/beliefs/${encodeURIComponent(b.subject)}/${encodeURIComponent(b.predicate)}`, {method:'DELETE'})
                              .then(() => { fetchBeliefs(); onRefresh(); });
                          }
                        }}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {entitySubject && <EntityProfileModal sessionId={sessionId} subject={entitySubject} onClose={() => setEntitySubject(null)} />}
    </div>
  );
}
