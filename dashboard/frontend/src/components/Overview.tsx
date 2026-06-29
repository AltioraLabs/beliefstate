import React, { useEffect, useState } from 'react';
import { Belief, SessionStats, StoreStats, ProviderInfo, DashboardConfig } from './types';
import { EntityProfileModal } from './EntityProfileModal';

interface Props {
  sessionId: string;
  onRefresh: () => void;
}

const categoryColors: Record<string, string> = {
  identity: '#58a6ff', technical: '#a371f7', planning: '#3fb950',
  constraint: '#d29922', state: '#8b949e', general: '#6e7681',
};

function StatCard({ label, value, icon, color, trend, onClick }: {
  label: string; value: string | number; icon: React.ReactNode; color: string; trend?: string; onClick?: () => void;
}) {
  return (
    <div className="stat-card" onClick={onClick} style={{ cursor: onClick ? 'pointer' : 'default' }}>
      <div className="stat-card-inner">
        <div className="stat-card-icon" style={{ background: `${color}15`, color }}>{icon}</div>
        <div className="stat-card-body">
          <div className="stat-value" style={{ color }}>{value}</div>
          <div className="stat-label">{label}</div>
          {trend && <div className="stat-trend">{trend}</div>}
        </div>
      </div>
    </div>
  );
}

