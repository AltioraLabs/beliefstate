import React, { useMemo } from 'react';
import { Belief } from './types';

interface Props {
  beliefs: Belief[];
  onSelectSubject?: (subject: string) => void;
}

interface Node { id: string; label: string; count: number; type: 'subject' | 'predicate' | 'value'; }
interface Edge { source: string; target: string; }

export function BeliefNetwork({ beliefs, onSelectSubject }: Props) {
  const { nodes, edges } = useMemo(() => {
    const n: Node[] = [];
    const e: Edge[] = [];
    const added = new Set<string>();
    for (const b of beliefs.slice(0, 60)) {
      if (!added.has(b.subject)) { n.push({ id: b.subject, label: b.subject, count: 1, type: 'subject' }); added.add(b.subject); }
      const predId = `${b.subject}→${b.predicate}`;
      if (!added.has(predId)) { n.push({ id: predId, label: b.predicate, count: 1, type: 'predicate' }); added.add(predId); }
      e.push({ source: b.subject, target: predId });
      if (!added.has(b.value)) {
        if (b.value.length < 40) { n.push({ id: b.value, label: b.value, count: 1, type: 'value' }); added.add(b.value); }
        e.push({ source: predId, target: b.value });
      }
    }
    return { nodes: n, edges: e };
  }, [beliefs]);

  const radius = Math.min(200, Math.max(140, nodes.length * 8));
  const subjectNodes = nodes.filter(n => n.type === 'subject');
  const predicateNodes = nodes.filter(n => n.type === 'predicate');
  const valueNodes = nodes.filter(n => n.type === 'value');

  const layout = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    const cx = 180, cy = 140;
    subjectNodes.forEach((n, i) => { const a = (i / subjectNodes.length) * Math.PI * 2 - Math.PI / 2; pos[n.id] = { x: cx + Math.cos(a) * radius * 0.5, y: cy + Math.sin(a) * radius * 0.5 }; });
    predicateNodes.forEach((n, i) => { const a = (i / predicateNodes.length) * Math.PI * 2 + Math.PI / 6; pos[n.id] = { x: cx + Math.cos(a) * radius * 0.8, y: cy + Math.sin(a) * radius * 0.8 }; });
    valueNodes.forEach((n, i) => { const a = (i / valueNodes.length) * Math.PI * 2 + Math.PI / 3; pos[n.id] = { x: cx + Math.cos(a) * radius, y: cy + Math.sin(a) * radius }; });
    return pos;
  }, [subjectNodes, predicateNodes, valueNodes, radius]);

  if (nodes.length === 0) return <div className="empty-small">No beliefs to graph</div>;
  if (nodes.length < 3) return <div className="empty-small">Add more beliefs to see the graph</div>;

  return (
    <svg viewBox="0 0 360 280" className="network-svg">
      {edges.map((e, i) => {
        const s = layout[e.source], t = layout[e.target];
        if (!s || !t) return null;
        return <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y} className="network-edge" />;
      })}
      {nodes.map(n => {
        const p = layout[n.id];
        if (!p) return null;
        const r = n.type === 'subject' ? 7 : n.type === 'predicate' ? 5 : 4;
        const fill = n.type === 'subject' ? 'var(--blue-500)' : n.type === 'predicate' ? 'var(--violet-500)' : 'var(--green-500)';
        return (
          <g key={n.id} className="network-node" onClick={() => n.type === 'subject' && onSelectSubject?.(n.id)} style={{ cursor: n.type === 'subject' ? 'pointer' : 'default' }}>
            <circle cx={p.x} cy={p.y} r={r} fill={fill} opacity={0.85} />
            <title>{n.label}</title>
          </g>
        );
      })}
    </svg>
  );
}
