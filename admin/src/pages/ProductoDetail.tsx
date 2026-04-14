import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, ArrowUpCircle, ArrowDownCircle, Settings2 } from "lucide-react";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Producto, PaginatedMovimientos } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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

const TIPO_ICONS: Record<string, typeof ArrowUpCircle> = {
  entrada: ArrowUpCircle,
  salida: ArrowDownCircle,
  ajuste: Settings2,
};

const TIPO_COLORS: Record<string, string> = {
  entrada: "text-green-600",
  salida: "text-red-600",
  ajuste: "text-blue-600",
};

export default function ProductoDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const [movDialogOpen, setMovDialogOpen] = useState(false);
  const [movForm, setMovForm] = useState({ tipo: "entrada", cantidad: 1, motivo: "" });
  const [movPage, setMovPage] = useState(1);

  const { data: producto, isLoading } = useQuery<Producto>({
    queryKey: ["producto", id],
    queryFn: () => api.get(`/inventario/${id}`).then((r) => r.data),
  });

  const { data: movimientos } = useQuery<PaginatedMovimientos>({
    queryKey: ["movimientos", id, movPage],
    queryFn: () =>
      api.get(`/inventario/${id}/movimientos`, { params: { page: movPage, page_size: 15 } }).then((r) => r.data),
  });

  const movMutation = useMutation({
    mutationFn: (body: typeof movForm) => api.post(`/inventario/${id}/movimientos`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["producto", id] });
      qc.invalidateQueries({ queryKey: ["movimientos", id] });
      setMovDialogOpen(false);
      setMovForm({ tipo: "entrada", cantidad: 1, motivo: "" });
    },
  });

  if (isLoading || !producto) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const stockStatus = producto.cantidad <= 0
    ? "destructive"
    : producto.cantidad <= producto.stock_minimo
    ? "warning"
    : "ok";

  const movTotalPages = movimientos ? Math.ceil(movimientos.total / movimientos.page_size) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/inventario")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{producto.nombre}</h1>
          <p className="text-muted-foreground">
            {producto.marca && `${producto.marca} · `}
            {producto.categoria === "reventa" ? "Reventa" : "Uso del Salon"}
          </p>
        </div>
        {isAdmin && (
          <Button className="ml-auto" onClick={() => setMovDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" /> Registrar Movimiento
          </Button>
        )}
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-sm text-muted-foreground">Stock Actual</p>
            <p className={`text-4xl font-bold mt-1 ${
              stockStatus === "destructive" ? "text-red-600" :
              stockStatus === "warning" ? "text-amber-500" : ""
            }`}>
              {producto.cantidad}
            </p>
            <p className="text-sm text-muted-foreground">{producto.unidad}</p>
            {stockStatus !== "ok" && (
              <Badge variant={stockStatus === "destructive" ? "destructive" : "secondary"} className="mt-2">
                {stockStatus === "destructive" ? "Agotado" : "Stock Bajo"}
              </Badge>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-sm text-muted-foreground">Costo Unitario</p>
            <p className="text-2xl font-bold mt-1">${producto.costo_unitario.toLocaleString()}</p>
            {producto.precio_venta && (
              <>
                <p className="text-sm text-muted-foreground mt-3">Precio de Venta</p>
                <p className="text-2xl font-bold mt-1">${producto.precio_venta.toLocaleString()}</p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-sm text-muted-foreground">Stock Minimo</p>
            <p className="text-xl font-bold mt-1">{producto.stock_minimo} {producto.unidad}</p>
            {producto.fecha_vencimiento && (
              <>
                <p className="text-sm text-muted-foreground mt-3">Vencimiento</p>
                <p className="text-xl font-bold mt-1">
                  {format(parseISO(producto.fecha_vencimiento), "dd MMM yyyy", { locale: es })}
                </p>
              </>
            )}
            {producto.codigo_barras && (
              <>
                <p className="text-sm text-muted-foreground mt-3">Codigo de Barras</p>
                <p className="text-sm font-mono mt-1">{producto.codigo_barras}</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Movements table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Historial de Movimientos</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fecha</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Cantidad</TableHead>
                <TableHead>Anterior</TableHead>
                <TableHead>Nuevo</TableHead>
                <TableHead>Motivo</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {movimientos?.items.map((mov) => {
                const Icon = TIPO_ICONS[mov.tipo] || Settings2;
                return (
                  <TableRow key={mov.id}>
                    <TableCell>
                      {format(parseISO(mov.created_at), "dd MMM yyyy HH:mm", { locale: es })}
                    </TableCell>
                    <TableCell>
                      <div className={`flex items-center gap-1 ${TIPO_COLORS[mov.tipo] || ""}`}>
                        <Icon className="h-4 w-4" />
                        <span className="capitalize">{mov.tipo}</span>
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">{mov.cantidad}</TableCell>
                    <TableCell>{mov.cantidad_anterior}</TableCell>
                    <TableCell className="font-medium">{mov.cantidad_nueva}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {mov.motivo || "-"}
                      {mov.referencia && <span className="ml-1 text-xs">({mov.referencia})</span>}
                    </TableCell>
                  </TableRow>
                );
              })}
              {(!movimientos || movimientos.items.length === 0) && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    Sin movimientos registrados
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          {movTotalPages > 1 && (
            <div className="flex items-center justify-end gap-2 mt-4">
              <Button variant="outline" size="sm" disabled={movPage <= 1} onClick={() => setMovPage(movPage - 1)}>
                Anterior
              </Button>
              <span className="text-sm">Pagina {movPage} de {movTotalPages}</span>
              <Button variant="outline" size="sm" disabled={movPage >= movTotalPages} onClick={() => setMovPage(movPage + 1)}>
                Siguiente
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Register Movement Dialog */}
      <Dialog open={movDialogOpen} onOpenChange={setMovDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Registrar Movimiento</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Tipo de Movimiento</Label>
              <Select value={movForm.tipo} onValueChange={(v) => setMovForm({ ...movForm, tipo: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="entrada">Entrada (agregar stock)</SelectItem>
                  <SelectItem value="salida">Salida (retirar stock)</SelectItem>
                  <SelectItem value="ajuste">Ajuste (establecer cantidad)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Cantidad</Label>
              <Input
                type="number"
                min={1}
                value={movForm.cantidad}
                onChange={(e) => setMovForm({ ...movForm, cantidad: parseInt(e.target.value) || 1 })}
              />
              {movForm.tipo === "salida" && producto.cantidad < movForm.cantidad && (
                <p className="text-sm text-destructive">Stock insuficiente (disponible: {producto.cantidad})</p>
              )}
            </div>
            <div className="space-y-2">
              <Label>Motivo</Label>
              <Input
                value={movForm.motivo}
                onChange={(e) => setMovForm({ ...movForm, motivo: e.target.value })}
                placeholder="Ej: Compra a proveedor, Uso interno..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMovDialogOpen(false)}>Cancelar</Button>
            <Button
              onClick={() => movMutation.mutate(movForm)}
              disabled={movMutation.isPending || movForm.cantidad < 1}
            >
              {movMutation.isPending ? "Registrando..." : "Registrar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