export function Overview({ sessionId, onRefresh }: Props) {
  const [beliefs, setBeliefs] = useState<Belief[]>([]);
  const [stats, setStats] = useState<SessionStats | null>(null);
  const [storeStats, setStoreStats] = useState<StoreStats | null>(null);
  const [providerInfo, setProviderInfo] = useState<ProviderInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [entitySubject, setEntitySubject] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [bRes, sRes, pRes] = await Promise.all([
          fetch(`/api/sessions/${sessionId}/beliefs?include_hypothetical=true`),
          fetch('/api/store/stats'),
          fetch('/api/provider/info'),
        ]);
        const bData = await bRes.json();
        setBeliefs(bData.beliefs || []);

        try { setStoreStats(await sRes.json()); } catch { setStoreStats(null); }
        try { setProviderInfo(await pRes.json()); } catch { setProviderInfo(null); }

        const sRes2 = await fetch(`/api/sessions/${sessionId}/stats`);
        setStats(await sRes2.json());
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, [sessionId]);

  if (loading) {
    return (
      <div className="page">
        <div className="page-header"><h1 className="page-title">Overview</h1></div>
        <div className="skeleton-grid">
          {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton-card" />)}
        </div>
      </div>
    );
  }

  const confRanges = stats?.by_confidence_range || {};
  const confColors: Record<string, string> = {
    '0.0-0.5': '#f85149', '0.5-0.7': '#d29922', '0.7-0.85': '#58a6ff', '0.85-0.95': '#3fb950', '0.95-1.0': '#3fb950',
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Session Overview</h1>
          <p className="page-subtitle">
            Session <span className="mono-highlight">{sessionId.length > 40 ? sessionId.slice(0, 40) + '…' : sessionId}</span>
          </p>
        </div>
        <div className="page-actions">
          {providerInfo?.internal && (
            <div className="chip-group">
              <span className="chip">{providerInfo.internal.name}{providerInfo.internal.model ? ` · ${providerInfo.internal.model}` : ''}</span>
            </div>
          )}
        </div>
      </div>

      <div className="stats-grid">
        <StatCard label="Total Beliefs" value={stats?.total_beliefs ?? 0}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>}
          color="#58a6ff" />
        <StatCard label="Avg Confidence" value={stats ? `${(stats.avg_confidence * 100).toFixed(1)}%` : '-'}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>}
          color="#3fb950" />
        <StatCard label="Latest Turn" value={stats?.latest_turn ?? '-'}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>}
          color="#d29922" />
        <StatCard label="Entities" value={stats?.entities ?? 0}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>}
          color="#a371f7" />
        <StatCard label="Contradictions" value={stats?.contradiction_count ?? 0}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>}
          color="#f85149" trend={stats && stats.contradiction_count > 0 ? `${stats.contradiction_count} resolved` : undefined} />
        <StatCard label="Categories" value={stats ? Object.keys(stats.by_category).length : 0}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>}
          color="#6e7681" />
      </div>

      <div className="grid-2col">
        <div className="glass-card">
          <div className="card-header">
            <h3>Category Breakdown</h3>
            <span className="card-badge">{stats ? Object.entries(stats.by_category).reduce((s, [,c]) => s + c, 0) : 0}</span>
          </div>
          <div className="card-body">
            {stats && Object.entries(stats.by_category).map(([cat, count]) => {
              const pct = stats.total_beliefs ? (count / stats.total_beliefs * 100) : 0;
              return (
                <div key={cat} className="bar-row">
                  <div className="bar-label">
                    <span className="bar-dot" style={{ background: categoryColors[cat] || '#6e7681' }} />
                    <span>{cat}</span>
                  </div>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${pct}%`, background: categoryColors[cat] || '#6e7681' }} />
                  </div>
                  <span className="bar-value">{count}</span>
                </div>
              );
            })}
            {(!stats || Object.keys(stats.by_category).length === 0) && (
              <div className="empty-small">No beliefs stored yet</div>
            )}
          </div>
        </div>

        <div className="glass-card">
          <div className="card-header">
            <h3>Confidence Heatmap</h3>
            <span className="card-badge">range distribution</span>
          </div>
          <div className="card-body">
            {stats && (
              <div className="heatmap">
                <table className="heatmap-table">
                  <thead>
                    <tr>
                      <th></th>
                      {['identity','technical','planning','constraint','state'].map(c => (
                        <th key={c} className="heatmap-col-label" title={c}>{c.slice(0,4)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[['0.95-1.0',0.95],['0.85-0.95',0.85],['0.7-0.85',0.7],['0.5-0.7',0.5],['0.0-0.5',0]].map(([range, min]) => {
                      const catData = stats.by_category;
                      const cats = ['identity','technical','planning','constraint','state'];
                      const maxVal = Math.max(1, ...cats.map(c => catData[c] || 0));
                      return (
                        <tr key={range}>
                          <td className="heatmap-row-label">{range}</td>
                          {cats.map(cat => {
                            const count = beliefs.filter(b => {
                              const cat2 = b.category || 'general';
                              return cat2 === cat && b.confidence >= min && b.confidence < (min === 0 ? 0.5 : min + (min === 0.95 ? 0.05 : min === 0.85 ? 0.1 : min === 0.7 ? 0.15 : min === 0.5 ? 0.2 : 0.5));
                            }).length;
                            const intensity = count > 0 ? Math.min(0.15 + (count / maxVal) * 0.7, 0.85) : 0.04;
                            return (
                              <td key={cat} className="heatmap-cell" style={{
                                background: count > 0 ? `rgba(88,166,255,${intensity})` : 'rgba(48,54,61,0.3)',
                                color: count > 0 ? '#e6edf3' : '#484f58',
                              }}>
                                {count > 0 ? count : '·'}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="glass-card">
          <div className="card-header">
            <h3>Source Distribution</h3>
            <span className="card-badge">{stats ? Object.entries(stats.by_source).reduce((s,[,c]) => s + c, 0) : 0}</span>
          </div>
          <div className="card-body">
            <div className="donut-row">
              {stats && Object.entries(stats.by_source).map(([src, count]) => {
                const pct = stats.total_beliefs ? (count / stats.total_beliefs * 100) : 0;
                const color = src === 'user' ? '#58a6ff' : src === 'assistant' ? '#a371f7' : '#6e7681';
                return (
                  <div key={src} className="source-bar">
                    <div className="source-bar-fill" style={{ width: `${pct}%`, background: color }} />
                    <div className="source-bar-info">
                      <span className="source-bar-label" style={{ color }}>{src}</span>
                      <span className="source-bar-count">{count}</span>
                      <span className="source-bar-pct">{pct.toFixed(0)}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="glass-card">
          <div className="card-header">
            <h3>Store Health</h3>
            <span className="card-badge">{storeStats?.type || '-'}</span>
          </div>
          <div className="card-body">
            {storeStats ? (
              <div className="health-grid">
                <div className="health-item">
                  <div className={`health-dot ${storeStats.healthy ? 'green' : 'red'}`} />
                  <div className="health-info">
                    <span className="health-label">Status</span>
                    <span className="health-value">{storeStats.healthy ? 'Healthy' : 'Unhealthy'}</span>
                  </div>
                </div>
                <div className="health-item">
                  <div className="health-info">
                    <span className="health-label">Total Beliefs</span>
                    <span className="health-value">{storeStats.total_beliefs}</span>
                  </div>
                </div>
                <div className="health-item">
                  <div className="health-info">
                    <span className="health-label">Sessions</span>
                    <span className="health-value">{storeStats.sessions}</span>
                  </div>
                </div>
                <div className="health-item">
                  <div className="health-info">
                    <span className="health-label">Storage</span>
                    <span className="health-value">{storeStats.type.replace('Store','')}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-small">Store stats unavailable</div>
            )}
          </div>
        </div>

        <div className="glass-card">
          <div className="card-header">
            <h3>Entity Quick View</h3>
            <span className="card-badge">{stats?.entities ?? 0} entities</span>
          </div>
          <div className="card-body">
            <div className="entity-cloud">
              {[...new Set(beliefs.map(b => b.subject))]
                .sort((a, b) => beliefs.filter(x => x.subject === b).length - beliefs.filter(x => x.subject === a).length)
                .slice(0, 20)
                .map(subject => {
                  const count = beliefs.filter(b => b.subject === subject).length;
                  const maxCount = Math.max(1, ...beliefs.map(b => beliefs.filter(x => x.subject === b.subject).length));
                  const size = 0.7 + (count / maxCount) * 0.8;
                  return (
                    <button key={subject} className="entity-chip" style={{ fontSize: `${size * 14}px` }}
                      onClick={() => setEntitySubject(subject)}>
                      {subject}
                      <span className="entity-chip-count">{count}</span>
                    </button>
                  );
                })}
            </div>
          </div>
        </div>

        <div className="glass-card">
          <div className="card-header">
            <h3>Belief Type Distribution</h3>
            <span className="card-badge">{stats ? Object.entries(stats.by_type).reduce((s,[,c]) => s + c, 0) : 0}</span>
          </div>
          <div className="card-body">
            <div className="type-chart">
              {stats && Object.entries(stats.by_type).map(([type, count]) => {
                const pct = stats.total_beliefs ? (count / stats.total_beliefs * 100) : 0;
                const colors: Record<string, string> = { assertion: '#3fb950', update: '#d29922', contradiction: '#f85149' };
                const color = colors[type] || '#58a6ff';
                return (
                  <div key={type} className="type-segment">
                    <div className="type-segment-bar" style={{ background: color, width: `${pct}%`, minWidth: count > 0 ? '4px' : '0' }} />
                    <div className="type-segment-info">
                      <span style={{ color }}>{type}</span>
                      <span className="font-mono text-xs">{count} ({pct.toFixed(0)}%)</span>
                    </div>
                  </div>
                );
              })}
              <div className="type-extra mt-3">
                <div className="extra-row">
                  <span>Hypothetical</span>
                  <span className="font-mono">{stats?.by_hypothetical?.yes ?? 0} / {stats?.total_beliefs ?? 0}</span>
                </div>
                <div className="extra-row">
                  <span>Confidence ≥ 0.85</span>
                  <span className="font-mono">{Object.entries(confRanges).filter(([k]) => ['0.85-0.95','0.95-1.0'].includes(k)).reduce((s,[,c]) => s + c, 0)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {entitySubject && (
        <EntityProfileModal
          sessionId={sessionId}
          subject={entitySubject}
          onClose={() => setEntitySubject(null)}
        />
      )}
    </div>
  );
}
