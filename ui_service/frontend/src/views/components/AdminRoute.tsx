import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { fetchCurrentUser } from "../../services/authService";

type AdminRouteProps = {
  children: JSX.Element;
};

export default function AdminRoute({ children }: AdminRouteProps): JSX.Element {
  const token: string | null = localStorage.getItem("access_token");
  const [checking, setChecking] = useState<boolean>(true);
  const [isAdmin, setIsAdmin] = useState<boolean>(false);

  useEffect(() => {
    if (!token) {
      setChecking(false);
      return;
    }

    async function checkAdmin(): Promise<void> {
      try {
        const user = await fetchCurrentUser();
        setIsAdmin(user.is_admin);
      } catch {
        setIsAdmin(false);
      } finally {
        setChecking(false);
      }
    }

    void checkAdmin();
  }, [token]);

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (checking) {
    return <div className="admin-page"><p className="admin-subtitle">Loading…</p></div>;
  }

  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}
