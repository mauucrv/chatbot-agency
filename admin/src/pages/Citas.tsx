import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import api from "@/lib/api";
import type { PaginatedAppointments, Stylist } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { StatusBadge } from "@/components/shared/StatusBadge";

const ESTADOS = [
  { value: "all", label: "Todos" },
  { value: "pendiente", label: "Pendiente" },
  { value: "confirmada", label: "Confirmada" },
  { value: "en_progreso", label: "En Progreso" },
  { value: "completada", label: "Completada" },
  { value: "cancelada", label: "Cancelada" },
  { value: "no_asistio", label: "No Asistio" },
];

export default function Citas() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [estado, setEstado] = useState("all");
  const [busqueda, setBusqueda] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const { data: stylists = [] } = useQuery<Stylist[]>({
    queryKey: ["stylists"],
    queryFn: () => api.get("/estilistas").then((r) => r.data),
  });

  const { data, isLoading } = useQuery<PaginatedAppointments>({
    queryKey: ["appointments", page, estado, busqueda],
    queryFn: () => {
      const params: Record<string, string | number> = { page, page_size: 20 };
      if (estado !== "all") params.estado = estado;
      if (busqueda) params.busqueda = busqueda;
      return api.get("/citas", { params }).then((r) => r.data);
    },
  });

  const stylistMap = new Map(stylists.map((s) => [s.id, s.nombre]));
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setBusqueda(searchInput);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Citas</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder="Buscar cliente o telefono..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-64"
          />
          <Button type="submit" variant="outline" size="icon">
            <Search className="h-4 w-4" />
          </Button>
        </form>
        <Select
          value={estado}
          onValueChange={(v) => {
            setEstado(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            {ESTADOS.map((e) => (
              <SelectItem key={e.value} value={e.value}>
                {e.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Cliente</TableHead>
              <TableHead>Telefono</TableHead>
              <TableHead>Fecha/Hora</TableHead>
              <TableHead>Consultor</TableHead>
              <TableHead>Servicios</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Estado</TableHead>
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
              data?.items.map((cita) => (
                <TableRow
                  key={cita.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/citas/${cita.id}`)}
                >
                  <TableCell className="font-medium">
                    {cita.nombre_cliente}
                  </TableCell>
                  <TableCell>{cita.telefono_cliente}</TableCell>
                  <TableCell>
                    {format(parseISO(cita.inicio), "dd MMM yyyy HH:mm", {
                      locale: es,
                    })}
                  </TableCell>
                  <TableCell>
                    {cita.estilista_id
                      ? stylistMap.get(cita.estilista_id) || `#${cita.estilista_id}`
                      : "-"}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">
                      {cita.servicios.join(", ")}
                    </span>
                  </TableCell>
                  <TableCell>${cita.precio_total.toLocaleString()}</TableCell>
                  <TableCell>
                    <StatusBadge status={cita.estado} />
                  </TableCell>
                </TableRow>
              ))
            )}
            {!isLoading && data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No se encontraron citas
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
            {data?.total} citas en total
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
    </div>
  );
}
