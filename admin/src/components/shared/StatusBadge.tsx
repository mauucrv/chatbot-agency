import { Badge } from "@/components/ui/badge";

const statusConfig: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" }> = {
  pendiente: { label: "Pendiente", variant: "warning" },
  confirmada: { label: "Confirmada", variant: "default" },
  en_progreso: { label: "En Progreso", variant: "secondary" },
  completada: { label: "Completada", variant: "success" },
  cancelada: { label: "Cancelada", variant: "destructive" },
  no_asistio: { label: "No Asistio", variant: "outline" },
};

export function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || { label: status, variant: "outline" as const };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
