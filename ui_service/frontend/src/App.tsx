import { Navigate, Route, Routes } from "react-router-dom";

import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import RecoveryPage from "./pages/RecoveryPage";

export default function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<RecoveryPage />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
