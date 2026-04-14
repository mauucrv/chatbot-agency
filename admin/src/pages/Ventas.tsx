import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { format, parseISO, subDays } from "date-fns";
import { es } from "date-fns/locale";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PaginatedVentas } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const METODOS = [
  { value: "all", label: "Todos" },
  { value: "efectivo", label: "Efectivo" },
  { value: "tarjeta", label: "Tarjeta" },
  { value: "transferencia", label: "Transferencia" },
  { value: "otro", label: "Otro" },
];

const TIPOS = [
  { value: "all", label: "Todos" },
  { value: "producto", label: "Producto" },
  { value: "servicio", label: "Servicio" },
  { value: "mixta", label: "Mixta" },
];

const tipoBadgeColor: Record<string, string> = {
  producto: "bg-blue-100 text-blue-800",
  servicio: "bg-green-100 text-green-800",
  mixta: "bg-purple-100 text-purple-800",
};

export default function Ventas() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [page, setPage] = useState(1);
  const [tipo, setTipo] = useState("all");
  const [metodo, setMetodo] = useState("all");
  const [fechaDesde, setFechaDesde] = useState(format(subDays(new Date(), 30), "yyyy-MM-dd"));
  const [fechaHasta, setFechaHasta] = useState(format(new Date(), "yyyy-MM-dd"));

  const { data, isLoading } = useQuery<PaginatedVentas>({
    queryKey: ["ventas", page, tipo, metodo, fechaDesde, fechaHasta],
    queryFn: () => {
      const params: Record<string, string | number> = {
        page,
        page_size: 20,
        fecha_desde: `${fechaDesde}T00:00:00Z`,
        fecha_hasta: `${fechaHasta}T23:59:59Z`,
      };
      if (tipo !== "all") params.tipo = tipo;
      if (metodo !== "all") params.metodo_pago = metodo;
      return api.get("/ventas", { params }).then((r) => r.data);
    },
  });

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Ventas</h1>
        {isAdmin && (
          <Button onClick={() => navigate("/ventas/nueva")}>
            <Plus className="h-4 w-4 mr-2" /> Nueva Venta
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="space-y-1">
          <Label className="text-xs">Desde</Label>
          <Input
            type="date"
            value={fechaDesde}
            onChange={(e) => { setFechaDesde(e.target.value); setPage(1); }}
            className="w-40"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Hasta</Label>
          <Input
            type="date"
            value={fechaHasta}
            onChange={(e) => { setFechaHasta(e.target.value); setPage(1); }}
            className="w-40"
          />
        </div>
        <Select value={tipo} onValueChange={(v) => { setTipo(v); setPage(1); }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Tipo" />
          </SelectTrigger>
          <SelectContent>
            {TIPOS.map((t) => (
              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={metodo} onValueChange={(v) => { setMetodo(v); setPage(1); }}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Metodo" />
          </SelectTrigger>
          <SelectContent>
            {METODOS.map((m) => (
              <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Fecha</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Items</TableHead>
              <TableHead>Subtotal</TableHead>
              <TableHead>Descuento</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Pago</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto" />
                </TableCell>
              </TableRow>
            ) : (
              data?.items.map((venta) => (
                <TableRow
                  key={venta.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/ventas/${venta.id}`)}
                >
                  <TableCell className="font-mono text-sm">#{venta.id}</TableCell>
                  <TableCell>
                    {format(parseISO(venta.created_at), "dd MMM yyyy HH:mm", { locale: es })}
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${tipoBadgeColor[venta.tipo] || ""}`}>
                      {venta.tipo.charAt(0).toUpperCase() + venta.tipo.slice(1)}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm">
                    {venta.detalles.length} item{venta.detalles.length !== 1 ? "s" : ""}
                  </TableCell>
                  <TableCell>${venta.subtotal.toLocaleString()}</TableCell>
                  <TableCell>
                    {venta.descuento > 0 ? (
                      <span className="text-red-600">-${venta.descuento.toLocaleString()}</span>
                    ) : "-"}
                  </TableCell>
                  <TableCell className="font-medium">${venta.total.toLocaleString()}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">{venta.metodo_pago}</Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
            {!isLoading && data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                  No se encontraron ventas
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">{data?.total} ventas en total</p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm">Pagina {page} de {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
