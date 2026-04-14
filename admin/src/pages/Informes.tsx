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
import { Download, DollarSign, ShoppingCart, TrendingUp, Package, AlertTriangle, Users, UserCheck } from "lucide-react";
import api from "@/lib/api";
import type {
  InformeVentas,
  InformeInventario,
  InformeClientes,
  InformeEstilistas,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/shared/StatCard";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

const COLORS = ["#2563EB", "#F97316", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#06B6D4"];

function downloadCSV(url: string, filename: string) {
  const token = localStorage.getItem("access_token");
  fetch(`/api/admin${url}`, { headers: { Authorization: `Bearer ${token}` } })
    .then((res) => res.blob())
    .then((blob) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    });
}

type TabKey = "ventas" | "inventario" | "clientes" | "estilistas";

export default function Informes() {
  const [activeTab, setActiveTab] = useState<TabKey>("ventas");
  const [fechaDesde, setFechaDesde] = useState(format(subDays(new Date(), 30), "yyyy-MM-dd"));
  const [fechaHasta, setFechaHasta] = useState(format(new Date(), "yyyy-MM-dd"));

  const dateParams = {
    fecha_desde: `${fechaDesde}T00:00:00Z`,
    fecha_hasta: `${fechaHasta}T23:59:59Z`,
  };

  const { data: ventas, isLoading: ventasLoading } = useQuery<InformeVentas>({
    queryKey: ["informe-ventas", fechaDesde, fechaHasta],
    queryFn: () => api.get("/informes/ventas", { params: dateParams }).then((r) => r.data),
    enabled: activeTab === "ventas",
  });

  const { data: inventario, isLoading: invLoading } = useQuery<InformeInventario>({
    queryKey: ["informe-inventario"],
    queryFn: () => api.get("/informes/inventario").then((r) => r.data),
    enabled: activeTab === "inventario",
  });

  const { data: clientes, isLoading: clientesLoading } = useQuery<InformeClientes>({
    queryKey: ["informe-clientes", fechaDesde, fechaHasta],
    queryFn: () => api.get("/informes/clientes", { params: dateParams }).then((r) => r.data),
    enabled: activeTab === "clientes",
  });

  const { data: estilistas, isLoading: estLoading } = useQuery<InformeEstilistas>({
    queryKey: ["informe-estilistas", fechaDesde, fechaHasta],
    queryFn: () => api.get("/informes/estilistas", { params: dateParams }).then((r) => r.data),
    enabled: activeTab === "estilistas",
  });

  const tabs: { key: TabKey; label: string }[] = [
    { key: "ventas", label: "Ventas" },
    { key: "inventario", label: "Inventario" },
    { key: "clientes", label: "Clientes" },
    { key: "estilistas", label: "Estilistas" },
  ];

  const isLoading =
    (activeTab === "ventas" && ventasLoading) ||
    (activeTab === "inventario" && invLoading) ||
    (activeTab === "clientes" && clientesLoading) ||
    (activeTab === "estilistas" && estLoading);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Informes</h1>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Date range (used by ventas, clientes, estilistas) */}
      {activeTab !== "inventario" && (
        <div className="flex flex-wrap gap-3 items-end">
          <div className="space-y-1">
            <Label className="text-xs">Desde</Label>
            <Input type="date" value={fechaDesde} onChange={(e) => setFechaDesde(e.target.value)} className="w-40" />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Hasta</Label>
            <Input type="date" value={fechaHasta} onChange={(e) => setFechaHasta(e.target.value)} className="w-40" />
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      ) : (
        <>
          {/* ── Ventas Tab ────────────────────────────── */}
          {activeTab === "ventas" && ventas && (
            <div className="space-y-6">
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    downloadCSV(
                      `/informes/ventas/exportar?fecha_desde=${dateParams.fecha_desde}&fecha_hasta=${dateParams.fecha_hasta}`,
                      "ventas.csv"
                    )
                  }
                >
                  <Download className="h-4 w-4 mr-1" /> Exportar CSV
                </Button>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <StatCard title="Total Ingresos" value={`$${ventas.total_ingresos.toLocaleString()}`} icon={DollarSign} />
                <StatCard title="Total Ventas" value={ventas.total_ventas} icon={ShoppingCart} />
                <StatCard title="Ticket Promedio" value={`$${ventas.ticket_promedio.toLocaleString()}`} icon={TrendingUp} />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader><CardTitle className="text-lg">Ingresos por Dia</CardTitle></CardHeader>
                  <CardContent>
                    {ventas.ventas_por_dia.length > 0 ? (
                      <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={ventas.ventas_por_dia.map((d) => ({
                          fecha: format(new Date(d.fecha), "dd/MM"),
                          total: d.total,
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="fecha" fontSize={12} />
                          <YAxis />
                          <Tooltip formatter={(v: number) => [`$${v.toLocaleString()}`, "Ingresos"]} />
                          <Line type="monotone" dataKey="total" stroke="#2563EB" strokeWidth={2} dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : <p className="text-center text-muted-foreground py-10">No hay datos</p>}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle className="text-lg">Por Metodo de Pago</CardTitle></CardHeader>
                  <CardContent>
                    {ventas.ventas_por_metodo_pago.length > 0 ? (
                      <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                          <Pie
                            data={ventas.ventas_por_metodo_pago}
                            dataKey="total"
                            nameKey="metodo"
                            cx="50%"
                            cy="50%"
                            outerRadius={80}
                            label={({ metodo, total }) => `${metodo}: $${total.toLocaleString()}`}
                          >
                            {ventas.ventas_por_metodo_pago.map((_, i) => (
                              <Cell key={i} fill={COLORS[i % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : <p className="text-center text-muted-foreground py-10">No hay datos</p>}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle className="text-lg">Productos Mas Vendidos</CardTitle></CardHeader>
                  <CardContent>
                    {ventas.productos_mas_vendidos.length > 0 ? (
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={ventas.productos_mas_vendidos} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" />
                          <YAxis type="category" dataKey="nombre" width={120} fontSize={12} />
                          <Tooltip />
                          <Bar dataKey="cantidad" fill="#F97316" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : <p className="text-center text-muted-foreground py-10">No hay datos</p>}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle className="text-lg">Servicios Mas Vendidos</CardTitle></CardHeader>
                  <CardContent>
                    {ventas.servicios_mas_vendidos.length > 0 ? (
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={ventas.servicios_mas_vendidos} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" />
                          <YAxis type="category" dataKey="nombre" width={120} fontSize={12} />
                          <Tooltip />
                          <Bar dataKey="cantidad" fill="#10B981" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : <p className="text-center text-muted-foreground py-10">No hay datos</p>}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* ── Inventario Tab ───────────────────────── */}
          {activeTab === "inventario" && inventario && (
            <div className="space-y-6">
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => downloadCSV("/informes/inventario/exportar", "inventario.csv")}
                >
                  <Download className="h-4 w-4 mr-1" /> Exportar CSV
                </Button>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <StatCard
                  title="Valor Total de Stock"
                  value={`$${inventario.valor_total_stock.toLocaleString()}`}
                  icon={DollarSign}
                />
                <StatCard title="Total Productos" value={inventario.total_productos} icon={Package} />
                <StatCard
                  title="Productos Bajo Stock"
                  value={inventario.productos_bajo_stock.length}
                  icon={AlertTriangle}
                />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader><CardTitle className="text-lg">Productos con Stock Bajo</CardTitle></CardHeader>
                  <CardContent>
                    {inventario.productos_bajo_stock.length > 0 ? (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Producto</TableHead>
                            <TableHead className="text-right">Actual</TableHead>
                            <TableHead className="text-right">Minimo</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {inventario.productos_bajo_stock.map((p) => (
                            <TableRow key={p.id}>
                              <TableCell className="font-medium">{p.nombre}</TableCell>
                              <TableCell className="text-right">
                                <Badge variant={p.cantidad <= 0 ? "destructive" : "secondary"}>
                                  {p.cantidad}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-right">{p.stock_minimo}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    ) : <p className="text-center text-muted-foreground py-8">Todos los productos tienen stock suficiente</p>}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle className="text-lg">Proximos a Vencer</CardTitle></CardHeader>
                  <CardContent>
                    {inventario.productos_por_vencer.length > 0 ? (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Producto</TableHead>
                            <TableHead>Vencimiento</TableHead>
                            <TableHead className="text-right">Cantidad</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {inventario.productos_por_vencer.map((p) => (
                            <TableRow key={p.id}>
                              <TableCell className="font-medium">{p.nombre}</TableCell>
                              <TableCell>
                                <Badge variant="destructive">
                                  {format(new Date(p.fecha_vencimiento), "dd MMM yyyy")}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-right">{p.cantidad}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    ) : <p className="text-center text-muted-foreground py-8">No hay productos proximos a vencer</p>}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader><CardTitle className="text-lg">Movimientos Recientes</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Fecha</TableHead>
                        <TableHead>Producto</TableHead>
                        <TableHead>Tipo</TableHead>
                        <TableHead className="text-right">Cantidad</TableHead>
                        <TableHead>Motivo</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {inventario.movimientos_recientes.map((m, i) => (
                        <TableRow key={i}>
                          <TableCell>{format(new Date(m.fecha), "dd/MM HH:mm")}</TableCell>
                          <TableCell className="font-medium">{m.producto}</TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className={
                                m.tipo === "entrada" ? "text-green-600 border-green-300" :
                                m.tipo === "salida" ? "text-red-600 border-red-300" :
                                "text-blue-600 border-blue-300"
                              }
                            >
                              {m.tipo}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">{m.cantidad}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">{m.motivo || "-"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ── Clientes Tab ─────────────────────────── */}
          {activeTab === "clientes" && clientes && (
            <div className="space-y-6">
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => downloadCSV("/informes/clientes/exportar", "clientes.csv")}
                >
                  <Download className="h-4 w-4 mr-1" /> Exportar CSV
                </Button>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <StatCard title="Total Clientes" value={clientes.total_clientes} icon={Users} />
                <StatCard title="Nuevos en Periodo" value={clientes.clientes_nuevos_periodo} icon={UserCheck} />
                <StatCard title="Recurrentes" value={clientes.clientes_recurrentes} icon={TrendingUp} />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader><CardTitle className="text-lg">Frecuencia de Visitas</CardTitle></CardHeader>
                  <CardContent>
                    {clientes.frecuencia_visitas.length > 0 ? (
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={clientes.frecuencia_visitas}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="rango" fontSize={12} />
                          <YAxis allowDecimals={false} />
                          <Tooltip />
                          <Bar dataKey="cantidad" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : <p className="text-center text-muted-foreground py-10">No hay datos</p>}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle className="text-lg">Top Clientes por Gasto</CardTitle></CardHeader>
                  <CardContent>
                    {clientes.top_clientes.length > 0 ? (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Cliente</TableHead>
                            <TableHead className="text-right">Ventas</TableHead>
                            <TableHead className="text-right">Total</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {clientes.top_clientes.map((c, i) => (
                            <TableRow key={i}>
                              <TableCell>
                                <div className="font-medium">{c.nombre}</div>
                                <div className="text-xs text-muted-foreground">{c.telefono}</div>
                              </TableCell>
                              <TableCell className="text-right">{c.total_ventas}</TableCell>
                              <TableCell className="text-right font-medium">${c.total_gastado.toLocaleString()}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    ) : <p className="text-center text-muted-foreground py-8">No hay datos</p>}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* ── Estilistas Tab ───────────────────────── */}
          {activeTab === "estilistas" && estilistas && (
            <div className="space-y-6">
              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader><CardTitle className="text-lg">Rendimiento de Estilistas</CardTitle></CardHeader>
                  <CardContent>
                    {estilistas.rendimiento.length > 0 ? (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Estilista</TableHead>
                            <TableHead className="text-right">Citas</TableHead>
                            <TableHead className="text-right">Completadas</TableHead>
                            <TableHead className="text-right">Ingresos</TableHead>
                            <TableHead className="text-right">% Cancel.</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {estilistas.rendimiento.map((e, i) => (
                            <TableRow key={i}>
                              <TableCell className="font-medium">{e.nombre}</TableCell>
                              <TableCell className="text-right">{e.citas_totales}</TableCell>
                              <TableCell className="text-right">{e.completadas}</TableCell>
                              <TableCell className="text-right">${e.ingresos.toLocaleString()}</TableCell>
                              <TableCell className="text-right">
                                <Badge variant={e.tasa_cancelacion > 20 ? "destructive" : "secondary"}>
                                  {e.tasa_cancelacion}%
                                </Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    ) : <p className="text-center text-muted-foreground py-8">No hay datos</p>}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle className="text-lg">Ingresos por Estilista</CardTitle></CardHeader>
                  <CardContent>
                    {estilistas.rendimiento.length > 0 ? (
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={estilistas.rendimiento}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="nombre" fontSize={12} />
                          <YAxis />
                          <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                          <Legend />
                          <Bar dataKey="ingresos" name="Ingresos" fill="#10B981" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : <p className="text-center text-muted-foreground py-10">No hay datos</p>}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
