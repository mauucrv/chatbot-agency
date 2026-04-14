import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Clock } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Stylist, StylistForm } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

export default function Consultors() {
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Stylist | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState<StylistForm>({
    nombre: "",
    telefono: "",
    email: "",
    especialidades: [],
  });
  const [especialidadInput, setEspecialidadInput] = useState("");

  const { data: stylists = [], isLoading } = useQuery<Stylist[]>({
    queryKey: ["stylists"],
    queryFn: () => api.get("/estilistas").then((r) => r.data),
  });

  const saveMutation = useMutation({
    mutationFn: (data: StylistForm & { id?: number }) => {
      if (data.id) {
        const { id, ...body } = data;
        return api.put(`/estilistas/${id}`, body);
      }
      return api.post("/estilistas", data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stylists"] });
      setDialogOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/estilistas/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stylists"] });
      setDeleteId(null);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) =>
      api.put(`/estilistas/${id}`, { activo }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["stylists"] }),
  });

  const openCreate = () => {
    setEditing(null);
    setForm({ nombre: "", telefono: "", email: "", especialidades: [] });
    setEspecialidadInput("");
    setDialogOpen(true);
  };

  const openEdit = (s: Stylist) => {
    setEditing(s);
    setForm({
      nombre: s.nombre,
      telefono: s.telefono || "",
      email: s.email || "",
      especialidades: s.especialidades || [],
    });
    setEspecialidadInput("");
    setDialogOpen(true);
  };

  const addEspecialidad = () => {
    const val = especialidadInput.trim();
    if (val && !form.especialidades?.includes(val)) {
      setForm({ ...form, especialidades: [...(form.especialidades || []), val] });
      setEspecialidadInput("");
    }
  };

  const removeEspecialidad = (idx: number) => {
    setForm({
      ...form,
      especialidades: (form.especialidades || []).filter((_, i) => i !== idx),
    });
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
        <h1 className="text-2xl font-bold">Consultors</h1>
        {isAdmin && (
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-2" /> Nuevo Consultor
          </Button>
        )}
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Contacto</TableHead>
              <TableHead>Especialidades</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="w-[120px]">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {stylists.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="font-medium">{s.nombre}</TableCell>
                <TableCell>
                  <div className="text-sm">
                    {s.telefono && <p>{s.telefono}</p>}
                    {s.email && (
                      <p className="text-muted-foreground">{s.email}</p>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {s.especialidades?.map((e) => (
                      <Badge key={e} variant="secondary" className="text-xs">
                        {e}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <Switch
                    checked={s.activo}
                    disabled={!isAdmin}
                    onCheckedChange={(checked) =>
                      toggleMutation.mutate({ id: s.id, activo: checked })
                    }
                  />
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => navigate(`/consultores/${s.id}`)}
                      title="Horarios"
                    >
                      <Clock className="h-4 w-4" />
                    </Button>
                    {isAdmin && (
                      <>
                        <Button variant="ghost" size="icon" onClick={() => openEdit(s)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteId(s.id)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {stylists.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  No hay consultores registrados
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Editar Consultor" : "Nuevo Consultor"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Nombre</Label>
              <Input
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Telefono</Label>
                <Input
                  value={form.telefono || ""}
                  onChange={(e) => setForm({ ...form, telefono: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={form.email || ""}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Especialidades</Label>
              <div className="flex gap-2">
                <Input
                  value={especialidadInput}
                  onChange={(e) => setEspecialidadInput(e.target.value)}
                  placeholder="Agregar especialidad"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addEspecialidad();
                    }
                  }}
                />
                <Button type="button" variant="outline" onClick={addEspecialidad}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {form.especialidades?.map((e, i) => (
                  <Badge
                    key={i}
                    variant="secondary"
                    className="cursor-pointer"
                    onClick={() => removeEspecialidad(i)}
                  >
                    {e} &times;
                  </Badge>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (editing) saveMutation.mutate({ ...form, id: editing.id });
                else saveMutation.mutate(form);
              }}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteId !== null}
        onOpenChange={() => setDeleteId(null)}
        title="Eliminar Consultor"
        description="Esta accion eliminara al consultor y todos sus horarios asociados."
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        confirmLabel="Eliminar"
        destructive
      />
    </div>
  );
}
