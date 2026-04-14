import { Navigate, type RouteObject } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Citas from "@/pages/Citas";
import CitaDetail from "@/pages/CitaDetail";
import Servicios from "@/pages/Servicios";
import Estilistas from "@/pages/Estilistas";
import EstilistaDetail from "@/pages/EstilistaDetail";
import Leads from "@/pages/Leads";
import LeadDetail from "@/pages/LeadDetail";
import Informacion from "@/pages/Informacion";
import Estadisticas from "@/pages/Estadisticas";
import Tenants from "@/pages/Tenants";
import TenantDetail from "@/pages/TenantDetail";

export const routes: RouteObject[] = [
  { path: "/login", element: <Login /> },
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "consultas", element: <Citas /> },
      { path: "consultas/:id", element: <CitaDetail /> },
      { path: "servicios", element: <Servicios /> },
      { path: "consultores", element: <Estilistas /> },
      { path: "consultores/:id", element: <EstilistaDetail /> },
      { path: "leads", element: <Leads /> },
      { path: "leads/:id", element: <LeadDetail /> },
      { path: "informacion", element: <Informacion /> },
      { path: "estadisticas", element: <Estadisticas /> },
      { path: "tenants", element: <Tenants /> },
      { path: "tenants/:id", element: <TenantDetail /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
];
