import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus } from "lucide-react";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FichaCliente, Appointment } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";

export default function ClienteDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<"info" | "color" | "tratamientos" | "citas">("info");
  const [histDialogOpen, setHistDialogOpen] = useState(false);
  const [histType, setHistType] = useState<"color" | "tratamientos">("color");
  const [histForm, setHistForm] = useState({ fecha: "", descripcion: "", estilista: "" });

  const { data: ficha, isLoading } = useQuery<FichaCliente>({
    queryKey: ["ficha", id],
    queryFn: () => api.get(`/fichas/${id}`).then((r) => r.data),
  });

  const { data: citas = [] } = useQuery<Appointment[]>({
    queryKey: ["ficha-citas", id],
    queryFn: () => api.get(`/fichas/${id}/citas`).then((r) => r.data),
    enabled: activeTab === "citas",
  });

  const histMutation = useMutation({
    mutationFn: (data: { type: string; body: typeof histForm }) =>
      api.post(`/fichas/${id}/historial-${data.type}`, data.body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ficha", id] });
      setHistDialogOpen(false);
      setHistForm({ fecha: "", descripcion: "", estilista: "" });
    },
  });

  const openAddHistorial = (type: "color" | "tratamientos") => {
    setHistType(type);
    setHistForm({ fecha: new Date().toISOString().split("T")[0], descripcion: "", estilista: "" });
    setHistDialogOpen(true);
  };

  if (isLoading || !ficha) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const tabs = [
    { key: "info", label: "Informacion" },
    { key: "color", label: "Historial Color" },
    { key: "tratamientos", label: "Historial Tratamientos" },
    { key: "citas", label: "Citas" },
  ] as const;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/clientes")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{ficha.nombre}</h1>
          <p className="text-muted-foreground">{ficha.telefono}</p>
        </div>
        <Badge variant={ficha.activo ? "default" : "destructive"} className="ml-auto">
          {ficha.activo ? "Activo" : "Inactivo"}
        </Badge>
      </div>

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

      {/* Info tab */}
      {activeTab === "info" && (
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-lg">Datos Personales</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div><span className="text-sm text-muted-foreground">Email:</span> <span>{ficha.email || "-"}</span></div>
              <div><span className="text-sm text-muted-foreground">Tipo de Cabello:</span> <span>{ficha.tipo_cabello || "-"}</span></div>
              <div><span className="text-sm text-muted-foreground">Tipo de Piel:</span> <span>{ficha.tipo_piel || "-"}</span></div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-lg">Detalles</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div>
                <span className="text-sm text-muted-foreground block">Alergias:</span>
                <span>{ficha.alergias || "Ninguna registrada"}</span>
              </div>
              <div>
                <span className="text-sm text-muted-foreground block">Preferencias:</span>
                <span>{ficha.preferencias || "Sin preferencias registradas"}</span>
              </div>
              <div>
                <span className="text-sm text-muted-foreground block">Notas:</span>
                <span>{ficha.notas || "Sin notas"}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Color history tab */}
      {activeTab === "color" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Historial de Color</CardTitle>
            {isAdmin && (
              <Button size="sm" onClick={() => openAddHistorial("color")}>
                <Plus className="h-4 w-4 mr-1" /> Agregar
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {(ficha.historial_color?.length || 0) > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Descripcion</TableHead>
                    <TableHead>Estilista</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ficha.historial_color?.map((entry, i) => (
                    <TableRow key={i}>
                      <TableCell>{entry.fecha}</TableCell>
                      <TableCell>{entry.descripcion}</TableCell>
                      <TableCell>{entry.estilista || "-"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">Sin historial de color</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Treatment history tab */}
      {activeTab === "tratamientos" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Historial de Tratamientos</CardTitle>
            {isAdmin && (
              <Button size="sm" onClick={() => openAddHistorial("tratamientos")}>
                <Plus className="h-4 w-4 mr-1" /> Agregar
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {(ficha.historial_tratamientos?.length || 0) > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Descripcion</TableHead>
                    <TableHead>Estilista</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ficha.historial_tratamientos?.map((entry, i) => (
                    <TableRow key={i}>
                      <TableCell>{entry.fecha}</TableCell>
                      <TableCell>{entry.descripcion}</TableCell>
                      <TableCell>{entry.estilista || "-"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">Sin historial de tratamientos</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Appointments tab */}
      {activeTab === "citas" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Citas del Cliente</CardTitle>
          </CardHeader>
          <CardContent>
            {citas.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Servicios</TableHead>
                    <TableHead>Total</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {citas.map((cita) => (
                    <TableRow
                      key={cita.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/citas/${cita.id}`)}
                    >
                      <TableCell>
                        {format(parseISO(cita.inicio), "dd MMM yyyy HH:mm", { locale: es })}
                      </TableCell>
                      <TableCell className="text-sm">{cita.servicios.join(", ")}</TableCell>
                      <TableCell>${cita.precio_total.toLocaleString()}</TableCell>
                      <TableCell><StatusBadge status={cita.estado} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No hay citas registradas</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Add history entry dialog */}
      <Dialog open={histDialogOpen} onOpenChange={setHistDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Agregar {histType === "color" ? "Entrada de Color" : "Tratamiento"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Fecha</Label>
              <Input
                type="date"
                value={histForm.fecha}
                onChange={(e) => setHistForm({ ...histForm, fecha: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Descripcion *</Label>
              <Textarea
                value={histForm.descripcion}
                onChange={(e) => setHistForm({ ...histForm, descripcion: e.target.value })}
                placeholder={histType === "color" ? "Ej: Balayage rubio cenizo" : "Ej: Keratina brasilena"}
              />
            </div>
            <div className="space-y-2">
              <Label>Estilista</Label>
              <Input
                value={histForm.estilista}
                onChange={(e) => setHistForm({ ...histForm, estilista: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setHistDialogOpen(false)}>Cancelar</Button>
            <Button
              onClick={() => histMutation.mutate({ type: histType, body: histForm })}
              disabled={histMutation.isPending || !histForm.descripcion || !histForm.fecha}
            >
              {histMutation.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
