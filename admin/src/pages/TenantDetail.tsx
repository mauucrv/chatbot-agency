import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CreditCard,
  BarChart3,
  MessageSquare,
  Mic,
  Image,
  Cpu,
  Users,
  Calendar,
  AlertTriangle,
  PhoneForwarded,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";
import type { Tenant, TenantUsageResponse, ConfirmPaymentResponse } from "@/lib/types";
import { format, parseISO, formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";

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

export default function TenantDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [paymentMonths, setPaymentMonths] = useState(1);
  const [paymentNotes, setPaymentNotes] = useState("");
  const [usageDays, setUsageDays] = useState(30);

  const { data: tenant, isLoading: loadingTenant } = useQuery<Tenant>({
    queryKey: ["tenant", id],
    queryFn: () => api.get(`/tenants/${id}`).then((r) => r.data),
  });

  const { data: usage, isLoading: loadingUsage } = useQuery<TenantUsageResponse>({
    queryKey: ["tenant-usage", id, usageDays],
    queryFn: () => api.get(`/tenants/${id}/usage?dias=${usageDays}`).then((r) => r.data),
  });

  const paymentMutation = useMutation<{ data: ConfirmPaymentResponse }>({
    mutationFn: () =>
      api.post(`/tenants/${id}/confirm-payment`, {
        months: paymentMonths,
        notes: paymentNotes || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant", id] });
      queryClient.invalidateQueries({ queryKey: ["tenants"] });
      setPaymentOpen(false);
      setPaymentMonths(1);
      setPaymentNotes("");
    },
  });

  if (loadingTenant || !tenant) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const expiresAt = tenant.subscription_expires_at
    ? parseISO(tenant.subscription_expires_at)
    : null;
  const isExpired = expiresAt ? expiresAt < new Date() : false;
  const trialEnds = tenant.trial_ends_at ? parseISO(tenant.trial_ends_at) : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/tenants")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{tenant.nombre}</h1>
            <Badge variant={planBadgeVariant[tenant.plan] ?? "default"}>
              {planLabel[tenant.plan] ?? tenant.plan}
            </Badge>
            <div
              className={`h-2 w-2 rounded-full ${tenant.activo ? "bg-emerald-500" : "bg-zinc-500"}`}
            />
          </div>
          <p className="text-sm text-muted-foreground font-mono mt-1">{tenant.slug}</p>
        </div>
      </div>

      <Tabs defaultValue="billing">
        <TabsList>
          <TabsTrigger value="billing" className="gap-2">
            <CreditCard className="h-4 w-4" />
            Billing
          </TabsTrigger>
          <TabsTrigger value="usage" className="gap-2">
            <BarChart3 className="h-4 w-4" />
            Uso
          </TabsTrigger>
        </TabsList>

        {/* ── Billing Tab ── */}
        <TabsContent value="billing" className="space-y-6 mt-6">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {/* Plan Status */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Plan
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Badge
                  variant={planBadgeVariant[tenant.plan] ?? "default"}
                  className="text-lg px-3 py-1"
                >
                  {planLabel[tenant.plan] ?? tenant.plan}
                </Badge>
              </CardContent>
            </Card>

            {/* Subscription Expiry */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {tenant.plan === "trial" ? "Fin de prueba" : "Vencimiento suscripción"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {tenant.plan === "trial" && trialEnds ? (
                  <div>
                    <p className="text-xl font-semibold">
                      {format(trialEnds, "dd MMM yyyy", { locale: es })}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {trialEnds < new Date()
                        ? "Prueba vencida"
                        : formatDistanceToNow(trialEnds, { locale: es, addSuffix: true })}
                    </p>
                  </div>
                ) : expiresAt ? (
                  <div>
                    <p className={`text-xl font-semibold ${isExpired ? "text-destructive" : ""}`}>
                      {format(expiresAt, "dd MMM yyyy", { locale: es })}
                    </p>
                    <p className={`text-xs mt-1 ${isExpired ? "text-destructive" : "text-muted-foreground"}`}>
                      {isExpired
                        ? "Suscripción vencida"
                        : formatDistanceToNow(expiresAt, { locale: es, addSuffix: true })}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Sin fecha</p>
                )}
              </CardContent>
            </Card>

            {/* Last Payment */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Último pago
                </CardTitle>
              </CardHeader>
              <CardContent>
                {tenant.last_payment_at ? (
                  <div>
                    <p className="text-xl font-semibold">
                      {format(parseISO(tenant.last_payment_at), "dd MMM yyyy", { locale: es })}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatDistanceToNow(parseISO(tenant.last_payment_at), {
                        locale: es,
                        addSuffix: true,
                      })}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Sin pagos registrados</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Confirm Payment Button */}
          <Button onClick={() => setPaymentOpen(true)} className="gap-2">
            <CreditCard className="h-4 w-4" />
            Registrar pago
          </Button>

          {/* Payment Notes */}
          {tenant.payment_notes && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Historial de pagos</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-sm text-muted-foreground whitespace-pre-wrap font-mono">
                  {tenant.payment_notes}
                </pre>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ── Usage Tab ── */}
        <TabsContent value="usage" className="space-y-6 mt-6">
          {/* Period selector */}
          <div className="flex items-center gap-2">
            <Label className="text-sm">Periodo:</Label>
            {[7, 30, 60, 90].map((d) => (
              <Button
                key={d}
                variant={usageDays === d ? "default" : "outline"}
                size="sm"
                onClick={() => setUsageDays(d)}
              >
                {d}d
              </Button>
            ))}
          </div>

          {loadingUsage || !usage ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
            </div>
          ) : (
            <>
              {/* Summary Cards */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">Mensajes</p>
                        <p className="text-2xl font-bold">{usage.total_mensajes_recibidos.toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">{usage.total_mensajes_respondidos.toLocaleString()} respondidos</p>
                      </div>
                      <div className="h-10 w-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                        <MessageSquare className="h-5 w-5 text-blue-500" />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">Tokens OpenAI</p>
                        <p className="text-2xl font-bold">{usage.total_tokens_openai_aprox.toLocaleString()}</p>
                      </div>
                      <div className="h-10 w-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                        <Cpu className="h-5 w-5 text-purple-500" />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">Media</p>
                        <p className="text-2xl font-bold">
                          {usage.total_mensajes_audio + usage.total_mensajes_imagen}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {usage.total_mensajes_audio} audio, {usage.total_mensajes_imagen} imagen
                        </p>
                      </div>
                      <div className="h-10 w-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
                        <Mic className="h-5 w-5 text-amber-500" />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">Citas creadas</p>
                        <p className="text-2xl font-bold">{usage.total_citas_creadas}</p>
                        <p className="text-xs text-muted-foreground">
                          {usage.total_transferencias_humano} handoffs
                        </p>
                      </div>
                      <div className="h-10 w-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                        <Calendar className="h-5 w-5 text-emerald-500" />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Extra stats row */}
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardContent className="p-5 flex items-center gap-4">
                    <div className="h-10 w-10 rounded-lg bg-cyan-500/10 flex items-center justify-center">
                      <Users className="h-5 w-5 text-cyan-500" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Conversaciones activas</p>
                      <p className="text-xl font-bold">{usage.conversaciones_activas}</p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-5 flex items-center gap-4">
                    <div className="h-10 w-10 rounded-lg bg-rose-500/10 flex items-center justify-center">
                      <AlertTriangle className="h-5 w-5 text-rose-500" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Errores</p>
                      <p className="text-xl font-bold">{usage.total_errores}</p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-5 flex items-center gap-4">
                    <div className="h-10 w-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
                      <Clock className="h-5 w-5 text-indigo-500" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Tiempo promedio</p>
                      <p className="text-xl font-bold">
                        {usage.promedio_respuesta_ms
                          ? `${(usage.promedio_respuesta_ms / 1000).toFixed(1)}s`
                          : "—"}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Daily detail table */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">Detalle diario</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Fecha</TableHead>
                          <TableHead className="text-right">Mensajes</TableHead>
                          <TableHead className="text-right hidden sm:table-cell">Audio</TableHead>
                          <TableHead className="text-right hidden sm:table-cell">Imagen</TableHead>
                          <TableHead className="text-right">Tokens</TableHead>
                          <TableHead className="text-right hidden md:table-cell">Usuarios</TableHead>
                          <TableHead className="text-right hidden md:table-cell">Citas</TableHead>
                          <TableHead className="text-right hidden lg:table-cell">Errores</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {usage.detalle_diario.length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                              Sin datos en este periodo
                            </TableCell>
                          </TableRow>
                        ) : (
                          usage.detalle_diario.map((d) => (
                            <TableRow key={d.fecha}>
                              <TableCell className="font-mono text-sm">
                                {format(parseISO(d.fecha), "dd MMM", { locale: es })}
                              </TableCell>
                              <TableCell className="text-right font-mono">
                                {d.mensajes_recibidos}
                              </TableCell>
                              <TableCell className="text-right font-mono hidden sm:table-cell">
                                {d.mensajes_audio}
                              </TableCell>
                              <TableCell className="text-right font-mono hidden sm:table-cell">
                                {d.mensajes_imagen}
                              </TableCell>
                              <TableCell className="text-right font-mono">
                                {d.tokens_openai_aprox.toLocaleString()}
                              </TableCell>
                              <TableCell className="text-right font-mono hidden md:table-cell">
                                {d.usuarios_unicos}
                              </TableCell>
                              <TableCell className="text-right font-mono hidden md:table-cell">
                                {d.citas_creadas}
                              </TableCell>
                              <TableCell className="text-right font-mono hidden lg:table-cell">
                                {d.errores > 0 ? (
                                  <span className="text-destructive">{d.errores}</span>
                                ) : (
                                  "0"
                                )}
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>

      {/* Payment Dialog */}
      <Dialog open={paymentOpen} onOpenChange={setPaymentOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Registrar pago — {tenant.nombre}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="months">Meses a extender</Label>
              <Input
                id="months"
                type="number"
                min={1}
                max={12}
                value={paymentMonths}
                onChange={(e) => setPaymentMonths(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notas (opcional)</Label>
              <Textarea
                id="notes"
                value={paymentNotes}
                onChange={(e) => setPaymentNotes(e.target.value)}
                placeholder="Ej: Pago por transferencia BBVA"
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPaymentOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => paymentMutation.mutate()}
              disabled={paymentMutation.isPending}
            >
              {paymentMutation.isPending ? "Procesando..." : "Confirmar pago"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
