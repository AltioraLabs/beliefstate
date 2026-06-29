import React from 'react';

interface Props {
  onClose: () => void;
}

const SHORTCUTS = [
  { keys: ['g', 'o'], desc: 'Go to Overview' },
  { keys: ['g', 'b'], desc: 'Go to Beliefs' },
  { keys: ['g', 't'], desc: 'Go to Timeline' },
  { keys: ['g', 'c'], desc: 'Go to Conflicts' },
  { keys: ['g', 'a'], desc: 'Go to Activity' },
  { keys: ['g', 'r'], desc: 'Go to Compare Sessions' },
  { keys: ['g', 's'], desc: 'Go to Simulator' },
  { keys: ['g', 'i'], desc: 'Go to Settings' },
  { keys: ['/'], desc: 'Open search' },
  { keys: ['?'], desc: 'Show shortcuts' },
];

export function KeyboardShortcuts({ onClose }: Props) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 480 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <span className="modal-title">Keyboard Shortcuts</span>
          </div>
          <button className="modal-close" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div className="modal-body">
          <div className="shortcuts-list">
            {SHORTCUTS.map(s => (
              <div key={s.keys.join('')} className="shortcut-row">
                <span className="shortcut-desc">{s.desc}</span>
                <span className="shortcut-keys">
                  {s.keys.map((k, i) => (
                    <React.Fragment key={i}>
                      {i > 0 && <span className="shortcut-plus">then</span>}
                      <kbd className="shortcut-kbd">{k === ' ' ? 'Space' : k}</kbd>
                    </React.Fragment>
                  ))}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
