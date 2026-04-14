import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Save } from "lucide-react";
import api from "@/lib/api";
import type { Stylist } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const DAYS = [
  { value: "lunes", label: "Lunes" },
  { value: "martes", label: "Martes" },
  { value: "miercoles", label: "Miercoles" },
  { value: "jueves", label: "Jueves" },
  { value: "viernes", label: "Viernes" },
  { value: "sabado", label: "Sabado" },
  { value: "domingo", label: "Domingo" },
];

interface ScheduleRow {
  dia: string;
  hora_inicio: string;
  hora_fin: string;
}

export default function EstilistaDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [schedules, setSchedules] = useState<ScheduleRow[]>([]);
  const [initialized, setInitialized] = useState(false);

  const { data: stylist, isLoading } = useQuery<Stylist>({
    queryKey: ["stylist", id],
    queryFn: () => api.get(`/estilistas/${id}`).then((r) => r.data),
  });

  // Init schedules from fetched data
  if (stylist && !initialized) {
    const existing =
      stylist.horarios?.map((h) => ({
        dia: h.dia,
        hora_inicio: h.hora_inicio,
        hora_fin: h.hora_fin,
      })) || [];
    setSchedules(existing.length > 0 ? existing : [{ dia: "lunes", hora_inicio: "09:00", hora_fin: "20:00" }]);
    setInitialized(true);
  }

  const saveMutation = useMutation({
    mutationFn: (data: ScheduleRow[]) =>
      api.put(`/estilistas/${id}/horarios`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stylist", id] });
      qc.invalidateQueries({ queryKey: ["stylists"] });
    },
  });

  const addRow = () => {
    setSchedules([...schedules, { dia: "lunes", hora_inicio: "09:00", hora_fin: "20:00" }]);
  };

  const removeRow = (idx: number) => {
    setSchedules(schedules.filter((_, i) => i !== idx));
  };

  const updateRow = (idx: number, field: keyof ScheduleRow, value: string) => {
    const updated = [...schedules];
    updated[idx] = { ...updated[idx], [field]: value };
    setSchedules(updated);
  };

  if (isLoading || !stylist) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/consultores")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-2xl font-bold">Disponibilidad de {stylist.nombre}</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Horario Semanal</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {schedules.map((row, idx) => (
            <div key={idx} className="flex items-end gap-3">
              <div className="flex-1">
                <Label className="text-xs">Dia</Label>
                <Select
                  value={row.dia}
                  onValueChange={(v) => updateRow(idx, "dia", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DAYS.map((d) => (
                      <SelectItem key={d.value} value={d.value}>
                        {d.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="w-32">
                <Label className="text-xs">Inicio</Label>
                <Input
                  type="time"
                  value={row.hora_inicio}
                  onChange={(e) => updateRow(idx, "hora_inicio", e.target.value)}
                />
              </div>
              <div className="w-32">
                <Label className="text-xs">Fin</Label>
                <Input
                  type="time"
                  value={row.hora_fin}
                  onChange={(e) => updateRow(idx, "hora_fin", e.target.value)}
                />
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive"
                onClick={() => removeRow(idx)}
              >
                Quitar
              </Button>
            </div>
          ))}

          <div className="flex gap-3 pt-4">
            <Button variant="outline" onClick={addRow}>
              Agregar Horario
            </Button>
            <Button
              onClick={() => saveMutation.mutate(schedules)}
              disabled={saveMutation.isPending}
            >
              <Save className="h-4 w-4 mr-2" />
              {saveMutation.isPending ? "Guardando..." : "Guardar Horarios"}
            </Button>
          </div>

          {saveMutation.isSuccess && (
            <p className="text-sm text-emerald-600">Horarios guardados correctamente</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
