import { useRoutes, Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { routes } from "@/router";

export default function App() {
  const { isAuthenticated, loading } = useAuth();
  const element = useRoutes(routes);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  // If not authenticated and not on login page, redirect
  if (!isAuthenticated && window.location.pathname !== "/admin/login") {
    return <Navigate to="/login" replace />;
  }

  return element;
}
