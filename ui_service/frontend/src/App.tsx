import { Navigate, Route, Routes, useParams } from "react-router-dom";

import AdminRoute from "./views/components/AdminRoute";
import ProtectedRoute from "./views/components/ProtectedRoute";
import AdminPage from "./views/pages/AdminPage";
import DashboardPage from "./views/pages/DashboardPage";
import HelpPage from "./views/pages/HelpPage";
import HomePage from "./views/pages/HomePage";
import LoginPage from "./views/pages/LoginPage";
import RegisterPage from "./views/pages/RegisterPage";
import RecoveryPage from "./views/pages/RecoveryPage";
import SettingsPage from "./views/pages/SettingsPage";
import StockDetailsPage from "./views/pages/StockDetailsPage";

function LegacyStockRedirect(): JSX.Element {
  const { stockId } = useParams<{ stockId: string }>();
  return <Navigate to={`/stock/${stockId ?? ""}`} replace />;
}

export default function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<RecoveryPage />} />
      <Route
        path="/admin"
        element={
          <AdminRoute>
            <AdminPage />
          </AdminRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stock/:stockId"
        element={
          <ProtectedRoute>
            <StockDetailsPage />
          </ProtectedRoute>
        }
      />
      <Route path="/stocks/:stockId" element={<LegacyStockRedirect />} />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
