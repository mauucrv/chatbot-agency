import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Appointment, Stylist } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const ESTADOS = [
  "pendiente",
  "confirmada",
  "en_progreso",
  "completada",
  "cancelada",
  "no_asistio",
];

export default function CitaDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const qc = useQueryClient();

  const { data: cita, isLoading } = useQuery<Appointment>({
    queryKey: ["appointment", id],
    queryFn: () => api.get(`/citas/${id}`).then((r) => r.data),
  });

  const { data: stylists = [] } = useQuery<Stylist[]>({
    queryKey: ["stylists"],
    queryFn: () => api.get("/estilistas").then((r) => r.data),
  });

  const statusMutation = useMutation({
    mutationFn: (estado: string) =>
      api.patch(`/citas/${id}/estado`, null, { params: { estado } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointment", id] });
      qc.invalidateQueries({ queryKey: ["appointments"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/citas/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointments"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      navigate("/citas");
    },
  });

  const stylistMap = new Map(stylists.map((s) => [s.id, s.nombre]));

  if (isLoading || !cita) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/citas")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-2xl font-bold">Cita #{cita.id}</h1>
        <StatusBadge status={cita.estado} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Detalles</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Cliente</p>
              <p className="font-medium">{cita.nombre_cliente}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Telefono</p>
              <p className="font-medium">{cita.telefono_cliente}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Inicio</p>
              <p className="font-medium">
                {format(parseISO(cita.inicio), "dd MMM yyyy HH:mm", { locale: es })}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Fin</p>
              <p className="font-medium">
                {format(parseISO(cita.fin), "dd MMM yyyy HH:mm", { locale: es })}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Estilista</p>
              <p className="font-medium">
                {cita.estilista_id
                  ? stylistMap.get(cita.estilista_id) || `#${cita.estilista_id}`
                  : "Sin asignar"}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Precio Total</p>
              <p className="font-medium text-lg">${cita.precio_total.toLocaleString()}</p>
            </div>
          </div>

          <Separator />

          <div>
            <p className="text-sm text-muted-foreground mb-2">Servicios</p>
            <div className="flex flex-wrap gap-2">
              {cita.servicios.map((s) => (
                <Badge key={s} variant="secondary">
                  {s}
                </Badge>
              ))}
            </div>
          </div>

          {cita.notas && (
            <>
              <Separator />
              <div>
                <p className="text-sm text-muted-foreground mb-1">Notas</p>
                <p className="text-sm">{cita.notas}</p>
              </div>
            </>
          )}

          {isAdmin && (
            <>
              <Separator />

              <div>
                <p className="text-sm text-muted-foreground mb-2">Cambiar Estado</p>
                <div className="flex gap-3">
                  <Select
                    value={cita.estado}
                    onValueChange={(v) => statusMutation.mutate(v)}
                  >
                    <SelectTrigger className="w-48">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ESTADOS.map((e) => (
                        <SelectItem key={e} value={e}>
                          {e.charAt(0).toUpperCase() + e.slice(1).replace("_", " ")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Separator />

              <div className="flex justify-end">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    if (confirm("Eliminar esta cita?")) deleteMutation.mutate();
                  }}
                >
                  Eliminar Cita
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
