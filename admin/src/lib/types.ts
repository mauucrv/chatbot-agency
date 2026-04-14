// ============================================================
// Tenants
// ============================================================

export interface Tenant {
  id: number;
  nombre: string;
  slug: string;
  plan: "trial" | "active" | "suspended";
  chatwoot_account_id: number | null;
  chatwoot_inbox_id: number | null;
  google_calendar_id: string | null;
  owner_phone: string | null;
  owner_email: string | null;
  max_conversations_per_day: number;
  timezone: string;
  activo: boolean;
  trial_ends_at: string | null;
  subscription_expires_at: string | null;
  last_payment_at: string | null;
  payment_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DailyUsageDetail {
  fecha: string;
  mensajes_recibidos: number;
  mensajes_respondidos: number;
  mensajes_audio: number;
  mensajes_imagen: number;
  usuarios_unicos: number;
  tokens_openai_aprox: number;
  citas_creadas: number;
  errores: number;
}

export interface TenantUsageResponse {
  tenant_id: number;
  tenant_nombre: string;
  periodo: string;
  total_mensajes_recibidos: number;
  total_mensajes_respondidos: number;
  total_mensajes_audio: number;
  total_mensajes_imagen: number;
  total_tokens_openai_aprox: number;
  total_citas_creadas: number;
  total_transferencias_humano: number;
  total_errores: number;
  promedio_respuesta_ms: number | null;
  conversaciones_activas: number;
  detalle_diario: DailyUsageDetail[];
}

export interface ConfirmPaymentResponse {
  message: string;
  tenant_id: number;
  plan: string;
  subscription_expires_at: string;
  last_payment_at: string;
}

export interface TenantForm {
  nombre: string;
  slug: string;
  plan?: string;
  chatwoot_account_id?: number | null;
  chatwoot_inbox_id?: number | null;
  chatwoot_api_token?: string;
  google_calendar_id?: string;
  owner_phone?: string;
  owner_email?: string;
  system_prompt_override?: string;
  max_conversations_per_day?: number;
  timezone?: string;
}

export interface Service {
  id: number;
  servicio: string;
  descripcion: string | null;
  precio: number;
  duracion_minutos: number;
  estilistas_disponibles: string[] | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}

export interface ServiceForm {
  servicio: string;
  descripcion?: string;
  precio: number;
  duracion_minutos: number;
  estilistas_disponibles?: string[];
}

export interface StylistSchedule {
  id: number;
  estilista_id: number;
  dia: string;
  hora_inicio: string;
  hora_fin: string;
  activo: boolean;
}

export interface Stylist {
  id: number;
  nombre: string;
  telefono: string | null;
  email: string | null;
  especialidades: string[] | null;
  activo: boolean;
  horarios: StylistSchedule[] | null;
  created_at: string;
  updated_at: string;
}

export interface StylistForm {
  nombre: string;
  telefono?: string;
  email?: string;
  especialidades?: string[];
}

export interface Appointment {
  id: number;
  nombre_cliente: string;
  telefono_cliente: string;
  inicio: string;
  fin: string;
  servicios: string[];
  precio_total: number;
  estilista_id: number | null;
  id_evento_google: string | null;
  estado: string;
  notas: string | null;
  recordatorio_enviado: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaginatedAppointments {
  items: Appointment[];
  total: number;
  page: number;
  page_size: number;
}

export interface SalonInfo {
  id: number;
  nombre_salon: string;
  direccion: string | null;
  telefono: string | null;
  horario: string | null;
  descripcion: string | null;
  redes_sociales: Record<string, string> | null;
  politicas: string | null;
  updated_at: string;
}

export interface Keyword {
  id: number;
  keyword: string;
  activo: boolean;
}

export interface UsageResumen {
  mensajes_mes: number;
  mensajes_audio_mes: number;
  mensajes_imagen_mes: number;
  tokens_openai_mes: number;
  usuarios_unicos_hoy: number;
}

export interface DashboardMetrics {
  citas_hoy: number;
  citas_pendientes: number;
  citas_completadas_hoy: number;
  ingresos_hoy: number;
  total_servicios: number;
  total_estilistas: number;
  mensajes_hoy: number;
  errores_hoy: number;
  total_leads: number;
  leads_nuevos_hoy: number;
  leads_en_pipeline: number;
  seguimientos_pendientes: number;
  uso: UsageResumen;
  citas_semana: { fecha: string; cantidad: number }[];
  citas_recientes: {
    id: number;
    nombre_cliente: string;
    inicio: string;
    estado: string;
    servicios: string[];
    precio_total: number;
  }[];
}

// CRM Lead types
export interface Lead {
  id: number;
  nombre: string | null;
  telefono: string;
  email: string | null;
  empresa: string | null;
  etapa: string;
  origen: string;
  notas: string | null;
  valor_estimado: number | null;
  servicio_interes: string | null;
  chatwoot_conversation_id: number | null;
  chatwoot_contact_id: number | null;
  ultimo_contacto: string | null;
  proximo_seguimiento: string | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}

export interface LeadForm {
  nombre?: string;
  telefono: string;
  email?: string;
  empresa?: string;
  etapa?: string;
  origen?: string;
  notas?: string;
  valor_estimado?: number;
  servicio_interes?: string;
  proximo_seguimiento?: string;
}

export interface PaginatedLeads {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
}

export interface PipelineStage {
  etapa: string;
  cantidad: number;
  valor_total: number;
}

export interface DailyStatistic {
  fecha: string;
  mensajes_recibidos: number;
  mensajes_respondidos: number;
  citas_creadas: number;
  citas_modificadas: number;
  citas_canceladas: number;
  transferencias_humano: number;
  errores: number;
  tiempo_respuesta_promedio_ms: number | null;
}

export interface StatsOverview {
  daily_stats: DailyStatistic[];
  servicios_populares: { servicio: string; cantidad: number }[];
  citas_por_estado: { estado: string; cantidad: number }[];
  citas_por_estilista: { estilista: string; cantidad: number }[];
  tasa_completadas: number;
  tasa_canceladas: number;
}

export interface TrendPoint {
  fecha: string;
  valor: number;
}

// ============================================================
// Fichas Clientes
// ============================================================

export interface FichaCliente {
  id: number;
  nombre: string;
  telefono: string;
  email: string | null;
  tipo_cabello: string | null;
  tipo_piel: string | null;
  alergias: string | null;
  historial_color: { fecha: string; descripcion: string; estilista?: string }[] | null;
  historial_tratamientos: { fecha: string; descripcion: string; estilista?: string }[] | null;
  preferencias: string | null;
  notas: string | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}

export interface FichaClienteForm {
  nombre: string;
  telefono: string;
  email?: string;
  tipo_cabello?: string;
  tipo_piel?: string;
  alergias?: string;
  preferencias?: string;
  notas?: string;
}

export interface PaginatedFichas {
  items: FichaCliente[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// Inventario
// ============================================================

export interface Producto {
  id: number;
  nombre: string;
  marca: string | null;
  categoria: "reventa" | "uso_salon";
  subcategoria: string | null;
  cantidad: number;
  unidad: string | null;
  costo_unitario: number;
  precio_venta: number | null;
  stock_minimo: number;
  fecha_vencimiento: string | null;
  codigo_barras: string | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductoForm {
  nombre: string;
  marca?: string;
  categoria: string;
  subcategoria?: string;
  unidad?: string;
  costo_unitario: number;
  precio_venta?: number;
  stock_minimo: number;
  cantidad_inicial?: number;
  fecha_vencimiento?: string;
  codigo_barras?: string;
}

export interface PaginatedProductos {
  items: Producto[];
  total: number;
  page: number;
  page_size: number;
}

export interface MovimientoInventario {
  id: number;
  producto_id: number;
  tipo: string;
  cantidad: number;
  cantidad_anterior: number;
  cantidad_nueva: number;
  motivo: string | null;
  referencia: string | null;
  created_at: string;
}

export interface PaginatedMovimientos {
  items: MovimientoInventario[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// Ventas
// ============================================================

export interface DetalleVenta {
  id: number;
  producto_id: number | null;
  descripcion: string;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
}

export interface Venta {
  id: number;
  ficha_cliente_id: number | null;
  cita_id: number | null;
  tipo: string;
  subtotal: number;
  descuento: number;
  total: number;
  metodo_pago: string;
  notas: string | null;
  vendedor: string | null;
  detalles: DetalleVenta[];
  created_at: string;
}

export interface PaginatedVentas {
  items: Venta[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// Informes
// ============================================================

export interface InformeVentas {
  total_ingresos: number;
  total_ventas: number;
  ticket_promedio: number;
  ventas_por_dia: { fecha: string; cantidad: number; total: number }[];
  ventas_por_metodo_pago: { metodo: string; cantidad: number; total: number }[];
  productos_mas_vendidos: { nombre: string; cantidad: number; total: number }[];
  servicios_mas_vendidos: { nombre: string; cantidad: number; total: number }[];
}

export interface InformeInventario {
  valor_total_stock: number;
  total_productos: number;
  productos_bajo_stock: { id: number; nombre: string; cantidad: number; stock_minimo: number }[];
  productos_por_vencer: { id: number; nombre: string; fecha_vencimiento: string; cantidad: number }[];
  movimientos_recientes: { fecha: string; producto: string; tipo: string; cantidad: number; motivo: string | null }[];
}

export interface InformeClientes {
  total_clientes: number;
  clientes_nuevos_periodo: number;
  clientes_recurrentes: number;
  top_clientes: { nombre: string; telefono: string; total_ventas: number; total_gastado: number }[];
  frecuencia_visitas: { rango: string; cantidad: number }[];
}

export interface InformeEstilistas {
  rendimiento: {
    nombre: string;
    citas_totales: number;
    completadas: number;
    canceladas: number;
    ingresos: number;
    tasa_cancelacion: number;
  }[];
}
