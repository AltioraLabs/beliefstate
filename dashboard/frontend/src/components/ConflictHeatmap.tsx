import React, { useMemo } from 'react';

interface Props {
  conflicts: any[];
}

export function ConflictHeatmap({ conflicts }: Props) {
  const { subjects, predicates, matrix, maxVal } = useMemo(() => {
    const subjSet = new Set<string>();
    const predSet = new Set<string>();
    const map: Record<string, Record<string, number>> = {};
    for (const c of conflicts) {
      const s = c.existing_belief?.subject || c.new_belief?.subject || 'unknown';
      const p = c.existing_belief?.predicate || c.new_belief?.predicate || 'unknown';
      subjSet.add(s); predSet.add(p);
      if (!map[s]) map[s] = {};
      map[s][p] = (map[s][p] || 0) + 1;
    }
    const subjects = [...subjSet].sort().slice(0, 15);
    const predicates = [...predSet].sort().slice(0, 10);
    let maxVal = 0;
    for (const s of subjects) for (const p of predicates) { maxVal = Math.max(maxVal, map[s]?.[p] || 0); }
    return { subjects, predicates, matrix: map, maxVal: Math.max(1, maxVal) };
  }, [conflicts]);

  if (subjects.length === 0) return <div className="empty-small">No conflict data for heatmap</div>;

  return (
    <div className="heatmap-scroll">
      <table className="conflict-heatmap-table">
        <thead>
          <tr>
            <th></th>
            {predicates.map(p => <th key={p} className="heatmap-col-label" title={p}>{p.length > 8 ? p.slice(0, 8) + '…' : p}</th>)}
          </tr>
        </thead>
        <tbody>
          {subjects.map(s => (
            <tr key={s}>
              <td className="heatmap-row-label" title={s}>{s.length > 12 ? s.slice(0, 12) + '…' : s}</td>
              {predicates.map(p => {
                const val = matrix[s]?.[p] || 0;
                const intensity = val > 0 ? 0.1 + (val / maxVal) * 0.7 : 0.03;
                return (
                  <td key={p} className="heatmap-cell" style={{
                    background: val > 0 ? `rgba(239,68,68,${intensity})` : 'rgba(0,0,0,0.02)',
                    color: val > 0 ? '#dc2626' : '#d1d5db',
                  }}>
                    {val > 0 ? val : '·'}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
