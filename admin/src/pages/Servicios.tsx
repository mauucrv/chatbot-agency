import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2 } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Service, ServiceForm } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";

export default function Servicios() {
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Service | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState<ServiceForm>({
    servicio: "",
    descripcion: "",
    precio: 0,
    duracion_minutos: 30,
  });

  const { data: services = [], isLoading } = useQuery<Service[]>({
    queryKey: ["services"],
    queryFn: () => api.get("/servicios").then((r) => r.data),
  });

  const saveMutation = useMutation({
    mutationFn: (data: ServiceForm & { id?: number; activo?: boolean }) => {
      if (data.id) {
        const { id, ...body } = data;
        return api.put(`/servicios/${id}`, body);
      }
      return api.post("/servicios", data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["services"] });
      setDialogOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/servicios/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["services"] });
      setDeleteId(null);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) =>
      api.put(`/servicios/${id}`, { activo }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["services"] }),
  });

  const openCreate = () => {
    setEditing(null);
    setForm({ servicio: "", descripcion: "", precio: 0, duracion_minutos: 30 });
    setDialogOpen(true);
  };

  const openEdit = (svc: Service) => {
    setEditing(svc);
    setForm({
      servicio: svc.servicio,
      descripcion: svc.descripcion || "",
      precio: svc.precio,
      duracion_minutos: svc.duracion_minutos,
      estilistas_disponibles: svc.estilistas_disponibles || undefined,
    });
    setDialogOpen(true);
  };

  const handleSave = () => {
    if (editing) {
      saveMutation.mutate({ ...form, id: editing.id });
    } else {
      saveMutation.mutate(form);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Servicios</h1>
        {isAdmin && (
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-2" /> Nuevo Servicio
          </Button>
        )}
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Servicio</TableHead>
              <TableHead>Precio</TableHead>
              <TableHead>Duracion</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="w-[100px]">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {services.map((svc) => (
              <TableRow key={svc.id}>
                <TableCell>
                  <div>
                    <p className="font-medium">{svc.servicio}</p>
                    {svc.descripcion && (
                      <p className="text-sm text-muted-foreground line-clamp-1">
                        {svc.descripcion}
                      </p>
                    )}
                  </div>
                </TableCell>
                <TableCell>${svc.precio.toLocaleString()}</TableCell>
                <TableCell>{svc.duracion_minutos} min</TableCell>
                <TableCell>
                  <Switch
                    checked={svc.activo}
                    disabled={!isAdmin}
                    onCheckedChange={(checked) =>
                      toggleMutation.mutate({ id: svc.id, activo: checked })
                    }
                  />
                </TableCell>
                {isAdmin && (
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(svc)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteId(svc.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                )}
              </TableRow>
            ))}
            {services.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  No hay servicios registrados
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Editar Servicio" : "Nuevo Servicio"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Nombre del servicio</Label>
              <Input
                value={form.servicio}
                onChange={(e) => setForm({ ...form, servicio: e.target.value })}
                placeholder="Corte de cabello"
              />
            </div>
            <div className="space-y-2">
              <Label>Descripcion</Label>
              <Textarea
                value={form.descripcion || ""}
                onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
                placeholder="Descripcion del servicio..."
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Precio ($)</Label>
                <Input
                  type="number"
                  min={0}
                  step={0.01}
                  value={form.precio}
                  onChange={(e) =>
                    setForm({ ...form, precio: parseFloat(e.target.value) || 0 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Duracion (min)</Label>
                <Input
                  type="number"
                  min={1}
                  value={form.duracion_minutos}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      duracion_minutos: parseInt(e.target.value) || 1,
                    })
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleSave} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <ConfirmDialog
        open={deleteId !== null}
        onOpenChange={() => setDeleteId(null)}
        title="Eliminar Servicio"
        description="Esta accion no se puede deshacer. El servicio sera eliminado permanentemente."
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        confirmLabel="Eliminar"
        destructive
      />
    </div>
  );
}
