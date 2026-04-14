import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Database,
  Plus,
  Search,
  MoreHorizontal,
  RefreshCw,
  Copy,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
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
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";
import type { Tenant, TenantForm } from "@/lib/types";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";

const planBadgeVariant: Record<string, "default" | "success" | "warning" | "destructive"> = {
  active: "success",
  trial: "warning",
  suspended: "destructive",
};

const planLabel: Record<string, string> = {
  active: "Activo",
  trial: "Prueba",
  suspended: "Suspendido",
};

const emptyForm: TenantForm = {
  nombre: "",
  slug: "",
  plan: "trial",
  max_conversations_per_day: 100,
  timezone: "America/Mexico_City",
};

export default function Tenants() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [form, setForm] = useState<TenantForm>(emptyForm);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [seedConfirmOpen, setSeedConfirmOpen] = useState(false);
  const [seedResult, setSeedResult] = useState<string | null>(null);

  const { data: tenants = [], isLoading } = useQuery<Tenant[]>({
    queryKey: ["tenants"],
    queryFn: () => api.get("/tenants").then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: TenantForm) => api.post("/tenants", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenants"] });
      setDialogOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<TenantForm & { activo?: boolean }> }) =>
      api.put(`/tenants/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenants"] });
      setDialogOpen(false);
    },
  });

  const regenTokenMutation = useMutation({
    mutationFn: (id: number) => api.post(`/tenants/${id}/regenerate-webhook-token`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenants"] }),
  });

  const seedDemoMutation = useMutation({
    mutationFn: (id: number) => api.post(`/tenants/${id}/seed-demo`),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["tenants"] });
      const d = res.data;
      setSeedResult(
        `${d.servicios_creados} servicios, ${d.estilistas_creados} estilistas, info y ${d.keywords_creados} keywords creados`
      );
    },
    onError: (err: any) => {
      setSeedResult(err.response?.data?.detail ?? "Error al cargar datos demo");
    },
  });

  const filtered = tenants.filter(
    (t) =>
      t.nombre.toLowerCase().includes(search.toLowerCase()) ||
      t.slug.toLowerCase().includes(search.toLowerCase())
  );

  const openCreate = () => {
    setEditingTenant(null);
    setForm(emptyForm);
    setShowAdvanced(false);
    setDialogOpen(true);
  };

  const openEdit = (tenant: Tenant) => {
    setEditingTenant(tenant);
    setForm({
      nombre: tenant.nombre,
      slug: tenant.slug,
      plan: tenant.plan,
      chatwoot_account_id: tenant.chatwoot_account_id,
      chatwoot_inbox_id: tenant.chatwoot_inbox_id,
      google_calendar_id: tenant.google_calendar_id ?? "",
      owner_phone: tenant.owner_phone ?? "",
      owner_email: tenant.owner_email ?? "",
      max_conversations_per_day: tenant.max_conversations_per_day,
      timezone: tenant.timezone,
    });
    setShowAdvanced(false);
    setDialogOpen(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingTenant) {
      updateMutation.mutate({ id: editingTenant.id, data: form });
    } else {
      createMutation.mutate(form);
    }
  };

  const toggleActive = (tenant: Tenant) => {
    updateMutation.mutate({ id: tenant.id, data: { activo: !tenant.activo } });
  };

  const copyWebhookUrl = (tenant: Tenant) => {
    const baseUrl = window.location.origin.replace("/admin", "");
    const url = `${baseUrl}/api/webhooks/chatwoot/${tenant.slug}?token=WEBHOOK_TOKEN`;
    navigator.clipboard.writeText(url);
  };

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tenants</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Gestiona los clientes y sus configuraciones
          </p>
        </div>
        <Button onClick={openCreate} size="sm" className="gap-2">
          <Plus className="h-4 w-4" />
          Nuevo Tenant
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar por nombre o slug..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tenant</TableHead>
                <TableHead>Plan</TableHead>
                <TableHead className="hidden md:table-cell">Propietario</TableHead>
                <TableHead className="hidden lg:table-cell">Conversaciones/día</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                    Cargando...
                  </TableCell>
                </TableRow>
              ) : filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12">
                    <Building2 className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2" />
                    <p className="text-muted-foreground">
                      {search ? "Sin resultados" : "No hay tenants"}
                    </p>
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((tenant) => (
                  <TableRow
                    key={tenant.id}
                    className="cursor-pointer hover:bg-secondary/50 transition-colors"
                    onClick={() => navigate(`/tenants/${tenant.id}`)}
                  >
                    <TableCell>
                      <div>
                        <p className="font-medium text-foreground">{tenant.nombre}</p>
                        <p className="text-xs text-muted-foreground font-mono">{tenant.slug}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={planBadgeVariant[tenant.plan] ?? "default"}>
                        {planLabel[tenant.plan] ?? tenant.plan}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <div className="text-sm">
                        {tenant.owner_email || tenant.owner_phone || (
                          <span className="text-muted-foreground/50">—</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      <span className="text-sm font-mono">{tenant.max_conversations_per_day}</span>
                    </TableCell>
                    <TableCell>
                      <div
                        className={`h-2 w-2 rounded-full ${tenant.activo ? "bg-emerald-500" : "bg-zinc-500"}`}
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground"
                        onClick={(e) => {
                          e.stopPropagation();
                          openEdit(tenant);
                        }}
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingTenant ? `Editar: ${editingTenant.nombre}` : "Nuevo Tenant"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Basic fields */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="nombre">Nombre</Label>
                <Input
                  id="nombre"
                  value={form.nombre}
                  onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                  placeholder="Mi Cliente"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="slug">Slug</Label>
                <Input
                  id="slug"
                  value={form.slug}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      slug: e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9-]/g, "-")
                        .replace(/-+/g, "-"),
                    })
                  }
                  placeholder="mi-cliente"
                  pattern="^[a-z0-9\-]+$"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Plan</Label>
                <Select
                  value={form.plan}
                  onValueChange={(v) => setForm({ ...form, plan: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="trial">Prueba</SelectItem>
                    <SelectItem value="active">Activo</SelectItem>
                    <SelectItem value="suspended">Suspendido</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="timezone">Zona horaria</Label>
                <Input
                  id="timezone"
                  value={form.timezone}
                  onChange={(e) => setForm({ ...form, timezone: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="owner_phone">Teléfono propietario</Label>
                <Input
                  id="owner_phone"
                  value={form.owner_phone ?? ""}
                  onChange={(e) => setForm({ ...form, owner_phone: e.target.value })}
                  placeholder="5212345678"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="owner_email">Email propietario</Label>
                <Input
                  id="owner_email"
                  type="email"
                  value={form.owner_email ?? ""}
                  onChange={(e) => setForm({ ...form, owner_email: e.target.value })}
                  placeholder="cliente@email.com"
                />
              </div>
            </div>

            {/* Webhook URL (edit mode) */}
            {editingTenant && (
              <div className="space-y-2">
                <Label>Webhook URL</Label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs bg-secondary/50 px-3 py-2 rounded-md text-muted-foreground overflow-x-auto">
                    /api/webhooks/chatwoot/{editingTenant.slug}?token=...
                  </code>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="shrink-0 h-8 w-8"
                    onClick={() => copyWebhookUrl(editingTenant)}
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="shrink-0 h-8 w-8"
                    onClick={() => regenTokenMutation.mutate(editingTenant.id)}
                    disabled={regenTokenMutation.isPending}
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${regenTokenMutation.isPending ? "animate-spin" : ""}`} />
                  </Button>
                </div>
              </div>
            )}

            {/* Seed demo data (edit mode) */}
            {editingTenant && (
              <div className="space-y-2">
                <Label>Datos demo</Label>
                <div className="flex items-center gap-2">
                  <p className="flex-1 text-xs text-muted-foreground">
                    Cargar servicios, estilistas e información de salón de belleza de ejemplo
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="shrink-0 gap-2"
                    onClick={(e) => {
                      e.preventDefault();
                      setSeedResult(null);
                      setSeedConfirmOpen(true);
                    }}
                    disabled={seedDemoMutation.isPending}
                  >
                    <Database className="h-3.5 w-3.5" />
                    {seedDemoMutation.isPending ? "Cargando..." : "Cargar datos demo"}
                  </Button>
                </div>
                {seedResult && (
                  <p className={`text-xs ${seedDemoMutation.isError ? "text-destructive" : "text-emerald-500"}`}>
                    {seedResult}
                  </p>
                )}
              </div>
            )}

            {/* Advanced toggle */}
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
            >
              <ExternalLink className="h-3 w-3" />
              {showAdvanced ? "Ocultar" : "Mostrar"} configuración avanzada
            </button>

            {showAdvanced && (
              <div className="space-y-4 pt-2 border-t border-border">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="chatwoot_account_id">Chatwoot Account ID</Label>
                    <Input
                      id="chatwoot_account_id"
                      type="number"
                      value={form.chatwoot_account_id ?? ""}
                      onChange={(e) =>
                        setForm({ ...form, chatwoot_account_id: e.target.value ? Number(e.target.value) : null })
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="chatwoot_inbox_id">Chatwoot Inbox ID</Label>
                    <Input
                      id="chatwoot_inbox_id"
                      type="number"
                      value={form.chatwoot_inbox_id ?? ""}
                      onChange={(e) =>
                        setForm({ ...form, chatwoot_inbox_id: e.target.value ? Number(e.target.value) : null })
                      }
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="chatwoot_api_token">Chatwoot API Token</Label>
                  <Input
                    id="chatwoot_api_token"
                    value={form.chatwoot_api_token ?? ""}
                    onChange={(e) => setForm({ ...form, chatwoot_api_token: e.target.value })}
                    placeholder="Token de API de Chatwoot"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="google_calendar_id">Google Calendar ID</Label>
                    <Input
                      id="google_calendar_id"
                      value={form.google_calendar_id ?? ""}
                      onChange={(e) => setForm({ ...form, google_calendar_id: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="max_conversations_per_day">Máx. conversaciones/día</Label>
                    <Input
                      id="max_conversations_per_day"
                      type="number"
                      min={1}
                      value={form.max_conversations_per_day ?? 100}
                      onChange={(e) =>
                        setForm({ ...form, max_conversations_per_day: Number(e.target.value) })
                      }
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="system_prompt_override">System Prompt Override</Label>
                  <Textarea
                    id="system_prompt_override"
                    value={form.system_prompt_override ?? ""}
                    onChange={(e) => setForm({ ...form, system_prompt_override: e.target.value })}
                    placeholder="Deja vacío para usar el prompt default..."
                    rows={4}
                  />
                </div>
              </div>
            )}

            {/* Active toggle (edit mode) */}
            {editingTenant && (
              <div className="flex items-center justify-between pt-2 border-t border-border">
                <Label>Tenant activo</Label>
                <Switch
                  checked={editingTenant.activo}
                  onCheckedChange={() => toggleActive(editingTenant)}
                />
              </div>
            )}

            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setDialogOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? "Guardando..." : editingTenant ? "Guardar" : "Crear"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={seedConfirmOpen}
        onOpenChange={setSeedConfirmOpen}
        title="Cargar datos demo"
        description={`Se crearán servicios, estilistas, información del salón y keywords de ejemplo para "${editingTenant?.nombre}". Esta acción solo funciona si el tenant no tiene datos existentes.`}
        onConfirm={() => {
          if (editingTenant) {
            seedDemoMutation.mutate(editingTenant.id);
          }
          setSeedConfirmOpen(false);
        }}
        confirmLabel="Cargar datos"
      />
    </div>
  );
}
