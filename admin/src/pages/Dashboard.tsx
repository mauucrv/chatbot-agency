import { useQuery } from "@tanstack/react-query";
import {
  Calendar,
  Clock,
  MessageSquare,
  Briefcase,
  Users,
  AlertTriangle,
  CheckCircle,
  Target,
  UserPlus,
  Bell,
  Cpu,
  Mic,
  Image,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import api from "@/lib/api";
import type { DashboardMetrics } from "@/lib/types";
import { StatCard } from "@/components/shared/StatCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";

export default function Dashboard() {
  const { data, isLoading } = useQuery<DashboardMetrics>({
    queryKey: ["dashboard"],
    queryFn: () => api.get("/dashboard").then((r) => r.data),
    refetchInterval: 60_000,
  });

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const chartData = data.citas_semana.map((d) => ({
    fecha: format(parseISO(d.fecha), "EEE", { locale: es }),
    cantidad: d.cantidad,
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Consultas Hoy" value={data.citas_hoy} icon={Calendar} />
        <StatCard title="Pendientes" value={data.citas_pendientes} icon={Clock} />
        <StatCard
          title="Completadas Hoy"
          value={data.citas_completadas_hoy}
          icon={CheckCircle}
        />
        <StatCard title="Mensajes Hoy" value={data.mensajes_hoy} icon={MessageSquare} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Prospectos Activos" value={data.total_leads} icon={Target} />
        <StatCard title="Nuevos Hoy" value={data.leads_nuevos_hoy} icon={UserPlus} />
        <StatCard title="En Pipeline" value={data.leads_en_pipeline} icon={Users} />
        <StatCard
          title="Seguimientos Pend."
          value={data.seguimientos_pendientes}
          icon={Bell}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Servicios Activos" value={data.total_servicios} icon={Briefcase} />
        <StatCard title="Consultores Activos" value={data.total_estilistas} icon={Users} />
        <StatCard title="Errores Hoy" value={data.errores_hoy} icon={AlertTriangle} />
      </div>

      {/* Monthly usage */}
      {data.uso && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Uso del mes</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
            <StatCard
              title="Mensajes"
              value={data.uso.mensajes_mes.toLocaleString()}
              icon={MessageSquare}
              description="este mes"
            />
            <StatCard
              title="Tokens OpenAI"
              value={data.uso.tokens_openai_mes.toLocaleString()}
              icon={Cpu}
              description="este mes"
            />
            <StatCard
              title="Audio"
              value={data.uso.mensajes_audio_mes}
              icon={Mic}
              description="mensajes de voz"
            />
            <StatCard
              title="Imágenes"
              value={data.uso.mensajes_imagen_mes}
              icon={Image}
              description="imágenes recibidas"
            />
            <StatCard
              title="Usuarios Hoy"
              value={data.uso.usuarios_unicos_hoy}
              icon={Users}
              description="únicos"
            />
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Consultas esta Semana</CardTitle>
          </CardHeader>
          <CardContent>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="fecha" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="cantidad" fill="hsl(221, 83%, 53%)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-10">
                No hay datos esta semana
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Consultas Recientes</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Prospecto</TableHead>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.citas_recientes.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.nombre_cliente}</TableCell>
                    <TableCell>
                      {format(parseISO(c.inicio), "dd MMM HH:mm", { locale: es })}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={c.estado} />
                    </TableCell>
                  </TableRow>
                ))}
                {data.citas_recientes.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-muted-foreground">
                      No hay consultas recientes
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
