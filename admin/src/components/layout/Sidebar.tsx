import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Calendar,
  Briefcase,
  Users,
  Target,
  Info,
  BarChart3,
  Building2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import logoIcon from "@/assets/logo-icon.jpeg";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/consultas", icon: Calendar, label: "Consultas" },
  { to: "/servicios", icon: Briefcase, label: "Servicios" },
  { to: "/consultores", icon: Users, label: "Consultores" },
  { to: "/leads", icon: Target, label: "Prospectos" },
  { to: "/informacion", icon: Info, label: "Información" },
  { to: "/estadisticas", icon: BarChart3, label: "Estadísticas" },
];

const superAdminItems = [
  { to: "/tenants", icon: Building2, label: "Tenants" },
];

export function Sidebar() {
  const { isSuperAdmin } = useAuth();

  const items = isSuperAdmin ? [...navItems, ...superAdminItems] : navItems;

  return (
    <aside className="hidden lg:flex lg:flex-col lg:w-60 lg:fixed lg:inset-y-0 bg-card border-r border-border">
      {/* Brand */}
      <div className="flex items-center h-14 px-5 border-b border-border gap-3">
        <img
          src={logoIcon}
          alt="AgencyBot"
          className="h-7 w-7 rounded-full object-cover shrink-0"
        />
        <div className="flex items-baseline">
          <span className="text-base font-bold tracking-tight text-foreground">
            AGENCYBOT
          </span>
          <span className="text-base font-light tracking-tight text-muted-foreground ml-1.5">
            AI
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-[13px] font-medium transition-all duration-150",
                isActive
                  ? "bg-white/10 text-foreground"
                  : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
