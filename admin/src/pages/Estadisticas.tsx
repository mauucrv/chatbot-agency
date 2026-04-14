import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format, subDays } from "date-fns";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import api from "@/lib/api";
import type { StatsOverview, TrendPoint } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatCard } from "@/components/shared/StatCard";
import { CheckCircle, XCircle } from "lucide-react";

const COLORS = [
  "#2563EB",
  "#F97316",
  "#10B981",
  "#F59E0B",
  "#EF4444",
  "#8B5CF6",
  "#EC4899",
  "#06B6D4",
];

export default function Estadisticas() {
  const [fechaDesde, setFechaDesde] = useState(
    format(subDays(new Date(), 30), "yyyy-MM-dd")
  );
  const [fechaHasta, setFechaHasta] = useState(
    format(new Date(), "yyyy-MM-dd")
  );

  const { data: overview, isLoading: overviewLoading } = useQuery<StatsOverview>({
    queryKey: ["stats-overview", fechaDesde, fechaHasta],
    queryFn: () =>
      api
        .get("/estadisticas/overview", {
          params: {
            fecha_desde: `${fechaDesde}T00:00:00Z`,
            fecha_hasta: `${fechaHasta}T23:59:59Z`,
          },
        })
        .then((r) => r.data),
  });

  const { data: trend = [] } = useQuery<TrendPoint[]>({
    queryKey: ["appointment-trend"],
    queryFn: () =>
      api.get("/estadisticas/tendencia-citas", { params: { dias: 30 } }).then((r) => r.data),
  });

  const trendData = trend.map((t) => ({
    fecha: format(new Date(t.fecha), "dd/MM"),
    citas: t.valor,
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Estadisticas</h1>

      {/* Date range */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="space-y-1">
          <Label className="text-xs">Desde</Label>
          <Input
            type="date"
            value={fechaDesde}
            onChange={(e) => setFechaDesde(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Hasta</Label>
          <Input
            type="date"
            value={fechaHasta}
            onChange={(e) => setFechaHasta(e.target.value)}
            className="w-40"
          />
        </div>
      </div>

      {overviewLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      ) : overview ? (
        <>
          {/* Rates */}
          <div className="grid gap-4 md:grid-cols-2">
            <StatCard
              title="Tasa de Completadas"
              value={`${overview.tasa_completadas}%`}
              icon={CheckCircle}
            />
            <StatCard
              title="Tasa de Canceladas"
              value={`${overview.tasa_canceladas}%`}
              icon={XCircle}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Appointment Trend */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Tendencia de Citas (30 dias)</CardTitle>
              </CardHeader>
              <CardContent>
                {trendData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="fecha" fontSize={12} />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey="citas"
                        stroke="#2563EB"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-10">
                    No hay datos
                  </p>
                )}
              </CardContent>
            </Card>

            {/* By Status Pie */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Citas por Estado</CardTitle>
              </CardHeader>
              <CardContent>
                {overview.citas_por_estado.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={overview.citas_por_estado}
                        dataKey="cantidad"
                        nameKey="estado"
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        label={({ estado, cantidad }) => `${estado}: ${cantidad}`}
                      >
                        {overview.citas_por_estado.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-10">
                    No hay datos
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Popular Services */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Servicios Populares</CardTitle>
              </CardHeader>
              <CardContent>
                {overview.servicios_populares.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart
                      data={overview.servicios_populares}
                      layout="vertical"
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" allowDecimals={false} />
                      <YAxis
                        type="category"
                        dataKey="servicio"
                        width={120}
                        fontSize={12}
                      />
                      <Tooltip />
                      <Bar
                        dataKey="cantidad"
                        fill="#F97316"
                        radius={[0, 4, 4, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-10">
                    No hay datos
                  </p>
                )}
              </CardContent>
            </Card>

            {/* By Stylist */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Consultas por Consultor</CardTitle>
              </CardHeader>
              <CardContent>
                {overview.citas_por_estilista.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={overview.citas_por_estilista}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="estilista" fontSize={12} />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Bar
                        dataKey="cantidad"
                        fill="#10B981"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-10">
                    No hay datos
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Bot Stats Table */}
          {overview.daily_stats.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Estadisticas del Bot (diario)</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart
                    data={overview.daily_stats.map((d) => ({
                      fecha: format(new Date(d.fecha), "dd/MM"),
                      mensajes: d.mensajes_recibidos,
                      citas: d.citas_creadas,
                      errores: d.errores,
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="fecha" fontSize={12} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="mensajes" fill="#2563EB" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="citas" fill="#10B981" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="errores" fill="#EF4444" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
}
