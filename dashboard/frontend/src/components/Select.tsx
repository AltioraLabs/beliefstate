import React, { useState, useRef, useEffect, useCallback } from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
  width?: string | number;
  disabled?: boolean;
}

export function Select({ value, onChange, options, placeholder = 'Select...', className = '', width, disabled }: SelectProps) {
  const [open, setOpen] = useState(false);
  const [upward, setUpward] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const selected = options.find(o => o.value === value);
  const handleSelect = useCallback((val: string) => {
    onChange(val);
    setOpen(false);
  }, [onChange]);

  const handleToggle = useCallback(() => {
    if (disabled) return;
    if (!open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      setUpward(spaceBelow < 200);
    }
    setOpen(o => !o);
  }, [disabled, open]);

  return (
    <div className={`custom-select ${className}${upward && open ? ' upward' : ''}`} ref={ref} style={width ? { width: typeof width === 'number' ? width + 'px' : width } : undefined}>
      <button className="custom-select-trigger" onClick={handleToggle} disabled={disabled} ref={triggerRef} type="button">
        <span className={selected ? 'custom-select-value' : 'custom-select-placeholder'}>
          {selected ? selected.label : placeholder}
        </span>
        <svg className={`custom-select-chevron ${open ? 'open' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className={`custom-select-dropdown${upward ? ' upward' : ''}`}>
          {options.map(opt => (
            <button
              key={opt.value}
              className={`custom-select-option ${opt.value === value ? 'selected' : ''}`}
              onClick={() => handleSelect(opt.value)}
              type="button"
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
