import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Belief, SessionStats, StoreStats, ProviderInfo } from './types';
import { EntityProfileModal } from './EntityProfileModal';
import { BeliefNetwork } from './BeliefNetwork';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';

interface Props { sessionId: string; onRefresh: () => void; }

const categoryColors: Record<string, string> = {
  identity: '#2563eb', technical: '#8b5cf6', planning: '#22c55e',
  constraint: '#f59e0b', state: '#6b7280', general: '#9ca3af',
};

const CARD_ORDER_KEY = 'belifstate_card_order';

const ALL_CARDS = [
  'stats', 'category', 'confidence', 'source', 'health', 'entities', 'types', 'trend', 'growth', 'network',
];

function loadOrder(): string[] {
  try { const o = JSON.parse(localStorage.getItem(CARD_ORDER_KEY) || 'null'); if (Array.isArray(o) && o.length) return o; } catch {}
  return ALL_CARDS;
}

function StatCard({ label, value, icon, color, trend, onClick }: {
  label: string; value: string | number; icon: React.ReactNode; color: string; trend?: string; onClick?: () => void;
}) {
  return (
    <div className="summary-card" onClick={onClick} style={{ cursor: onClick ? 'pointer' : 'default' }}>
      <div className="summary-card-top">
        <div className="summary-card-icon" style={{ background: `${color}12`, color }}>{icon}</div>
        {trend && <span className={`summary-card-trend ${trend.startsWith('+') ? 'up' : 'down'}`}>{trend}</span>}
      </div>
      <div className="summary-card-value">{value}</div>
      <div className="summary-card-label">{label}</div>
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
  const [cardOrder, setCardOrder] = useState<string[]>(loadOrder);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);
  const [allBeliefs, setAllBeliefs] = useState<Belief[]>([]);

  const saveOrder = (order: string[]) => {
    setCardOrder(order);
    localStorage.setItem(CARD_ORDER_KEY, JSON.stringify(order));
  };

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
        const allRes = await fetch(`/api/sessions/${sessionId}/beliefs?include_hypothetical=true&limit=2000`);
        const allData = await allRes.json();
        setAllBeliefs(allData.beliefs || []);
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, [sessionId]);

  const confRanges = stats?.by_confidence_range || {};
  const confColors: Record<string, string> = {
    '0.0-0.5': '#ef4444', '0.5-0.7': '#f59e0b', '0.7-0.85': '#2563eb', '0.85-0.95': '#22c55e', '0.95-1.0': '#22c55e',
  };

  // chart data
  const catChartData = stats ? Object.entries(stats.by_category).map(([name, value]) => ({ name, value })) : [];
  const typeChartData = stats ? Object.entries(stats.by_type).map(([name, value]) => ({ name, value })) : [];
  const sourceChartData = stats ? Object.entries(stats.by_source).map(([name, value]) => ({ name, value })) : [];

  // confidence trend data derived from beliefs
  const trendData = (() => {
    const turns = [...new Set(beliefs.map(b => b.turn))].sort((a, b) => a - b);
    return turns.map(turn => {
      const turnBeliefs = beliefs.filter(b => b.turn === turn);
      const avg = turnBeliefs.length ? turnBeliefs.reduce((s, b) => s + b.confidence, 0) / turnBeliefs.length : 0;
      return { turn, avgConf: +(avg * 100).toFixed(1), count: turnBeliefs.length };
    });
  })();

  // growth data
  const growthData = (() => {
    const turns = [...new Set(beliefs.map(b => b.turn))].sort((a, b) => a - b);
    let running = 0;
    return turns.map(turn => {
      running += beliefs.filter(b => b.turn === turn).length;
      return { turn, total: running };
    });
  })();

  const handleDragStart = useCallback((e: React.DragEvent, idx: number) => {
    setDragIdx(idx);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, idx: number) => {
    e.preventDefault();
    setOverIdx(idx);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, idx: number) => {
    e.preventDefault();
    if (dragIdx === null || dragIdx === idx) { setDragIdx(null); setOverIdx(null); return; }
    const order = [...cardOrder];
    const [item] = order.splice(dragIdx, 1);
    order.splice(idx, 0, item);
    saveOrder(order);
    setDragIdx(null);
    setOverIdx(null);
  }, [dragIdx, cardOrder]);

  if (loading) {
    return (
      <div className="page">
        <div className="skeleton-grid">
          {[1,2,3,4].map(i => <div key={i} className="skeleton-card" />)}
        </div>
      </div>
    );
  }

  const renderCard = (id: string, idx: number) => {
    const isDrag = dragIdx === idx;
    const isOver = overIdx === idx;
    const style: React.CSSProperties = { opacity: isDrag ? 0.4 : 1, borderTop: isOver ? '3px solid var(--blue-500)' : undefined, cursor: 'grab' };

    switch (id) {
      case 'stats': return (
        <div className="summary-cards" style={{ gridColumn: '1 / -1' }} key="stat-cards">
          <StatCard label="Total Beliefs" value={stats?.total_beliefs ?? 0}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>}
            color="#2563eb" />
          <StatCard label="Avg Confidence" value={stats ? `${(stats.avg_confidence * 100).toFixed(1)}%` : '-'}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>}
            color="#22c55e" />
          <StatCard label="Latest Turn" value={stats?.latest_turn ?? '-'}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>}
            color="#f59e0b" />
          <StatCard label="Entities" value={stats?.entities ?? 0}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>}
            color="#8b5cf6" />
          <StatCard label="Contradictions" value={stats?.contradiction_count ?? 0}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>}
            color="#ef4444" trend={stats && stats.contradiction_count > 0 ? `${stats.contradiction_count} total` : undefined} />
          <StatCard label="Categories" value={stats ? Object.keys(stats.by_category).length : 0}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>}
            color="#6b7280" />
        </div>
      );

      case 'category': return (
        <div className="card" style={style} draggable onDragStart={e => handleDragStart(e, idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={e => handleDrop(e, idx)}>
          <div className="card-header"><h3>Category Breakdown</h3><span className="card-badge">{stats ? Object.entries(stats.by_category).reduce((s, [,c]) => s + c, 0) : 0}</span></div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={catChartData}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" radius={[4,4,0,0]}>
                  {catChartData.map((e, i) => <Cell key={i} fill={categoryColors[e.name] || '#9ca3af'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      );

      case 'confidence': return (
        <div className="card" style={style} draggable onDragStart={e => handleDragStart(e, idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={e => handleDrop(e, idx)}>
          <div className="card-header"><h3>Confidence Heatmap</h3><span className="card-badge">range distribution</span></div>
          <div className="card-body">
            {stats && (
              <div className="heatmap">
                <table className="heatmap-table">
                  <thead><tr><th></th>{['identity','technical','planning','constraint','state'].map(c => (<th key={c} className="heatmap-col-label" title={c}>{c.slice(0,4)}</th>))}</tr></thead>
                  <tbody>{[['0.95-1.0',0.95],['0.85-0.95',0.85],['0.7-0.85',0.7],['0.5-0.7',0.5],['0.0-0.5',0]].map(([range, min]) => {
                    const cats = ['identity','technical','planning','constraint','state'];
                    const maxVal = Math.max(1, ...cats.map(c => stats.by_category[c] || 0));
                    return (<tr key={range}><td className="heatmap-row-label">{range}</td>{cats.map(cat => {
                      const count = beliefs.filter(b => (b.category || 'general') === cat && b.confidence >= (min as number) && b.confidence < ((min as number) === 0 ? 0.5 : (min as number) + ((min as number) === 0.95 ? 0.05 : (min as number) === 0.85 ? 0.1 : (min as number) === 0.7 ? 0.15 : (min as number) === 0.5 ? 0.2 : 0.5))).length;
                      const intensity = count > 0 ? Math.min(0.15 + (count / maxVal) * 0.7, 0.85) : 0.04;
                      return (<td key={cat} className="heatmap-cell" style={{ background: count > 0 ? `rgba(37,99,235,${intensity})` : 'rgba(0,0,0,0.04)', color: count > 0 ? '#374151' : '#9ca3af' }}>{count > 0 ? count : '·'}</td>);
                    })}</tr>);
                  })}</tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      );

      case 'source': return (
        <div className="card" style={style} draggable onDragStart={e => handleDragStart(e, idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={e => handleDrop(e, idx)}>
          <div className="card-header"><h3>Source Distribution</h3><span className="card-badge">{stats ? Object.entries(stats.by_source).reduce((s,[,c]) => s + c, 0) : 0}</span></div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={sourceChartData} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={70} />
                <Tooltip />
                <Bar dataKey="value" fill="#2563eb" radius={[0,4,4,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      );

      case 'health': return (
        <div className="card" style={style} draggable onDragStart={e => handleDragStart(e, idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={e => handleDrop(e, idx)}>
          <div className="card-header"><h3>Store Health</h3><span className="card-badge">{storeStats?.type || '-'}</span></div>
          <div className="card-body">
            {storeStats ? (
              <div className="health-grid">
                <div className="health-item"><div className={`health-dot ${storeStats.healthy ? 'green' : 'red'}`} /><div className="health-info"><span className="health-label">Status</span><span className="health-value">{storeStats.healthy ? 'Healthy' : 'Unhealthy'}</span></div></div>
                <div className="health-item"><div className="health-info"><span className="health-label">Total Beliefs</span><span className="health-value">{storeStats.total_beliefs}</span></div></div>
                <div className="health-item"><div className="health-info"><span className="health-label">Sessions</span><span className="health-value">{storeStats.sessions}</span></div></div>
                <div className="health-item"><div className="health-info"><span className="health-label">Storage</span><span className="health-value">{storeStats.type.replace('Store','')}</span></div></div>
              </div>
            ) : <div className="empty-small">Store stats unavailable</div>}
          </div>
        </div>
      );

      case 'entities': return (
        <div className="card" style={style} draggable onDragStart={e => handleDragStart(e, idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={e => handleDrop(e, idx)}>
          <div className="card-header"><h3>Entity Quick View</h3><span className="card-badge">{stats?.entities ?? 0} entities</span></div>
          <div className="card-body">
            <div className="entity-cloud">
              {[...new Set(beliefs.map(b => b.subject))].sort((a, b) => beliefs.filter(x => x.subject === b).length - beliefs.filter(x => x.subject === a).length).slice(0, 20).map(subject => {
                const count = beliefs.filter(b => b.subject === subject).length;
                const maxCount = Math.max(1, ...beliefs.map(b => beliefs.filter(x => x.subject === b.subject).length));
                return (<button key={subject} className="entity-chip" style={{ fontSize: `${(0.7 + (count / maxCount) * 0.8) * 14}px` }} onClick={() => setEntitySubject(subject)}>{subject}<span className="entity-chip-count">{count}</span></button>);
              })}
            </div>
          </div>
        </div>
      );

      case 'types': return (
        <div className="card" style={style} draggable onDragStart={e => handleDragStart(e, idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={e => handleDrop(e, idx)}>
          <div className="card-header"><h3>Belief Type Distribution</h3><span className="card-badge">{stats ? Object.entries(stats.by_type).reduce((s,[,c]) => s + c, 0) : 0}</span></div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={typeChartData}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" radius={[4,4,0,0]}>
                  {typeChartData.map((e, i) => {
                    const colors: Record<string, string> = { assertion: '#22c55e', update: '#f59e0b', contradiction: '#ef4444' };
                    return <Cell key={i} fill={colors[e.name] || '#2563eb'} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      );

      case 'trend': return (
        <div className="card" style={style} draggable onDragStart={e => handleDragStart(e, idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={e => handleDrop(e, idx)}>
          <div className="card-header"><h3>Confidence Trend</h3><span className="card-badge">{trendData.length} turns</span></div>
          <div className="card-body">
            {trendData.length > 1 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={trendData}>
                  <XAxis dataKey="turn" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="avgConf" stroke="#2563eb" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div className="empty-small">Need more turns to show trend</div>}
          </div>
        </div>
      );

      case 'growth': return (
        <div className="card" style={style} draggable onDragStart={e => handleDragStart(e, idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={e => handleDrop(e, idx)}>
          <div className="card-header"><h3>Session Growth</h3><span className="card-badge">{growthData.length} turns</span></div>
          <div className="card-body">
            {growthData.length > 1 ? (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={growthData}>
                  <XAxis dataKey="turn" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="total" stroke="#2563eb" strokeWidth={2} fill="rgba(37,99,235,0.08)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : <div className="empty-small">Need more turns to show growth</div>}
          </div>
        </div>
      );

      case 'network': return (
        <div className="card" style={style} draggable onDragStart={e => handleDragStart(e, idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={e => handleDrop(e, idx)}>
          <div className="card-header"><h3>Belief Network</h3><span className="card-badge">{allBeliefs.length} beliefs</span></div>
          <div className="card-body" style={{ padding: '8px 12px' }}>
            <BeliefNetwork beliefs={allBeliefs} onSelectSubject={setEntitySubject} />
          </div>
        </div>
      );

      default: return null;
    }
  };

  const visibleCards = cardOrder.filter(id => id !== 'stats');
  const statsCard = cardOrder.includes('stats') ? renderCard('stats', -1) : null;

  return (
    <div className="page">
      {statsCard}
      {statsCard && <div className="drag-hint">Drag cards to reorder</div>}
      <div className="grid-2col">
        {visibleCards.map((id, idx) => {
          const actualIdx = cardOrder.indexOf(id);
          return <React.Fragment key={id}>{renderCard(id, actualIdx)}</React.Fragment>;
        })}
      </div>
      {entitySubject && (
        <EntityProfileModal sessionId={sessionId} subject={entitySubject} onClose={() => setEntitySubject(null)} />
      )}
    </div>
  );
}
