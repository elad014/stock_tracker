import { useCallback, useEffect, useState } from "react";

import type { Notification } from "../../models/notifications";
import {
  fetchUnreadNotifications,
  markNotificationRead,
} from "../../services/notificationService";

const POLL_INTERVAL_MS = 30_000;

export default function NotificationBanner(): JSX.Element | null {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const loadNotifications = useCallback(async (): Promise<void> => {
    try {
      const data = await fetchUnreadNotifications();
      setNotifications(data);
    } catch {
      // Silently ignore — the user is still authenticated; notification
      // failures should not affect the rest of the UI.
    }
  }, []);

  // Fetch on mount and then poll every 30 s
  useEffect(() => {
    void loadNotifications();
    const interval = setInterval(() => void loadNotifications(), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [loadNotifications]);

  async function dismiss(id: string): Promise<void> {
    // Optimistically remove from the list right away
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    try {
      await markNotificationRead(id);
    } catch {
      // If the API call fails the notification simply won't re-appear on the
      // next poll because we already removed it locally.
    }
  }

  if (notifications.length === 0) {
    return null;
  }

  return (
    <div className="notification-banner-stack" aria-live="polite">
      {notifications.map((n) => (
        <div key={n.id} className="notification-banner" role="alert">
          <span className="notification-banner-message">{n.message}</span>
          <button
            type="button"
            className="notification-banner-close"
            aria-label="Dismiss notification"
            onClick={() => void dismiss(n.id)}
          >
            &times;
          </button>
        </div>
      ))}
    </div>
  );
}
