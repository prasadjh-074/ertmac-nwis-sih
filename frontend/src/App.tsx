import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { RequirePermission } from "@/auth/RoleGuard";
import { homePathFor } from "@/auth/permissions";
import EngineerDashboard from "@/pages/EngineerDashboard";
import AdminDashboard from "@/pages/AdminDashboard";
import LoginPage from "@/pages/LoginPage";
import UnauthorizedPage from "@/pages/UnauthorizedPage";

function StartRoute() {
  const { user } = useAuth();
  return <Navigate to={user ? homePathFor(user.role) : "/login"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<StartRoute />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        <Route path="/engineer/*" element={<RequirePermission permission="VIEW_WELLS"><EngineerDashboard /></RequirePermission>} />
        <Route path="/admin/*" element={<RequirePermission permission="VIEW_SYSTEM_HEALTH"><AdminDashboard /></RequirePermission>} />
        <Route path="*" element={<StartRoute />} />
      </Routes>
    </AuthProvider>
  );
}
