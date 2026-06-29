import React, { useEffect, useState } from 'react';
import { DashboardConfig, ProviderInfo } from './types';
import { Select } from './Select';
import { AlertRules as AlertRulesComp } from './AlertRules';
import { AlertRule } from '../hooks/useNotifications';

interface Props {
  alerts: AlertRule[];
  onUpdateAlerts: (rules: AlertRule[]) => void;
}

export function Settings({ alerts, onUpdateAlerts }: Props) {
  const [config, setConfig] = useState<DashboardConfig | null>(null);
  const [providerInfo, setProviderInfo] = useState<ProviderInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');
  const [reExtractResult, setReExtractResult] = useState<any>(null);

  useEffect(() => {
    (async () => {
      try {
        const [cRes, pRes] = await Promise.all([fetch('/api/config'), fetch('/api/provider/info')]);
        const cfg = await cRes.json();
        setConfig(cfg);
        try { setProviderInfo(await pRes.json()); } catch {}
      } catch {}
    })();
  }, []);

  const updateField = (field: string, value: any) => {
    if (!config) return;
    setConfig({...config, [field]: value});
    setSaved(false);
  };

  const saveConfig = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {}
    setSaving(false);
  };

  const handleReExtract = async () => {
    if (!config) return;
    setReExtractResult(null);
    try {
      const res = await fetch(`/api/sessions/default/re-extract`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ custom_prompt: customPrompt, message: 'Re-extract with custom prompt' }) });
      setReExtractResult(await res.json());
    } catch {}
  };

  if (!config) return <div className="page"><div className="skeleton-card" style={{height:400}}/></div>;

  const sections = [
    { title: 'Storage & Limits', icon: 'box', fields: [
      { key: 'max_beliefs', label: 'Max Beliefs', type: 'number', min: 1, max: 10000 },
      { key: 'belief_budget_tokens', label: 'Token Budget', type: 'number', min: 100, max: 5000 },
      { key: 'belief_sort_strategy', label: 'Sort Strategy', type: 'select', options: [
        {value:'confidence_recency', label:'Confidence + Recency'},{value:'recency', label:'Recency'},{value:'confidence', label:'Confidence'},
      ]},
    ]},
    { title: 'Detection Thresholds', icon: 'sliders', fields: [
      { key: 'similarity_threshold', label: 'Similarity', type: 'range', min: 0.5, max: 0.99 },
      { key: 'contradiction_threshold', label: 'Contradiction', type: 'range', min: 0.5, max: 0.99 },
      { key: 'entailment_threshold', label: 'Entailment', type: 'range', min: 0.5, max: 0.99 },
      { key: 'min_injection_confidence', label: 'Min Injection Confidence', type: 'range', min: 0, max: 1 },
    ]},
    { title: 'Resolution', icon: 'git-merge', fields: [
      { key: 'resolution_strategy', label: 'Strategy', type: 'select', options: [
        {value:'overwrite', label:'Overwrite (replace old)'},{value:'keep_old', label:'Keep Old (ignore new)'},{value:'raise', label:'Raise Error'},
      ]},
      { key: 'respect_strategy_for_updates', label: 'Respect strategy for updates', type: 'checkbox' },
    ]},
    { title: 'Staleness', icon: 'clock', fields: [
      { key: 'enable_staleness_scoring', label: 'Enable Staleness Scoring', type: 'checkbox' },
      { key: 'staleness_threshold', label: 'Staleness Threshold', type: 'range', min: 0, max: 1 },
      { key: 'include_hypothetical_in_context', label: 'Include Hypotheticals in Context', type: 'checkbox' },
    ]},
  ];

  return (
    <div className="page settings-page">
      <div className="page-actions">
        <button className="btn btn-primary" onClick={saveConfig} disabled={saving}>
          {saving ? 'Saving...' : saved ? '✓ Saved!' : 'Save Changes'}
        </button>
      </div>

      <div className="settings-grid">
        {sections.map(section => (
          <div key={section.title} className="card">
            <div className="card-header"><h3>{section.title}</h3></div>
            <div className="card-body settings-body">
              {section.fields.map(f => {
                const val = (config as any)[f.key];
                return (
                  <div key={f.key} className="settings-field">
                    <label className="settings-label">{f.label}</label>
                    {f.type === 'checkbox' ? (
                      <label className="toggle-label"><input type="checkbox" checked={!!val} onChange={e => updateField(f.key, e.target.checked)} /><span>{val ? 'On' : 'Off'}</span></label>
                    ) : f.type === 'select' ? (
                      <Select value={val || ''} onChange={v => updateField(f.key, v)} options={f.options || []} />
                    ) : f.type === 'range' ? (
                      <div className="range-field"><input type="range" min={f.min || 0} max={f.max || 1} step={0.01} value={val || 0} onChange={e => updateField(f.key, Number(e.target.value))} className="range-input" /><span className="range-value">{f.key.includes('threshold') || f.key.includes('confidence') ? `${(val * 100).toFixed(0)}%` : val}</span></div>
                    ) : (
                      <input type="number" value={val || 0} onChange={e => updateField(f.key, Number(e.target.value))} min={f.min} max={f.max} className="settings-input" />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="card"><AlertRulesComp rules={alerts} onUpdate={onUpdateAlerts} /></div>

      <div className="card">
        <div className="card-header"><h3>Provider Info</h3></div>
        <div className="card-body">
          {providerInfo ? (
            <div className="provider-grid">
              {Object.entries(providerInfo).map(([name, info]: [string, any]) => (
                <div key={name} className="provider-card">
                  <div className="provider-name">{name}</div>
                  <div className="provider-detail"><span>Provider:</span><span className="font-mono">{info.name}</span></div>
                  {info.model && <div className="provider-detail"><span>Model:</span><span className="font-mono">{info.model}</span></div>}
                </div>
              ))}
            </div>
          ) : <div className="empty-small">No provider info available</div>}
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h3>Extraction Prompt Editor</h3></div>
        <div className="card-body">
          <textarea value={customPrompt || 'Enter custom prompt to test re-extraction...'} onChange={e => setCustomPrompt(e.target.value)} rows={10} className="sim-input font-mono text-sm" />
          <div className="flex gap-2 mt-3"><button className="btn btn-primary" onClick={handleReExtract}>Test Re-extract</button></div>
          {reExtractResult && (
            <div className="mt-4"><span className="badge badge-assertion">Extracted {reExtractResult.count} beliefs</span><pre className="sim-code mt-2">{JSON.stringify(reExtractResult.extracted, null, 2).slice(0, 2000)}</pre></div>
          )}
        </div>
      </div>
    </div>
  );
}
