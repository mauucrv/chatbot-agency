import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, Trash2, Search } from "lucide-react";
import api from "@/lib/api";
import type { PaginatedFichas, PaginatedProductos, Service } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

interface LineItem {
  producto_id: number | null;
  descripcion: string;
  cantidad: number;
  precio_unitario: number;
}

export default function NuevaVenta() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [items, setItems] = useState<LineItem[]>([]);
  const [descuento, setDescuento] = useState(0);
  const [metodoPago, setMetodoPago] = useState("efectivo");
  const [vendedor, setVendedor] = useState("");
  const [notas, setNotas] = useState("");
  const [clienteId, setClienteId] = useState<number | null>(null);
  const [clienteNombre, setClienteNombre] = useState("");

  // Add product dialog
  const [prodDialogOpen, setProdDialogOpen] = useState(false);
  const [prodSearch, setProdSearch] = useState("");

  // Add service dialog
  const [svcDialogOpen, setSvcDialogOpen] = useState(false);

  // Client search dialog
  const [clientDialogOpen, setClientDialogOpen] = useState(false);
  const [clientSearch, setClientSearch] = useState("");

  const { data: productos } = useQuery<PaginatedProductos>({
    queryKey: ["productos-venta", prodSearch],
    queryFn: () => api.get("/inventario", { params: { busqueda: prodSearch, page_size: 50 } }).then((r) => r.data),
    enabled: prodDialogOpen,
  });

  const { data: servicios = [] } = useQuery<Service[]>({
    queryKey: ["services-venta"],
    queryFn: () => api.get("/servicios").then((r) => r.data),
    enabled: svcDialogOpen,
  });

  const { data: clientes } = useQuery<PaginatedFichas>({
    queryKey: ["clientes-venta", clientSearch],
    queryFn: () => api.get("/fichas", { params: { busqueda: clientSearch, page_size: 20 } }).then((r) => r.data),
    enabled: clientDialogOpen,
  });

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post("/ventas", body),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["ventas"] });
      navigate(`/ventas/${res.data.id}`);
    },
  });

  const addProduct = (prod: { id: number; nombre: string; precio_venta: number | null; costo_unitario: number }) => {
    setItems([
      ...items,
      {
        producto_id: prod.id,
        descripcion: prod.nombre,
        cantidad: 1,
        precio_unitario: prod.precio_venta || prod.costo_unitario,
      },
    ]);
    setProdDialogOpen(false);
  };

  const addService = (svc: { servicio: string; precio: number }) => {
    setItems([
      ...items,
      {
        producto_id: null,
        descripcion: svc.servicio,
        cantidad: 1,
        precio_unitario: svc.precio,
      },
    ]);
    setSvcDialogOpen(false);
  };

  const removeItem = (index: number) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const updateItem = (index: number, field: "cantidad" | "precio_unitario", value: number) => {
    const updated = [...items];
    updated[index] = { ...updated[index], [field]: value };
    setItems(updated);
  };

  const subtotal = items.reduce((sum, item) => sum + item.cantidad * item.precio_unitario, 0);
  const total = subtotal - descuento;

  const handleSubmit = () => {
    createMutation.mutate({
      ficha_cliente_id: clienteId,
      detalles: items.map((item) => ({
        producto_id: item.producto_id,
        descripcion: item.descripcion,
        cantidad: item.cantidad,
        precio_unitario: item.precio_unitario,
      })),
      descuento,
      metodo_pago: metodoPago,
      notas: notas || undefined,
      vendedor: vendedor || undefined,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/ventas")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-2xl font-bold">Nueva Venta</h1>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left: Line items */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-lg">Items</CardTitle>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setProdDialogOpen(true)}>
                  <Plus className="h-4 w-4 mr-1" /> Producto
                </Button>
                <Button size="sm" variant="outline" onClick={() => setSvcDialogOpen(true)}>
                  <Plus className="h-4 w-4 mr-1" /> Servicio
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {items.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Descripcion</TableHead>
                      <TableHead className="w-24">Cantidad</TableHead>
                      <TableHead className="w-32">Precio</TableHead>
                      <TableHead className="w-28">Subtotal</TableHead>
                      <TableHead className="w-12"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((item, i) => (
                      <TableRow key={i}>
                        <TableCell>
                          <span className="font-medium">{item.descripcion}</span>
                          <span className="text-xs text-muted-foreground ml-2">
                            {item.producto_id ? "(Producto)" : "(Servicio)"}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            min={1}
                            value={item.cantidad}
                            onChange={(e) => updateItem(i, "cantidad", parseInt(e.target.value) || 1)}
                            className="w-20"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            min={0}
                            step={0.01}
                            value={item.precio_unitario}
                            onChange={(e) => updateItem(i, "precio_unitario", parseFloat(e.target.value) || 0)}
                            className="w-28"
                          />
                        </TableCell>
                        <TableCell className="font-medium">
                          ${(item.cantidad * item.precio_unitario).toLocaleString()}
                        </TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" onClick={() => removeItem(i)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-center text-muted-foreground py-8">
                  Agrega productos o servicios a la venta
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Summary */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Cliente</CardTitle>
            </CardHeader>
            <CardContent>
              {clienteId ? (
                <div className="flex items-center justify-between">
                  <span className="font-medium">{clienteNombre}</span>
                  <Button size="sm" variant="ghost" onClick={() => { setClienteId(null); setClienteNombre(""); }}>
                    Quitar
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setClientDialogOpen(true)}
                >
                  <Search className="h-4 w-4 mr-2" /> Buscar Cliente
                </Button>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Resumen</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between text-sm">
                <span>Subtotal</span>
                <span>${subtotal.toLocaleString()}</span>
              </div>
              <div className="space-y-2">
                <Label className="text-sm">Descuento ($)</Label>
                <Input
                  type="number"
                  min={0}
                  step={0.01}
                  value={descuento}
                  onChange={(e) => setDescuento(parseFloat(e.target.value) || 0)}
                />
              </div>
              <div className="flex justify-between text-lg font-bold border-t pt-3">
                <span>Total</span>
                <span>${total.toLocaleString()}</span>
              </div>

              <div className="space-y-2">
                <Label className="text-sm">Metodo de Pago</Label>
                <Select value={metodoPago} onValueChange={setMetodoPago}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="efectivo">Efectivo</SelectItem>
                    <SelectItem value="tarjeta">Tarjeta</SelectItem>
                    <SelectItem value="transferencia">Transferencia</SelectItem>
                    <SelectItem value="otro">Otro</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label className="text-sm">Vendedor</Label>
                <Input value={vendedor} onChange={(e) => setVendedor(e.target.value)} placeholder="Nombre del vendedor" />
              </div>

              <div className="space-y-2">
                <Label className="text-sm">Notas</Label>
                <Textarea value={notas} onChange={(e) => setNotas(e.target.value)} rows={2} />
              </div>

              <Button
                className="w-full"
                size="lg"
                disabled={items.length === 0 || createMutation.isPending}
                onClick={handleSubmit}
              >
                {createMutation.isPending ? "Registrando..." : "Registrar Venta"}
              </Button>

              {createMutation.isError && (
                <p className="text-sm text-destructive text-center">
                  {(createMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al registrar la venta"}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Add Product Dialog */}
      <Dialog open={prodDialogOpen} onOpenChange={setProdDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Agregar Producto</DialogTitle></DialogHeader>
          <Input
            placeholder="Buscar producto..."
            value={prodSearch}
            onChange={(e) => setProdSearch(e.target.value)}
          />
          <div className="max-h-64 overflow-y-auto">
            <Table>
              <TableBody>
                {productos?.items
                  .filter((p) => p.activo && p.cantidad > 0)
                  .map((prod) => (
                    <TableRow
                      key={prod.id}
                      className="cursor-pointer"
                      onClick={() => addProduct(prod)}
                    >
                      <TableCell>
                        <div className="font-medium">{prod.nombre}</div>
                        <div className="text-xs text-muted-foreground">
                          Stock: {prod.cantidad} | {prod.marca || "Sin marca"}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        ${(prod.precio_venta || prod.costo_unitario).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                {(!productos || productos.items.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={2} className="text-center text-muted-foreground py-4">
                      No se encontraron productos
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Service Dialog */}
      <Dialog open={svcDialogOpen} onOpenChange={setSvcDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Agregar Servicio</DialogTitle></DialogHeader>
          <div className="max-h-64 overflow-y-auto">
            <Table>
              <TableBody>
                {servicios
                  .filter((s) => s.activo)
                  .map((svc) => (
                    <TableRow
                      key={svc.id}
                      className="cursor-pointer"
                      onClick={() => addService(svc)}
                    >
                      <TableCell>
                        <div className="font-medium">{svc.servicio}</div>
                        <div className="text-xs text-muted-foreground">{svc.duracion_minutos} min</div>
                      </TableCell>
                      <TableCell className="text-right">${svc.precio.toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </div>
        </DialogContent>
      </Dialog>

      {/* Client Search Dialog */}
      <Dialog open={clientDialogOpen} onOpenChange={setClientDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Buscar Cliente</DialogTitle></DialogHeader>
          <Input
            placeholder="Nombre o telefono..."
            value={clientSearch}
            onChange={(e) => setClientSearch(e.target.value)}
          />
          <div className="max-h-64 overflow-y-auto">
            <Table>
              <TableBody>
                {clientes?.items.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => {
                      setClienteId(c.id);
                      setClienteNombre(`${c.nombre} (${c.telefono})`);
                      setClientDialogOpen(false);
                    }}
                  >
                    <TableCell className="font-medium">{c.nombre}</TableCell>
                    <TableCell>{c.telefono}</TableCell>
                  </TableRow>
                ))}
                {(!clientes || clientes.items.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={2} className="text-center text-muted-foreground py-4">
                      No se encontraron clientes
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
