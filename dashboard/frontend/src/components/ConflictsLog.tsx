import React, { useEffect, useState } from 'react';

interface Props { sessionId: string; onRefresh: () => void; }

export function ConflictsLog({ sessionId, onRefresh }: Props) {
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetchConflicts = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/sessions/${sessionId}/history`);
      const data = await res.json();
      setConflicts(data.history || []);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchConflicts(); }, [sessionId]);

  const filtered = filter === 'all' ? conflicts : conflicts.filter(c => c.resolution === filter);

  const resColors: Record<string, string> = { overwrite: '#d29922', keep_old: '#3fb950', raise: '#f85149', pending: '#6e7681' };
  const resLabels: Record<string, string> = { overwrite: 'Overwritten', keep_old: 'Kept Old', raise: 'Raised', pending: 'Pending' };

  const stats = { total: conflicts.length, ...Object.fromEntries(['overwrite','keep_old','raise','pending'].map(k => [k, conflicts.filter(c => c.resolution === k).length])) };

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Conflict Log</h1>
        <p className="page-subtitle">{conflicts.length} total resolution events</p>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={fetchConflicts}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
            Refresh
          </button>
        </div>
      </div>

      <div className="conflict-stats-bar">
        {Object.entries(stats).map(([key, val]) => (
          <div key={key} className="conflict-stat" style={{borderLeft: `3px solid ${resColors[key] || '#6e7681'}`}}>
            <span className="stat-value" style={{color: resColors[key] || '#6e7681', fontSize:'1.5rem'}}>{val}</span>
            <span className="stat-label">{key === 'total' ? 'Total' : resLabels[key] || key}</span>
          </div>
        ))}
      </div>

      <div className="filter-bar">
        <select value={filter} onChange={e => setFilter(e.target.value)} className="filter-select">
          <option value="all">All resolutions</option>
          <option value="overwrite">Overwritten</option>
          <option value="keep_old">Kept Old</option>
          <option value="raise">Raised Error</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      <div className="glass-card">
        {loading ? (
          <div className="empty-small">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="empty-small">No conflicts found</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th style={{width:'30px'}}></th>
                <th>Existing</th>
                <th>New</th>
                <th style={{width:'100px'}}>Score</th>
                <th style={{width:'120px'}}>Resolution</th>
                <th style={{width:'140px'}}>Time</th>
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
                      <span className="badge" style={{background: `${resColors[c.resolution] || '#6e7681'}20`, color: resColors[c.resolution] || '#6e7681'}}>
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
                            <div>
                              <span className="text-xs text-muted">Reason</span>
                              <p className="text-sm">{c.reason || 'N/A'}</p>
                            </div>
                            {c.resolution_note && (
                              <div>
                                <span className="text-xs text-muted">Resolution Note</span>
                                <p className="font-mono text-sm" style={{color: resColors[c.resolution]}}>{c.resolution_note}</p>
                              </div>
                            )}
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
    </div>
  );
}
