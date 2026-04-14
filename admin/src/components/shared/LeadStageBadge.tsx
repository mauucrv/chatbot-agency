import { Badge } from "@/components/ui/badge";

const stageConfig: Record<string, { label: string; className: string }> = {
  nuevo: { label: "Nuevo", className: "bg-blue-100 text-blue-800" },
  contactado: { label: "Contactado", className: "bg-yellow-100 text-yellow-800" },
  cita_agendada: { label: "Cita Agendada", className: "bg-purple-100 text-purple-800" },
  en_negociacion: { label: "En Negociacion", className: "bg-orange-100 text-orange-800" },
  cerrado_ganado: { label: "Cerrado Ganado", className: "bg-emerald-100 text-emerald-800" },
  cerrado_perdido: { label: "Cerrado Perdido", className: "bg-red-100 text-red-800" },
};

export function LeadStageBadge({ stage }: { stage: string }) {
  const config = stageConfig[stage] || { label: stage, className: "bg-gray-100 text-gray-800" };
  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  );
}
