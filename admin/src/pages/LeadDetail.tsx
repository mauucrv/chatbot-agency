import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Pencil,
  Trash2,
  Phone,
  Mail,
  Building2,
  MessageSquare,
  Calendar,
  Clock,
  AlertCircle,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Lead, LeadForm, Appointment } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { LeadStageBadge } from "@/components/shared/LeadStageBadge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";

const ETAPAS = [
  { value: "nuevo", label: "Nuevo" },
  { value: "contactado", label: "Contactado" },
  { value: "cita_agendada", label: "Cita Agendada" },
  { value: "en_negociacion", label: "En Negociacion" },
  { value: "cerrado_ganado", label: "Cerrado Ganado" },
  { value: "cerrado_perdido", label: "Cerrado Perdido" },
];

const ORIGENES = [
  { value: "whatsapp_organico", label: "WhatsApp Organico" },
  { value: "meta_ads", label: "Meta Ads" },
  { value: "referido", label: "Referido" },
  { value: "sitio_web", label: "Sitio Web" },
  { value: "otro", label: "Otro" },
];

interface ConversacionData {
  conversation_id: number;
  contact_id: number | null;
  bot_activo: boolean;
  ultimo_mensaje_at: string | null;
}

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [form, setForm] = useState<LeadForm>({ telefono: "" });

  const { data: lead, isLoading } = useQuery<Lead>({
    queryKey: ["lead", id],
    queryFn: () => api.get(`/leads/${id}`).then((r) => r.data),
  });

  const { data: citas = [] } = useQuery<Appointment[]>({
    queryKey: ["lead-citas", id],
    queryFn: () => api.get(`/leads/${id}/citas`).then((r) => r.data),
    enabled: !!lead,
  });

  const { data: conversacion } = useQuery<ConversacionData | null>({
    queryKey: ["lead-conversacion", id],
    queryFn: () => api.get(`/leads/${id}/conversacion`).then((r) => r.data),
    enabled: !!lead,
  });

  const stageMutation = useMutation({
    mutationFn: (etapa: string) =>
      api.patch(`/leads/${id}/etapa`, null, { params: { etapa } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead", id] });
      qc.invalidateQueries({ queryKey: ["leads-pipeline"] });
    },
  });

  const saveMutation = useMutation({
    mutationFn: (data: LeadForm) => {
      const cleaned = Object.fromEntries(
        Object.entries(data).filter(([, v]) => v !== "" && v !== undefined)
      );
      return api.put(`/leads/${id}`, cleaned);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead", id] });
      qc.invalidateQueries({ queryKey: ["leads"] });
      setEditOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/leads/${id}`),
    onSuccess: () => navigate("/leads"),
  });

  const openEdit = () => {
    if (!lead) return;
    setForm({
      nombre: lead.nombre || "",
      telefono: lead.telefono,
      email: lead.email || "",
      empresa: lead.empresa || "",
      etapa: lead.etapa,
      origen: lead.origen,
      notas: lead.notas || "",
      valor_estimado: lead.valor_estimado || undefined,
      servicio_interes: lead.servicio_interes || "",
      proximo_seguimiento: lead.proximo_seguimiento
        ? lead.proximo_seguimiento.slice(0, 16)
        : "",
    });
    setEditOpen(true);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Prospecto no encontrado
      </div>
    );
  }

  const seguimientoVencido =
    lead.proximo_seguimiento && new Date(lead.proximo_seguimiento) < new Date();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/leads")}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{lead.nombre || "Sin nombre"}</h1>
            <p className="text-sm text-muted-foreground">
              Creado {format(parseISO(lead.created_at), "dd MMM yyyy", { locale: es })}
            </p>
          </div>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={openEdit}>
              <Pencil className="h-4 w-4 mr-2" /> Editar
            </Button>
            <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
              <Trash2 className="h-4 w-4 mr-2" /> Eliminar
            </Button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column — Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Contact Info Card */}
          <div className="border rounded-lg p-5 space-y-4">
            <h2 className="font-semibold text-lg">Informacion de Contacto</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-muted-foreground" />
                <span>{lead.telefono}</span>
              </div>
              {lead.email && (
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <span>{lead.email}</span>
                </div>
              )}
              {lead.empresa && (
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  <span>{lead.empresa}</span>
                </div>
              )}
              {lead.servicio_interes && (
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span>{lead.servicio_interes}</span>
                </div>
              )}
            </div>
            {lead.notas && (
              <div className="pt-2 border-t">
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {lead.notas}
                </p>
              </div>
            )}
          </div>

          {/* Linked Appointments */}
          <div className="border rounded-lg p-5 space-y-4">
            <h2 className="font-semibold text-lg">Consultas Vinculadas</h2>
            {citas.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No hay consultas vinculadas a este prospecto
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Servicios</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Total</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {citas.map((cita) => (
                    <TableRow
                      key={cita.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/consultas/${cita.id}`)}
                    >
                      <TableCell>
                        {format(parseISO(cita.inicio), "dd MMM yyyy HH:mm", {
                          locale: es,
                        })}
                      </TableCell>
                      <TableCell>
                        <span className="text-sm">
                          {cita.servicios.join(", ")}
                        </span>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={cita.estado} />
                      </TableCell>
                      <TableCell>${cita.precio_total.toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </div>

        {/* Right Column — Stage & Follow-up */}
        <div className="space-y-6">
          {/* Stage */}
          <div className="border rounded-lg p-5 space-y-4">
            <h2 className="font-semibold text-lg">Etapa</h2>
            <div className="flex items-center gap-2 mb-3">
              <LeadStageBadge stage={lead.etapa} />
            </div>
            {isAdmin && (
              <div className="grid grid-cols-2 gap-2">
                {ETAPAS.map((e) => (
                  <Button
                    key={e.value}
                    variant={lead.etapa === e.value ? "default" : "outline"}
                    size="sm"
                    className="text-xs"
                    disabled={lead.etapa === e.value || stageMutation.isPending}
                    onClick={() => stageMutation.mutate(e.value)}
                  >
                    {e.label}
                  </Button>
                ))}
              </div>
            )}
          </div>

          {/* Follow-up */}
          <div className="border rounded-lg p-5 space-y-3">
            <h2 className="font-semibold text-lg flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Seguimiento
            </h2>
            {lead.proximo_seguimiento ? (
              <div
                className={`rounded-lg p-3 ${
                  seguimientoVencido
                    ? "bg-red-50 border border-red-200"
                    : "bg-muted"
                }`}
              >
                <div className="flex items-center gap-2">
                  {seguimientoVencido && (
                    <AlertCircle className="h-4 w-4 text-red-500" />
                  )}
                  <span
                    className={`text-sm font-medium ${
                      seguimientoVencido ? "text-red-700" : ""
                    }`}
                  >
                    {format(parseISO(lead.proximo_seguimiento), "dd MMM yyyy HH:mm", {
                      locale: es,
                    })}
                  </span>
                </div>
                {seguimientoVencido && (
                  <p className="text-xs text-red-600 mt-1">
                    Seguimiento vencido
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Sin seguimiento programado
              </p>
            )}
            {lead.ultimo_contacto && (
              <p className="text-xs text-muted-foreground">
                Ultimo contacto:{" "}
                {format(parseISO(lead.ultimo_contacto), "dd MMM yyyy HH:mm", {
                  locale: es,
                })}
              </p>
            )}
          </div>

          {/* Pipeline Info */}
          <div className="border rounded-lg p-5 space-y-3">
            <h2 className="font-semibold text-lg">Detalles</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Origen</span>
                <span>
                  {ORIGENES.find((o) => o.value === lead.origen)?.label || lead.origen}
                </span>
              </div>
              {lead.valor_estimado != null && lead.valor_estimado > 0 && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Valor Estimado</span>
                  <span className="font-medium">
                    ${lead.valor_estimado.toLocaleString()}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Estado</span>
                <Badge variant={lead.activo ? "default" : "secondary"}>
                  {lead.activo ? "Activo" : "Inactivo"}
                </Badge>
              </div>
            </div>
          </div>

          {/* Chatwoot Conversation */}
          {conversacion && (
            <div className="border rounded-lg p-5 space-y-3">
              <h2 className="font-semibold text-lg flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Conversacion
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">ID Conversacion</span>
                  <span>#{conversacion.conversation_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Bot</span>
                  <Badge variant={conversacion.bot_activo ? "default" : "secondary"}>
                    {conversacion.bot_activo ? "Activo" : "Pausado"}
                  </Badge>
                </div>
                {conversacion.ultimo_mensaje_at && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Ultimo msg</span>
                    <span>
                      {format(
                        parseISO(conversacion.ultimo_mensaje_at),
                        "dd MMM HH:mm",
                        { locale: es }
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Editar Prospecto</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Nombre</Label>
                <Input
                  value={form.nombre || ""}
                  onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Telefono</Label>
                <Input
                  value={form.telefono}
                  onChange={(e) => setForm({ ...form, telefono: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={form.email || ""}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Empresa</Label>
                <Input
                  value={form.empresa || ""}
                  onChange={(e) => setForm({ ...form, empresa: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Etapa</Label>
                <Select
                  value={form.etapa || "nuevo"}
                  onValueChange={(v) => setForm({ ...form, etapa: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ETAPAS.map((e) => (
                      <SelectItem key={e.value} value={e.value}>{e.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Origen</Label>
                <Select
                  value={form.origen || "whatsapp_organico"}
                  onValueChange={(v) => setForm({ ...form, origen: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ORIGENES.map((o) => (
                      <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Servicio de Interes</Label>
                <Input
                  value={form.servicio_interes || ""}
                  onChange={(e) => setForm({ ...form, servicio_interes: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Valor Estimado</Label>
                <Input
                  type="number"
                  value={form.valor_estimado ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      valor_estimado: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Proximo Seguimiento</Label>
              <Input
                type="datetime-local"
                value={form.proximo_seguimiento || ""}
                onChange={(e) => setForm({ ...form, proximo_seguimiento: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Notas</Label>
              <Textarea
                value={form.notas || ""}
                onChange={(e) => setForm({ ...form, notas: e.target.value })}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => saveMutation.mutate(form)}
              disabled={saveMutation.isPending || !form.telefono}
            >
              {saveMutation.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Eliminar Prospecto"
        description="Esta accion eliminara permanentemente este prospecto y toda su informacion."
        onConfirm={() => deleteMutation.mutate()}
        confirmLabel="Eliminar"
        destructive
      />
    </div>
  );
}
