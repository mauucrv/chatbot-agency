import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, ChevronLeft, ChevronRight, Pencil, Trash2 } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PaginatedFichas, FichaCliente, FichaClienteForm } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";

const TIPOS_CABELLO = ["liso", "ondulado", "rizado", "crespo", "mixto"];
const TIPOS_PIEL = ["normal", "seca", "grasa", "mixta", "sensible"];

const emptyForm: FichaClienteForm = {
  nombre: "",
  telefono: "",
  email: "",
  tipo_cabello: "",
  tipo_piel: "",
  alergias: "",
  preferencias: "",
  notas: "",
};

export default function Clientes() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<FichaCliente | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState<FichaClienteForm>(emptyForm);

  const { data, isLoading } = useQuery<PaginatedFichas>({
    queryKey: ["fichas", page, busqueda],
    queryFn: () => {
      const params: Record<string, string | number> = { page, page_size: 20 };
      if (busqueda) params.busqueda = busqueda;
      return api.get("/fichas", { params }).then((r) => r.data);
    },
  });

  const saveMutation = useMutation({
    mutationFn: (data: FichaClienteForm & { id?: number }) => {
      const body = { ...data };
      if (!body.email) delete body.email;
      if (!body.tipo_cabello) delete body.tipo_cabello;
      if (!body.tipo_piel) delete body.tipo_piel;
      if (!body.alergias) delete body.alergias;
      if (!body.preferencias) delete body.preferencias;
      if (!body.notas) delete body.notas;

      if (data.id) {
        const { id, ...rest } = body as FichaClienteForm & { id: number };
        return api.put(`/fichas/${data.id}`, rest);
      }
      return api.post("/fichas", body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fichas"] });
      setDialogOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/fichas/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fichas"] });
      setDeleteId(null);
    },
  });

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (ficha: FichaCliente) => {
    setEditing(ficha);
    setForm({
      nombre: ficha.nombre,
      telefono: ficha.telefono,
      email: ficha.email || "",
      tipo_cabello: ficha.tipo_cabello || "",
      tipo_piel: ficha.tipo_piel || "",
      alergias: ficha.alergias || "",
      preferencias: ficha.preferencias || "",
      notas: ficha.notas || "",
    });
    setDialogOpen(true);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setBusqueda(searchInput);
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Clientes</h1>
        {isAdmin && (
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-2" /> Nuevo Cliente
          </Button>
        )}
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <Input
          placeholder="Buscar por nombre o telefono..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="w-64"
        />
        <Button type="submit" variant="outline" size="icon">
          <Search className="h-4 w-4" />
        </Button>
      </form>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Telefono</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Tipo Cabello</TableHead>
              <TableHead>Tipo Piel</TableHead>
              <TableHead>Estado</TableHead>
              {isAdmin && <TableHead className="w-[100px]">Acciones</TableHead>}
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
              data?.items.map((ficha) => (
                <TableRow
                  key={ficha.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/clientes/${ficha.id}`)}
                >
                  <TableCell className="font-medium">{ficha.nombre}</TableCell>
                  <TableCell>{ficha.telefono}</TableCell>
                  <TableCell>{ficha.email || "-"}</TableCell>
                  <TableCell>
                    {ficha.tipo_cabello ? (
                      <Badge variant="secondary">{ficha.tipo_cabello}</Badge>
                    ) : "-"}
                  </TableCell>
                  <TableCell>
                    {ficha.tipo_piel ? (
                      <Badge variant="secondary">{ficha.tipo_piel}</Badge>
                    ) : "-"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={ficha.activo ? "default" : "destructive"}>
                      {ficha.activo ? "Activo" : "Inactivo"}
                    </Badge>
                  </TableCell>
                  {isAdmin && (
                    <TableCell>
                      <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="icon" onClick={() => openEdit(ficha)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteId(ficha.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
            {!isLoading && data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No se encontraron clientes
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">{data?.total} clientes en total</p>
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
            <DialogTitle>{editing ? "Editar Cliente" : "Nuevo Cliente"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Nombre *</Label>
                <Input
                  value={form.nombre}
                  onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Telefono *</Label>
                <Input
                  value={form.telefono}
                  onChange={(e) => setForm({ ...form, telefono: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input
                type="email"
                value={form.email || ""}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Tipo de Cabello</Label>
                <Select
                  value={form.tipo_cabello || "none"}
                  onValueChange={(v) => setForm({ ...form, tipo_cabello: v === "none" ? "" : v })}
                >
                  <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Sin especificar</SelectItem>
                    {TIPOS_CABELLO.map((t) => (
                      <SelectItem key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Tipo de Piel</Label>
                <Select
                  value={form.tipo_piel || "none"}
                  onValueChange={(v) => setForm({ ...form, tipo_piel: v === "none" ? "" : v })}
                >
                  <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Sin especificar</SelectItem>
                    {TIPOS_PIEL.map((t) => (
                      <SelectItem key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Alergias</Label>
              <Textarea
                value={form.alergias || ""}
                onChange={(e) => setForm({ ...form, alergias: e.target.value })}
                placeholder="Alergias conocidas..."
              />
            </div>
            <div className="space-y-2">
              <Label>Preferencias</Label>
              <Textarea
                value={form.preferencias || ""}
                onChange={(e) => setForm({ ...form, preferencias: e.target.value })}
                placeholder="Preferencias del cliente..."
              />
            </div>
            <div className="space-y-2">
              <Label>Notas</Label>
              <Textarea
                value={form.notas || ""}
                onChange={(e) => setForm({ ...form, notas: e.target.value })}
                placeholder="Notas adicionales..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button
              onClick={() => saveMutation.mutate(editing ? { ...form, id: editing.id } : form)}
              disabled={saveMutation.isPending || !form.nombre || !form.telefono}
            >
              {saveMutation.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteId !== null}
        onOpenChange={() => setDeleteId(null)}
        title="Eliminar Cliente"
        description="Esta accion eliminara la ficha del cliente permanentemente."
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        confirmLabel="Eliminar"
        destructive
      />
    </div>
  );
}
