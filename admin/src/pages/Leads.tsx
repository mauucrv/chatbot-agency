import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, ChevronLeft, ChevronRight, Target } from "lucide-react";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PaginatedLeads, PipelineStage, Lead, LeadForm } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { LeadStageBadge } from "@/components/shared/LeadStageBadge";

const ETAPAS = [
  { value: "all", label: "Todas las etapas" },
  { value: "nuevo", label: "Nuevo" },
  { value: "contactado", label: "Contactado" },
  { value: "cita_agendada", label: "Cita Agendada" },
  { value: "en_negociacion", label: "En Negociacion" },
  { value: "cerrado_ganado", label: "Cerrado Ganado" },
  { value: "cerrado_perdido", label: "Cerrado Perdido" },
];

const ORIGENES = [
  { value: "all", label: "Todos los origenes" },
  { value: "whatsapp_organico", label: "WhatsApp Organico" },
  { value: "meta_ads", label: "Meta Ads" },
  { value: "referido", label: "Referido" },
  { value: "sitio_web", label: "Sitio Web" },
  { value: "otro", label: "Otro" },
];

const ORIGEN_LABELS: Record<string, string> = {
  whatsapp_organico: "WhatsApp",
  meta_ads: "Meta Ads",
  referido: "Referido",
  sitio_web: "Sitio Web",
  otro: "Otro",
};

const STAGE_COLORS: Record<string, string> = {
  nuevo: "bg-blue-50 border-blue-200 text-blue-700",
  contactado: "bg-yellow-50 border-yellow-200 text-yellow-700",
  cita_agendada: "bg-purple-50 border-purple-200 text-purple-700",
  en_negociacion: "bg-orange-50 border-orange-200 text-orange-700",
  cerrado_ganado: "bg-emerald-50 border-emerald-200 text-emerald-700",
  cerrado_perdido: "bg-red-50 border-red-200 text-red-700",
};

const emptyForm: LeadForm = {
  telefono: "",
  nombre: "",
  email: "",
  empresa: "",
  etapa: "nuevo",
  origen: "whatsapp_organico",
  notas: "",
  valor_estimado: undefined,
  servicio_interes: "",
  proximo_seguimiento: "",
};

