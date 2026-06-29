import React from 'react';

interface Props {
  selectedCount: number;
  onDelete: () => void;
  onExport: () => void;
  onClear: () => void;
  loading?: boolean;
}

export function BulkActionsBar({ selectedCount, onDelete, onExport, onClear, loading }: Props) {
  if (selectedCount === 0) return null;
  return (
    <div className="bulk-bar">
      <span className="bulk-count">{selectedCount} selected</span>
      <button className="btn btn-secondary btn-sm" onClick={onExport} disabled={loading}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Export
      </button>
      <button className="btn btn-danger btn-sm" onClick={onDelete} disabled={loading}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        Delete
      </button>
      <button className="btn-ghost btn-sm" onClick={onClear}>Cancel</button>
    </div>
  );
}
