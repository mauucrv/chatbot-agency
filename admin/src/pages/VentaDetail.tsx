import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2 } from "lucide-react";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Venta } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useState } from "react";

export default function VentaDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const [deleteOpen, setDeleteOpen] = useState(false);

  const { data: venta, isLoading } = useQuery<Venta>({
    queryKey: ["venta", id],
    queryFn: () => api.get(`/ventas/${id}`).then((r) => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/ventas/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ventas"] });
      navigate("/ventas");
    },
  });

  if (isLoading || !venta) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const tipoBadge: Record<string, string> = {
    producto: "bg-blue-100 text-blue-800",
    servicio: "bg-green-100 text-green-800",
    mixta: "bg-purple-100 text-purple-800",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/ventas")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Venta #{venta.id}</h1>
          <p className="text-muted-foreground">
            {format(parseISO(venta.created_at), "dd MMMM yyyy, HH:mm", { locale: es })}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${tipoBadge[venta.tipo] || ""}`}>
            {venta.tipo.charAt(0).toUpperCase() + venta.tipo.slice(1)}
          </span>
          {isAdmin && (
            <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}>
              <Trash2 className="h-4 w-4 mr-1" /> Eliminar
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-sm text-muted-foreground">Total</p>
            <p className="text-3xl font-bold mt-1">${venta.total.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-sm text-muted-foreground">Metodo de Pago</p>
            <p className="text-xl font-semibold mt-1 capitalize">{venta.metodo_pago}</p>
            {venta.vendedor && (
              <>
                <p className="text-sm text-muted-foreground mt-3">Vendedor</p>
                <p className="font-medium mt-1">{venta.vendedor}</p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-sm text-muted-foreground">Subtotal</p>
            <p className="font-semibold mt-1">${venta.subtotal.toLocaleString()}</p>
            {venta.descuento > 0 && (
              <>
                <p className="text-sm text-muted-foreground mt-2">Descuento</p>
                <p className="font-semibold mt-1 text-red-600">-${venta.descuento.toLocaleString()}</p>
              </>
            )}
            {venta.ficha_cliente_id && (
              <>
                <p className="text-sm text-muted-foreground mt-2">Cliente</p>
                <Button
                  variant="link"
                  className="p-0 h-auto"
                  onClick={() => navigate(`/clientes/${venta.ficha_cliente_id}`)}
                >
                  Ver ficha #{venta.ficha_cliente_id}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Line items */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Detalle de la Venta</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Descripcion</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead className="text-right">Cantidad</TableHead>
                <TableHead className="text-right">Precio Unit.</TableHead>
                <TableHead className="text-right">Subtotal</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {venta.detalles.map((det) => (
                <TableRow key={det.id}>
                  <TableCell className="font-medium">{det.descripcion}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {det.producto_id ? "Producto" : "Servicio"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">{det.cantidad}</TableCell>
                  <TableCell className="text-right">${det.precio_unitario.toLocaleString()}</TableCell>
                  <TableCell className="text-right font-medium">${det.subtotal.toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {venta.notas && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Notas</CardTitle></CardHeader>
          <CardContent>
            <p className="text-sm">{venta.notas}</p>
          </CardContent>
        </Card>
      )}

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Eliminar Venta"
        description="Esta accion eliminara la venta y revertira los movimientos de inventario. No se puede deshacer."
        onConfirm={() => deleteMutation.mutate()}
        confirmLabel="Eliminar"
        destructive
      />
    </div>
  );
}
