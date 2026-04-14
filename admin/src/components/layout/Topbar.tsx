import { useState } from "react";
import { useNavigate, NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Calendar,
  Briefcase,
  Users,
  Target,
  Info,
  BarChart3,
  Building2,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
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

export function Topbar() {
  const { username, rol, logout, isSuperAdmin } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const items = isSuperAdmin ? [...navItems, ...superAdminItems] : navItems;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const rolLabel = rol === "superadmin" ? "Super Admin" : rol === "admin" ? "Admin" : rol;

  return (
    <>
      <header className="sticky top-0 z-40 flex h-12 items-center border-b border-border bg-background px-4 lg:px-6">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden mr-2 text-muted-foreground hover:text-foreground"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>

        <div className="flex-1" />

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground hidden sm:inline">
              {username}
            </span>
            {rol && (
              <span className="text-[10px] font-medium uppercase tracking-wider bg-white/10 text-muted-foreground px-1.5 py-0.5 rounded hidden sm:inline">
                {rolLabel}
              </span>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            className="text-muted-foreground hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {/* Mobile nav */}
      {mobileOpen && (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div
            className="fixed inset-0 bg-background/80 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 w-64 bg-card border-r border-border p-4 pt-16">
            <div className="flex items-center gap-3 px-3 mb-4">
              <img
                src={logoIcon}
                alt="AgencyBot"
                className="h-7 w-7 rounded-full object-cover shrink-0"
              />
              <div className="flex items-baseline">
                <span className="text-base font-bold tracking-tight text-foreground">AGENCYBOT</span>
                <span className="text-base font-light tracking-tight text-muted-foreground ml-1.5">AI</span>
              </div>
            </div>
            <nav className="space-y-1">
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all duration-150",
                      isActive
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )
                  }
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      )}
    </>
  );
}
