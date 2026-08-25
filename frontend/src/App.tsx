import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./auth";
import { Shell } from "./Shell";
import { LoginPage, RegisterPage } from "./pages/Auth";
import { CatalogPage } from "./pages/Catalog";
import { PlayPage } from "./pages/Play";
import { DashboardPage } from "./pages/Dashboard";
import { RecommendationsPage } from "./pages/Recommendations";
import { CreatorPage } from "./pages/Creator";
import { AdminPage } from "./pages/Admin";

function RequireRole({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<Shell />}>
        <Route path="/" element={<CatalogPage />} />
        <Route path="/play/:gameId" element={<PlayPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/recommendations" element={<RecommendationsPage />} />
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
  );
}