export default function Leads() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [etapa, setEtapa] = useState("all");
  const [origen, setOrigen] = useState("all");
  const [busqueda, setBusqueda] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Lead | null>(null);
  const [form, setForm] = useState<LeadForm>({ ...emptyForm });

  const { data: pipeline = [] } = useQuery<PipelineStage[]>({
    queryKey: ["leads-pipeline"],
    queryFn: () => api.get("/leads/pipeline/summary").then((r) => r.data),
  });

  const { data, isLoading } = useQuery<PaginatedLeads>({
    queryKey: ["leads", page, etapa, origen, busqueda],
    queryFn: () => {
      const params: Record<string, string | number | boolean> = { page, page_size: 20 };
      if (etapa !== "all") params.etapa = etapa;
      if (origen !== "all") params.origen = origen;
      if (busqueda) params.busqueda = busqueda;
      return api.get("/leads", { params }).then((r) => r.data);
    },
  });

  const saveMutation = useMutation({
    mutationFn: (data: LeadForm & { id?: number }) => {
      const { id, ...body } = data;
      // Clean empty strings
      const cleaned = Object.fromEntries(
        Object.entries(body).filter(([, v]) => v !== "" && v !== undefined)
      );
      if (id) return api.put(`/leads/${id}`, cleaned);
      return api.post("/leads", cleaned);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leads"] });
      qc.invalidateQueries({ queryKey: ["leads-pipeline"] });
      setDialogOpen(false);
    },
  });

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setBusqueda(searchInput);
    setPage(1);
  };

  const handlePipelineClick = (stage: string) => {
    setEtapa(etapa === stage ? "all" : stage);
    setPage(1);
  };

  const openCreate = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    setDialogOpen(true);
  };

  const openEdit = (lead: Lead) => {
    setEditing(lead);
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
    setDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold">Prospectos</h1>
        </div>
        {isAdmin && (
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-2" /> Nuevo Prospecto
          </Button>
        )}
      </div>

      {/* Pipeline Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {pipeline.map((stage) => (
          <button
            key={stage.etapa}
            onClick={() => handlePipelineClick(stage.etapa)}
            className={`rounded-lg border p-3 text-left transition-all hover:shadow-md ${
              etapa === stage.etapa ? "ring-2 ring-primary" : ""
            } ${STAGE_COLORS[stage.etapa] || "bg-gray-50 border-gray-200"}`}
          >
            <p className="text-xs font-medium uppercase tracking-wide opacity-70">
              {ETAPAS.find((e) => e.value === stage.etapa)?.label || stage.etapa}
            </p>
            <p className="text-2xl font-bold mt-1">{stage.cantidad}</p>
            {stage.valor_total > 0 && (
              <p className="text-xs mt-0.5">
                ${stage.valor_total.toLocaleString()}
              </p>
            )}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder="Buscar nombre, telefono, empresa..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-72"
          />
          <Button type="submit" variant="outline" size="icon">
            <Search className="h-4 w-4" />
          </Button>
        </form>
        <Select
          value={etapa}
          onValueChange={(v) => { setEtapa(v); setPage(1); }}
        >
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ETAPAS.map((e) => (
              <SelectItem key={e.value} value={e.value}>{e.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={origen}
          onValueChange={(v) => { setOrigen(v); setPage(1); }}
        >
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ORIGENES.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Telefono</TableHead>
              <TableHead>Empresa</TableHead>
              <TableHead>Etapa</TableHead>
              <TableHead>Origen</TableHead>
              <TableHead>Ultimo Contacto</TableHead>
              <TableHead>Seguimiento</TableHead>
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
              data?.items.map((lead) => {
                const seguimientoVencido =
                  lead.proximo_seguimiento &&
                  new Date(lead.proximo_seguimiento) < new Date();
                return (
                  <TableRow
                    key={lead.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/leads/${lead.id}`)}
                  >
                    <TableCell className="font-medium">
                      {lead.nombre || "-"}
                    </TableCell>
                    <TableCell>{lead.telefono}</TableCell>
                    <TableCell>{lead.empresa || "-"}</TableCell>
                    <TableCell>
                      <LeadStageBadge stage={lead.etapa} />
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">
                        {ORIGEN_LABELS[lead.origen] || lead.origen}
                      </span>
                    </TableCell>
                    <TableCell>
                      {lead.ultimo_contacto
                        ? format(parseISO(lead.ultimo_contacto), "dd MMM HH:mm", { locale: es })
                        : "-"}
                    </TableCell>
                    <TableCell>
                      {lead.proximo_seguimiento ? (
                        <span
                          className={`text-sm ${
                            seguimientoVencido
                              ? "text-red-600 font-medium"
                              : "text-muted-foreground"
                          }`}
                        >
                          {format(parseISO(lead.proximo_seguimiento), "dd MMM HH:mm", { locale: es })}
                          {seguimientoVencido && " (vencido)"}
                        </span>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
            {!isLoading && data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No se encontraron prospectos
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {data?.total} prospectos en total
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm">
              Pagina {page} de {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Editar Prospecto" : "Nuevo Prospecto"}
            </DialogTitle>
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
                <Label>Telefono *</Label>
                <Input
                  value={form.telefono}
                  onChange={(e) => setForm({ ...form, telefono: e.target.value })}
                  placeholder="5212345678900"
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
                    {ETAPAS.filter((e) => e.value !== "all").map((e) => (
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
                    {ORIGENES.filter((o) => o.value !== "all").map((o) => (
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
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (editing) saveMutation.mutate({ ...form, id: editing.id });
                else saveMutation.mutate(form);
              }}
              disabled={saveMutation.isPending || !form.telefono}
            >
              {saveMutation.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
