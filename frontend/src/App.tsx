import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/auth/AuthContext";
import EngineerDashboard from "@/pages/EngineerDashboard";
import AdminDashboard from "@/pages/AdminDashboard";
import LoginPage from "@/pages/LoginPage";
import UnauthorizedPage from "@/pages/UnauthorizedPage";
import type { Role } from "@/auth/permissions";

function RequireAuth({ role }: { role?: Role }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (role && user.role !== role) return <UnauthorizedPage />;
  return <Outlet />;
}

function StartRoute() {
  const { user } = useAuth();
  return <Navigate to={user?.role === "SYSTEM_ADMIN" ? "/admin" : user ? "/engineer" : "/login"} replace />;
}

export default function App() {
  return <AuthProvider><Routes>
    <Route path="/" element={<StartRoute />} />
    <Route path="/login" element={<LoginPage />} />
    <Route element={<RequireAuth role="DRILLING_ENGINEER" />}><Route path="/engineer/*" element={<EngineerDashboard />} /></Route>
    <Route element={<RequireAuth role="SYSTEM_ADMIN" />}><Route path="/admin/*" element={<AdminDashboard />} /></Route>
    <Route path="*" element={<StartRoute />} />
  </Routes></AuthProvider>;
}
