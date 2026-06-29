import React, { useState } from 'react';
import { AlertRule } from '../hooks/useNotifications';

interface Props {
  rules: AlertRule[];
  onUpdate: (rules: AlertRule[]) => void;
}

const METRICS = [
  { value: 'contradiction_count', label: 'Contradiction Count' },
  { value: 'confidence_drop', label: 'Avg Confidence Drop' },
  { value: 'new_beliefs', label: 'New Beliefs' },
  { value: 'entity_count', label: 'Entity Count' },
];
const CONDITIONS = [
  { value: 'gt', label: '>' },
  { value: 'lt', label: '<' },
  { value: 'eq', label: '=' },
];

export function AlertRules({ rules, onUpdate }: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<AlertRule>({ id: '', name: '', metric: 'contradiction_count', condition: 'gt', value: 0, enabled: true });

  const add = () => {
    const id = crypto.randomUUID();
    onUpdate([...rules, { ...form, id }]);
    setForm({ id: '', name: '', metric: 'contradiction_count', condition: 'gt', value: 0, enabled: true });
    setEditing(null);
  };

  const remove = (id: string) => onUpdate(rules.filter(r => r.id !== id));
  const toggle = (id: string) => onUpdate(rules.map(r => r.id === id ? { ...r, enabled: !r.enabled } : r));

  return (
    <div>
      <div className="card-header">
        <h3>Alert Rules</h3>
        <button className="btn btn-secondary btn-sm" onClick={() => setEditing(editing === 'new' ? null : 'new')}>
          {editing === 'new' ? 'Cancel' : '+ Add Rule'}
        </button>
      </div>
      <div className="card-body">
        {editing === 'new' && (
          <div className="alert-form">
            <input type="text" placeholder="Rule name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="search-input" style={{flex:1}} />
            <select value={form.metric} onChange={e => setForm({ ...form, metric: e.target.value as any })} className="filter-select">
              {METRICS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <select value={form.condition} onChange={e => setForm({ ...form, condition: e.target.value as any })} className="filter-select" style={{width:60}}>
              {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
            <input type="number" value={form.value} onChange={e => setForm({ ...form, value: Number(e.target.value) })} className="settings-input" style={{width:80}} />
            <button className="btn btn-primary btn-sm" onClick={add} disabled={!form.name}>Add</button>
          </div>
        )}
        {rules.length === 0 && <div className="empty-small">No alert rules configured</div>}
        {rules.map(r => (
          <div key={r.id} className="alert-rule-row">
            <div className="alert-rule-info">
              <span className={`alert-rule-name ${r.enabled ? '' : 'text-muted'}`}>{r.name}</span>
              <span className="alert-rule-detail">{METRICS.find(m => m.value === r.metric)?.label} {CONDITIONS.find(c => c.value === r.condition)?.label} {r.value}</span>
            </div>
            <div className="alert-rule-actions">
              <button className={`btn-icon-sm ${r.enabled ? 'text-muted' : ''}`} onClick={() => toggle(r.id)} title={r.enabled ? 'Disable' : 'Enable'}>
                {r.enabled
                  ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                }
              </button>
              <button className="btn-icon-sm text-danger" onClick={() => remove(r.id)} title="Delete">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
