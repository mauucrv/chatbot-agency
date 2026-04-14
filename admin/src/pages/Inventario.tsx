import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, ChevronLeft, ChevronRight, Pencil, AlertTriangle } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PaginatedProductos, Producto, ProductoForm } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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

const CATEGORIAS = [
  { value: "all", label: "Todas" },
  { value: "reventa", label: "Reventa" },
  { value: "uso_salon", label: "Uso del Salon" },
];

const emptyForm: ProductoForm = {
  nombre: "",
  marca: "",
  categoria: "reventa",
  subcategoria: "",
  unidad: "unidad",
  costo_unitario: 0,
  precio_venta: 0,
  stock_minimo: 5,
  cantidad_inicial: 0,
  codigo_barras: "",
};

export default function Inventario() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [categoria, setCategoria] = useState("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Producto | null>(null);
  const [form, setForm] = useState<ProductoForm>(emptyForm);

  const { data, isLoading } = useQuery<PaginatedProductos>({
    queryKey: ["productos", page, busqueda, categoria],
    queryFn: () => {
      const params: Record<string, string | number> = { page, page_size: 20 };
      if (busqueda) params.busqueda = busqueda;
      if (categoria !== "all") params.categoria = categoria;
      return api.get("/inventario", { params }).then((r) => r.data);
    },
  });

  const saveMutation = useMutation({
    mutationFn: (data: ProductoForm & { id?: number }) => {
      if (data.id) {
        const { id, cantidad_inicial, ...body } = data;
        return api.put(`/inventario/${id}`, body);
      }
      return api.post("/inventario", data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["productos"] });
      setDialogOpen(false);
    },
  });

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (prod: Producto) => {
    setEditing(prod);
    setForm({
      nombre: prod.nombre,
      marca: prod.marca || "",
      categoria: prod.categoria,
      subcategoria: prod.subcategoria || "",
      unidad: prod.unidad || "unidad",
      costo_unitario: prod.costo_unitario,
      precio_venta: prod.precio_venta || 0,
      stock_minimo: prod.stock_minimo,
      codigo_barras: prod.codigo_barras || "",
    });
    setDialogOpen(true);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setBusqueda(searchInput);
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  const stockBadge = (prod: Producto) => {
    if (prod.cantidad <= 0)
      return <Badge variant="destructive">Agotado</Badge>;
    if (prod.cantidad <= prod.stock_minimo)
      return <Badge className="bg-amber-500 hover:bg-amber-600 text-white">{prod.cantidad} {prod.unidad}</Badge>;
    return <Badge variant="secondary">{prod.cantidad} {prod.unidad}</Badge>;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Inventario</h1>
        {isAdmin && (
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-2" /> Nuevo Producto
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder="Buscar producto..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-64"
          />
          <Button type="submit" variant="outline" size="icon">
            <Search className="h-4 w-4" />
          </Button>
        </form>
        <Select
          value={categoria}
          onValueChange={(v) => { setCategoria(v); setPage(1); }}
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Categoria" />
          </SelectTrigger>
          <SelectContent>
            {CATEGORIAS.map((c) => (
              <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Producto</TableHead>
              <TableHead>Marca</TableHead>
              <TableHead>Categoria</TableHead>
              <TableHead>Stock</TableHead>
              <TableHead>Costo</TableHead>
              <TableHead>Precio Venta</TableHead>
              {isAdmin && <TableHead className="w-[60px]"></TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto" />
                </TableCell>
              </TableRow>
            ) : (
              data?.items.map((prod) => (
                <TableRow
                  key={prod.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/inventario/${prod.id}`)}
                >
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{prod.nombre}</span>
                      {prod.cantidad <= prod.stock_minimo && prod.cantidad > 0 && (
                        <AlertTriangle className="h-4 w-4 text-amber-500" />
                      )}
                    </div>
                    {prod.subcategoria && (
                      <p className="text-xs text-muted-foreground">{prod.subcategoria}</p>
                    )}
                  </TableCell>
                  <TableCell>{prod.marca || "-"}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {prod.categoria === "reventa" ? "Reventa" : "Uso Salon"}
                    </Badge>
                  </TableCell>
                  <TableCell>{stockBadge(prod)}</TableCell>
                  <TableCell>${prod.costo_unitario.toLocaleString()}</TableCell>
                  <TableCell>{prod.precio_venta ? `$${prod.precio_venta.toLocaleString()}` : "-"}</TableCell>
                  {isAdmin && (
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => { e.stopPropagation(); openEdit(prod); }}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
            {!isLoading && data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No se encontraron productos
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">{data?.total} productos en total</p>
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

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? "Editar Producto" : "Nuevo Producto"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
            <div className="space-y-2">
              <Label>Nombre *</Label>
              <Input value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Marca</Label>
                <Input value={form.marca || ""} onChange={(e) => setForm({ ...form, marca: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>Categoria *</Label>
                <Select value={form.categoria} onValueChange={(v) => setForm({ ...form, categoria: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="reventa">Reventa</SelectItem>
                    <SelectItem value="uso_salon">Uso del Salon</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Subcategoria</Label>
                <Input value={form.subcategoria || ""} onChange={(e) => setForm({ ...form, subcategoria: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>Unidad</Label>
                <Input value={form.unidad || "unidad"} onChange={(e) => setForm({ ...form, unidad: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Costo Unitario ($)</Label>
                <Input
                  type="number" min={0} step={0.01}
                  value={form.costo_unitario}
                  onChange={(e) => setForm({ ...form, costo_unitario: parseFloat(e.target.value) || 0 })}
                />
              </div>
              <div className="space-y-2">
                <Label>Precio Venta ($)</Label>
                <Input
                  type="number" min={0} step={0.01}
                  value={form.precio_venta || ""}
                  onChange={(e) => setForm({ ...form, precio_venta: parseFloat(e.target.value) || 0 })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Stock Minimo</Label>
                <Input
                  type="number" min={0}
                  value={form.stock_minimo}
                  onChange={(e) => setForm({ ...form, stock_minimo: parseInt(e.target.value) || 0 })}
                />
              </div>
              {!editing && (
                <div className="space-y-2">
                  <Label>Cantidad Inicial</Label>
                  <Input
                    type="number" min={0}
                    value={form.cantidad_inicial || 0}
                    onChange={(e) => setForm({ ...form, cantidad_inicial: parseInt(e.target.value) || 0 })}
                  />
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Codigo de Barras</Label>
                <Input value={form.codigo_barras || ""} onChange={(e) => setForm({ ...form, codigo_barras: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>Fecha de Vencimiento</Label>
                <Input
                  type="date"
                  value={form.fecha_vencimiento || ""}
                  onChange={(e) => setForm({ ...form, fecha_vencimiento: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button
              onClick={() => saveMutation.mutate(editing ? { ...form, id: editing.id } : form)}
              disabled={saveMutation.isPending || !form.nombre}
            >
              {saveMutation.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
