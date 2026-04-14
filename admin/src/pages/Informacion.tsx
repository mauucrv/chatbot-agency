import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Save, Plus, Trash2 } from "lucide-react";
import api from "@/lib/api";
import type { SalonInfo, Keyword } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function Informacion() {
  const qc = useQueryClient();

  // Salon Info
  const { data: info } = useQuery<SalonInfo | null>({
    queryKey: ["salon-info"],
    queryFn: () => api.get("/info").then((r) => r.data),
  });

  const [form, setForm] = useState({
    nombre_salon: "",
    direccion: "",
    telefono: "",
    horario: "",
    descripcion: "",
    politicas: "",
    redes_sociales: {} as Record<string, string>,
  });
  const [infoInitialized, setInfoInitialized] = useState(false);

  useEffect(() => {
    if (info && !infoInitialized) {
      setForm({
        nombre_salon: info.nombre_salon || "",
        direccion: info.direccion || "",
        telefono: info.telefono || "",
        horario: info.horario || "",
        descripcion: info.descripcion || "",
        politicas: info.politicas || "",
        redes_sociales: info.redes_sociales || {},
      });
      setInfoInitialized(true);
    }
  }, [info, infoInitialized]);

  const saveInfoMutation = useMutation({
    mutationFn: () => api.put("/info", form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["salon-info"] }),
  });

  // Keywords
  const { data: keywords = [] } = useQuery<Keyword[]>({
    queryKey: ["keywords"],
    queryFn: () => api.get("/info/keywords").then((r) => r.data),
  });

  const [newKeyword, setNewKeyword] = useState("");

  const addKeywordMutation = useMutation({
    mutationFn: (keyword: string) =>
      api.post("/info/keywords", { keyword }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["keywords"] });
      setNewKeyword("");
    },
  });

  const toggleKeywordMutation = useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) =>
      api.put(`/info/keywords/${id}`, null, { params: { activo } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keywords"] }),
  });

  const deleteKeywordMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/info/keywords/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keywords"] }),
  });

  // Social media helper
  const [socialKey, setSocialKey] = useState("");
  const [socialVal, setSocialVal] = useState("");

  const addSocial = () => {
    if (socialKey.trim() && socialVal.trim()) {
      setForm({
        ...form,
        redes_sociales: {
          ...form.redes_sociales,
          [socialKey.trim().toLowerCase()]: socialVal.trim(),
        },
      });
      setSocialKey("");
      setSocialVal("");
    }
  };

  const removeSocial = (key: string) => {
    const updated = { ...form.redes_sociales };
    delete updated[key];
    setForm({ ...form, redes_sociales: updated });
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Informacion del Negocio</h1>

      {/* Salon Info Form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Datos Generales</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Nombre del Salon</Label>
            <Input
              value={form.nombre_salon}
              onChange={(e) => setForm({ ...form, nombre_salon: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Telefono</Label>
              <Input
                value={form.telefono}
                onChange={(e) => setForm({ ...form, telefono: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Horario</Label>
              <Input
                value={form.horario}
                onChange={(e) => setForm({ ...form, horario: e.target.value })}
                placeholder="L-S 9:00-20:00"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Direccion</Label>
            <Input
              value={form.direccion}
              onChange={(e) => setForm({ ...form, direccion: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>Descripcion</Label>
            <Textarea
              value={form.descripcion}
              onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
              rows={3}
            />
          </div>
          <div className="space-y-2">
            <Label>Politicas</Label>
            <Textarea
              value={form.politicas}
              onChange={(e) => setForm({ ...form, politicas: e.target.value })}
              rows={3}
            />
          </div>

          {/* Social Media */}
          <div className="space-y-2">
            <Label>Redes Sociales</Label>
            <div className="flex flex-wrap gap-2 mb-2">
              {Object.entries(form.redes_sociales).map(([k, v]) => (
                <Badge
                  key={k}
                  variant="secondary"
                  className="cursor-pointer"
                  onClick={() => removeSocial(k)}
                >
                  {k}: {v} &times;
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                placeholder="Red social"
                value={socialKey}
                onChange={(e) => setSocialKey(e.target.value)}
                className="w-32"
              />
              <Input
                placeholder="URL o usuario"
                value={socialVal}
                onChange={(e) => setSocialVal(e.target.value)}
              />
              <Button type="button" variant="outline" onClick={addSocial}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <Button
            onClick={() => saveInfoMutation.mutate()}
            disabled={saveInfoMutation.isPending}
          >
            <Save className="h-4 w-4 mr-2" />
            {saveInfoMutation.isPending ? "Guardando..." : "Guardar Informacion"}
          </Button>
          {saveInfoMutation.isSuccess && (
            <p className="text-sm text-emerald-600 mt-2">Guardado correctamente</p>
          )}
        </CardContent>
      </Card>

      {/* Keywords */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Keywords de Transferencia Humana</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Nueva keyword..."
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && newKeyword.trim()) {
                  e.preventDefault();
                  addKeywordMutation.mutate(newKeyword.trim());
                }
              }}
            />
            <Button
              variant="outline"
              onClick={() =>
                newKeyword.trim() && addKeywordMutation.mutate(newKeyword.trim())
              }
              disabled={addKeywordMutation.isPending}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Keyword</TableHead>
                <TableHead>Activa</TableHead>
                <TableHead className="w-[60px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {keywords.map((kw) => (
                <TableRow key={kw.id}>
                  <TableCell className="font-medium">{kw.keyword}</TableCell>
                  <TableCell>
                    <Switch
                      checked={kw.activo}
                      onCheckedChange={(checked) =>
                        toggleKeywordMutation.mutate({ id: kw.id, activo: checked })
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => deleteKeywordMutation.mutate(kw.id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {keywords.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-muted-foreground py-6">
                    No hay keywords registradas
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
