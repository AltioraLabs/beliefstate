import React from 'react';
import { Notification } from '../hooks/useNotifications';

interface Props {
  notifications: Notification[];
  unreadCount: number;
  onMarkRead: (id: string) => void;
  onMarkAllRead: () => void;
  onClear: () => void;
  onClose: () => void;
}

export function NotificationPanel({ notifications, unreadCount, onMarkRead, onMarkAllRead, onClear, onClose }: Props) {
  return (
    <div className="notif-panel-overlay" onClick={onClose}>
      <div className="notif-panel" onClick={e => e.stopPropagation()}>
        <div className="notif-panel-head">
          <span>Notifications {unreadCount > 0 && <span className="badge badge-primary">{unreadCount}</span>}</span>
          <div className="notif-panel-actions">
            {unreadCount > 0 && <button className="btn-ghost btn-xs" onClick={onMarkAllRead}>Mark all read</button>}
            <button className="btn-ghost btn-xs" onClick={onClear}>Clear</button>
            <button className="btn-ghost btn-xs" onClick={onClose}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <div className="notif-panel-body">
          {notifications.length === 0 ? (
            <div className="empty-small">No notifications yet</div>
          ) : (
            notifications.slice(0, 50).map(n => (
              <div key={n.id} className={`notif-item ${n.read ? '' : 'unread'}`} onClick={() => onMarkRead(n.id)}>
                <div className={`notif-dot ${n.type}`} />
                <div className="notif-content">
                  <div className="notif-title">{n.title}</div>
                  <div className="notif-msg">{n.message}</div>
                  <div className="notif-time">{new Date(n.timestamp).toLocaleString()}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
