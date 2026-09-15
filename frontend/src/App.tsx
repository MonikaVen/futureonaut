import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useEffect } from "react";
import { useAuth } from "./auth";
import { Shell } from "./Shell";
import { LoginPage, RegisterPage } from "./pages/Auth";
import { CatalogPage } from "./pages/Catalog";
import { PlayPage } from "./pages/Play";
import { DashboardPage } from "./pages/Dashboard";
import { RecommendationsPage } from "./pages/Recommendations";
import { CreatorPage } from "./pages/Creator";
import { ClassroomPage } from "./pages/Classroom";
import { AdminPage } from "./pages/Admin";
import { applyTheme, useTheme } from "./theme";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireRole({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function ThemeSync() {
  const { theme } = useTheme();
  const location = useLocation();
  useEffect(() => {
    applyTheme(theme);
  }, [theme, location.pathname]);
  return null;
}

export default function App() {
  return (
    <>
      <ThemeSync />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<Shell />}>
          <Route path="/" element={<CatalogPage />} />
          <Route path="/play/:gameId" element={<PlayPage />} />
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <DashboardPage />
              </RequireAuth>
            }
          />
          <Route
            path="/recommendations"
            element={
              <RequireAuth>
                <RecommendationsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/classrooms"
            element={
              <RequireAuth>
                <ClassroomPage />
              </RequireAuth>
            }
          />
          <Route
            path="/creator"
            element={
              <RequireRole roles={["creator", "admin"]}>
                <CreatorPage />
              </RequireRole>
            }
          />
          <Route
            path="/admin"
            element={
              <RequireRole roles={["admin"]}>
                <AdminPage />
              </RequireRole>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
