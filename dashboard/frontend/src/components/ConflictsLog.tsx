import React, { useEffect, useState } from 'react';
import { Select } from './Select';
import { ConflictHeatmap } from './ConflictHeatmap';

interface Props { sessionId: string; onRefresh: () => void; refreshSignal: number; }

export function ConflictsLog({ sessionId, onRefresh, refreshSignal }: Props) {
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [view, setView] = useState<'list' | 'heatmap'>('list');

  const fetchConflicts = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/sessions/${sessionId}/conflicts`);
      const data = await res.json();
      setConflicts(data.conflicts || []);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchConflicts(); }, [sessionId, refreshSignal]);

  const filtered = filter === 'all' ? conflicts : conflicts.filter(c => c.resolution === filter);
  const resColors: Record<string, string> = { overwrite: '#f59e0b', keep_old: '#22c55e', raise: '#ef4444', pending: '#6b7280' };
  const resLabels: Record<string, string> = { overwrite: 'Overwritten', keep_old: 'Kept Old', raise: 'Raised', pending: 'Pending' };
  const stats = { total: conflicts.length, ...Object.fromEntries(['overwrite','keep_old','raise','pending'].map(k => [k, conflicts.filter(c => c.resolution === k).length])) };

  return (
    <div className="page">
      <div className="page-actions">
        <button className="btn btn-secondary" onClick={fetchConflicts}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          Refresh
        </button>
        <div className="segmented-control">
          <button className={`seg-btn ${view === 'list' ? 'active' : ''}`} onClick={() => setView('list')}>List</button>
          <button className={`seg-btn ${view === 'heatmap' ? 'active' : ''}`} onClick={() => setView('heatmap')}>Heatmap</button>
        </div>
      </div>

      <div className="conflict-stats-bar">
        {Object.entries(stats).map(([key, val]) => (
          <div key={key} className="conflict-stat" style={{borderTopColor: resColors[key] || '#6b7280'}}>
            <span className="stat-value" style={{color: resColors[key] || '#6b7280'}}>{val}</span>
            <span className="stat-label">{key === 'total' ? 'Total' : resLabels[key] || key}</span>
          </div>
        ))}
      </div>

      {view === 'heatmap' ? (
        <div className="card">
          <div className="card-header"><h3>Contradiction Heatmap</h3><span className="card-badge">{conflicts.length} conflicts</span></div>
          <div className="card-body"><ConflictHeatmap conflicts={conflicts} /></div>
        </div>
      ) : (
        <>
          <div className="filter-bar">
            <Select value={filter} onChange={setFilter}
              options={[
                {value:'all',label:'All resolutions'},{value:'overwrite',label:'Overwritten'},
                {value:'keep_old',label:'Kept Old'},{value:'raise',label:'Raised Error'},{value:'pending',label:'Pending'},
              ]} />
          </div>

          <div className="card table-wrap">
            {loading ? (<div className="empty-small">Loading...</div>
            ) : filtered.length === 0 ? (
              <div className="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
                <h4>No conflicts found</h4>
                <p>All belief updates have been resolved without contradiction.</p>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{width:'30px'}}></th>
                    <th style={{width:'35%'}}>Existing</th>
                    <th style={{width:'35%'}}>New</th>
                    <th style={{width:'12%'}}>Score</th>
                    <th style={{width:'15%'}}>Resolution</th>
                    <th style={{width:'15%'}}>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c, i) => (
                    <React.Fragment key={`${c.id || i}`}>
                      <tr className={`${c.resolution === 'raise' ? 'conflict-row' : c.resolution === 'keep_old' ? 'conflict-row resolved' : ''}`}>
                        <td>
                          <button className="btn-icon-sm" onClick={() => setExpanded(expanded === `${c.id}-${i}` ? null : `${c.id}-${i}`)}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                              {expanded === `${c.id}-${i}` ? <polyline points="18 15 12 9 6 15"/> : <polyline points="6 9 12 15 18 9"/>}
                            </svg>
                          </button>
                        </td>
                        <td className="mono truncate max-w-[200px]" title={`${c.existing_belief?.subject} ${c.existing_belief?.predicate} ${c.existing_belief?.value || ''}`}>
                          <span className="font-mono text-xs block">{c.existing_belief?.subject} {c.existing_belief?.predicate}</span>
                          <span className="font-mono text-xs text-muted truncate block">{c.existing_belief?.value || ''}</span>
                        </td>
                        <td className="mono truncate max-w-[200px]" title={`${c.new_belief?.subject} ${c.new_belief?.predicate} ${c.new_belief?.value || ''}`}>
                          <span className="font-mono text-xs block">{c.new_belief?.subject} {c.new_belief?.predicate}</span>
                          <span className="font-mono text-xs text-muted truncate block">{c.new_belief?.value || ''}</span>
                        </td>
                        <td>
                          <div className="conf-bar-wrap">
                            <div className={`conf-bar ${(c.score || 0) >= 0.85 ? 'conf-high' : (c.score || 0) >= 0.7 ? 'conf-medium' : 'conf-low'}`} style={{width: `${(c.score || 0) * 100}%`}} />
                            <span className="conf-text">{(c.score || 0).toFixed(2)}</span>
                          </div>
                        </td>
                        <td>
                          <span className="badge" style={{background: `${resColors[c.resolution] || '#6b7280'}20`, color: resColors[c.resolution] || '#6b7280'}}>
                            {resLabels[c.resolution] || c.resolution}
                          </span>
                        </td>
                        <td className="font-mono text-xs text-muted">{c.created_at ? new Date(c.created_at).toLocaleString() : ''}</td>
                      </tr>
                      {expanded === `${c.id}-${i}` && (
                        <tr className="expanded-row">
                          <td colSpan={6}>
                            <div className="expanded-content">
                              <div className="grid-2col">
                                <div><span className="text-xs text-muted">Reason</span><p className="text-sm">{c.reason || 'N/A'}</p></div>
                                {c.resolution_note && <div><span className="text-xs text-muted">Resolution Note</span><p className="font-mono text-sm" style={{color: resColors[c.resolution]}}>{c.resolution_note}</p></div>}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
