"""
SQLAlchemy database models for the AgencyBot chatbot.
"""

from datetime import datetime, time
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EstadoCita(str, PyEnum):
    """Appointment status enum."""

    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    EN_PROGRESO = "en_progreso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"
    NO_ASISTIO = "no_asistio"


class DiaSemana(str, PyEnum):
    """Day of week enum."""

    LUNES = "lunes"
    MARTES = "martes"
    MIERCOLES = "miercoles"
    JUEVES = "jueves"
    VIERNES = "viernes"
    SABADO = "sabado"
    DOMINGO = "domingo"


class PlanTenant(str, PyEnum):
    """Tenant plan enum."""
    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Tenant(Base):
    """Tenants table — each tenant is a separate business using the platform."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    plan: Mapped[PlanTenant] = mapped_column(
        Enum(PlanTenant, values_callable=lambda x: [e.value for e in x]),
        default=PlanTenant.TRIAL,
    )
    chatwoot_account_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chatwoot_inbox_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chatwoot_api_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    webhook_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_calendar_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    owner_email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    system_prompt_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_conversations_per_day: Mapped[int] = mapped_column(Integer, default=100)
    timezone: Mapped[str] = mapped_column(String(50), default="America/Mexico_City")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_payment_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    servicios: Mapped[List["ServicioBelleza"]] = relationship("ServicioBelleza", back_populates="tenant")
    estilistas: Mapped[List["Estilista"]] = relationship("Estilista", back_populates="tenant")
    citas: Mapped[List["Cita"]] = relationship("Cita", back_populates="tenant")
    admin_users: Mapped[List["AdminUser"]] = relationship("AdminUser", back_populates="tenant")
    leads: Mapped[List["Lead"]] = relationship("Lead", back_populates="tenant")

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, nombre='{self.nombre}', slug='{self.slug}')>"


class ServicioBelleza(Base):
    """Services table."""

    __tablename__ = "servicios_belleza"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    servicio: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    precio: Mapped[float] = mapped_column(Float, nullable=False)
    duracion_minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    estilistas_disponibles: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, default=list
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="servicios")

    def __repr__(self) -> str:
        return f"<ServicioBelleza(id={self.id}, servicio='{self.servicio}', precio={self.precio})>"


class Estilista(Base):
    """Stylists table."""

    __tablename__ = "estilistas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    telefono: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    especialidades: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, default=list
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    google_calendar_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    horarios: Mapped[List["HorarioEstilista"]] = relationship(
        "HorarioEstilista", back_populates="estilista", cascade="all, delete-orphan"
    )
    citas: Mapped[List["Cita"]] = relationship("Cita", back_populates="estilista")
    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="estilistas")

    def __repr__(self) -> str:
        return f"<Estilista(id={self.id}, nombre='{self.nombre}')>"


class HorarioEstilista(Base):
    """Stylist schedules table."""

    __tablename__ = "horarios_estilistas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estilista_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("estilistas.id", ondelete="CASCADE"), nullable=False
    )
    dia: Mapped[DiaSemana] = mapped_column(Enum(DiaSemana, values_callable=lambda x: [e.value for e in x]), nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    estilista: Mapped["Estilista"] = relationship(
        "Estilista", back_populates="horarios"
    )

    def __repr__(self) -> str:
        return f"<HorarioEstilista(estilista_id={self.estilista_id}, dia='{self.dia}')>"


class Cita(Base):
    """Appointments table."""

    __tablename__ = "citas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre_cliente: Mapped[str] = mapped_column(String(100), nullable=False)
    telefono_cliente: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_evento_google: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    servicios: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    precio_total: Mapped[float] = mapped_column(Float, nullable=False)
    estilista_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("estilistas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    estado: Mapped[EstadoCita] = mapped_column(
        Enum(EstadoCita, values_callable=lambda x: [e.value for e in x]), default=EstadoCita.PENDIENTE, index=True
    )
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recordatorio_enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    estilista: Mapped[Optional["Estilista"]] = relationship(
        "Estilista", back_populates="citas"
    )
    ventas: Mapped[List["Venta"]] = relationship("Venta", back_populates="cita")
    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="citas")

    def __repr__(self) -> str:
        return f"<Cita(id={self.id}, cliente='{self.nombre_cliente}', inicio='{self.inicio}')>"


class InformacionGeneral(Base):
    """General salon information table."""

    __tablename__ = "informacion_general"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre_salon: Mapped[str] = mapped_column(String(200), nullable=False)
    direccion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    horario: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    redes_sociales: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    politicas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<InformacionGeneral(nombre_salon='{self.nombre_salon}')>"


class ConversacionChatwoot(Base):
    """Chatwoot conversations tracking table."""

    __tablename__ = "conversaciones_chatwoot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatwoot_conversation_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )
    chatwoot_contact_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    telefono_cliente: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    nombre_cliente: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bot_activo: Mapped[bool] = mapped_column(Boolean, default=True)
    motivo_pausa: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pausado_por: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pausado_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ultimo_mensaje_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mensajes_pendientes: Mapped[Optional[List[dict]]] = mapped_column(
        JSON, nullable=True, default=list
    )
    contexto_conversacion: Mapped[Optional[List[dict]]] = mapped_column(
        JSON, nullable=True, default=list
    )
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ConversacionChatwoot(id={self.chatwoot_conversation_id}, telefono='{self.telefono_cliente}')>"


class KeywordHumano(Base):
    """Keywords that trigger human agent handoff."""

    __tablename__ = "keywords_humano"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<KeywordHumano(keyword='{self.keyword}')>"


class RolAdmin(str, PyEnum):
    """Admin role enum."""

    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    VIEWER = "viewer"


class AdminUser(Base):
    """Admin users for the web panel."""

    __tablename__ = "admin_users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_admin_users_tenant_username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolAdmin] = mapped_column(
        Enum(RolAdmin, values_callable=lambda x: [e.value for e in x]),
        default=RolAdmin.ADMIN,
        server_default="admin",
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    ultimo_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="admin_users")

    def __repr__(self) -> str:
        return f"<AdminUser(id={self.id}, username='{self.username}')>"


class EstadisticasBot(Base):
    """Bot statistics for reporting."""

    __tablename__ = "estadisticas_bot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    mensajes_recibidos: Mapped[int] = mapped_column(Integer, default=0)
    mensajes_respondidos: Mapped[int] = mapped_column(Integer, default=0)
    mensajes_audio: Mapped[int] = mapped_column(Integer, default=0)
    mensajes_imagen: Mapped[int] = mapped_column(Integer, default=0)
    usuarios_unicos: Mapped[int] = mapped_column(Integer, default=0)
    tokens_openai_aprox: Mapped[int] = mapped_column(Integer, default=0)
    citas_creadas: Mapped[int] = mapped_column(Integer, default=0)
    citas_modificadas: Mapped[int] = mapped_column(Integer, default=0)
    citas_canceladas: Mapped[int] = mapped_column(Integer, default=0)
    transferencias_humano: Mapped[int] = mapped_column(Integer, default=0)
    errores: Mapped[int] = mapped_column(Integer, default=0)
    tiempo_respuesta_promedio_ms: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<EstadisticasBot(fecha='{self.fecha}')>"


# ============================================================
# CRM - Leads / Prospectos
# ============================================================


class EtapaLead(str, PyEnum):
    """Lead pipeline stage enum."""

    NUEVO = "nuevo"
    CONTACTADO = "contactado"
    CITA_AGENDADA = "cita_agendada"
    EN_NEGOCIACION = "en_negociacion"
    CERRADO_GANADO = "cerrado_ganado"
    CERRADO_PERDIDO = "cerrado_perdido"


class OrigenLead(str, PyEnum):
    """Lead source enum."""

    WHATSAPP_ORGANICO = "whatsapp_organico"
    META_ADS = "meta_ads"
    REFERIDO = "referido"
    SITIO_WEB = "sitio_web"
    OTRO = "otro"


class Lead(Base):
    """CRM leads table."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telefono: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    empresa: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    etapa: Mapped[EtapaLead] = mapped_column(
        Enum(EtapaLead, values_callable=lambda x: [e.value for e in x]),
        default=EtapaLead.NUEVO,
        index=True,
    )
    origen: Mapped[OrigenLead] = mapped_column(
        Enum(OrigenLead, values_callable=lambda x: [e.value for e in x]),
        default=OrigenLead.WHATSAPP_ORGANICO,
    )
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    valor_estimado: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    servicio_interes: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    chatwoot_conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    chatwoot_contact_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ultimo_contacto: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    proximo_seguimiento: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="leads")

    def __repr__(self) -> str:
        return f"<Lead(id={self.id}, nombre='{self.nombre}', etapa='{self.etapa}')>"


# ============================================================
# Fichas Tecnicas de Clientes (legacy — kept for migration compatibility)
# ============================================================


class TipoCabello(str, PyEnum):
    """Hair type enum."""

    LISO = "liso"
    ONDULADO = "ondulado"
    RIZADO = "rizado"
    CRESPO = "crespo"
    MIXTO = "mixto"


class TipoPiel(str, PyEnum):
    """Skin type enum."""

    NORMAL = "normal"
    SECA = "seca"
    GRASA = "grasa"
    MIXTA = "mixta"
    SENSIBLE = "sensible"


class FichaCliente(Base):
    """Client technical profiles table."""

    __tablename__ = "fichas_clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    telefono: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    tipo_cabello: Mapped[Optional[TipoCabello]] = mapped_column(
        Enum(TipoCabello, values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    tipo_piel: Mapped[Optional[TipoPiel]] = mapped_column(
        Enum(TipoPiel, values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    alergias: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    historial_color: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True, default=list)
    historial_tratamientos: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True, default=list)
    preferencias: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    ventas: Mapped[List["Venta"]] = relationship("Venta", back_populates="ficha_cliente")

    def __repr__(self) -> str:
        return f"<FichaCliente(id={self.id}, nombre='{self.nombre}')>"


# ============================================================
# Inventario de Productos
# ============================================================


class CategoriaProducto(str, PyEnum):
    """Product category enum."""

    REVENTA = "reventa"
    USO_SALON = "uso_salon"


class TipoMovimiento(str, PyEnum):
    """Inventory movement type enum."""

    ENTRADA = "entrada"
    SALIDA = "salida"
    AJUSTE = "ajuste"


class Producto(Base):
    """Products inventory table."""

    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    marca: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    categoria: Mapped[CategoriaProducto] = mapped_column(
        Enum(CategoriaProducto, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    subcategoria: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cantidad: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unidad: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, default="unidad")
    costo_unitario: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    precio_venta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stock_minimo: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    fecha_vencimiento: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    codigo_barras: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    movimientos: Mapped[List["MovimientoInventario"]] = relationship(
        "MovimientoInventario", back_populates="producto", cascade="all, delete-orphan"
    )
    detalles_venta: Mapped[List["DetalleVenta"]] = relationship("DetalleVenta", back_populates="producto")

    def __repr__(self) -> str:
        return f"<Producto(id={self.id}, nombre='{self.nombre}', cantidad={self.cantidad})>"


class MovimientoInventario(Base):
    """Inventory movements audit trail."""

    __tablename__ = "movimientos_inventario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    producto_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("productos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[TipoMovimiento] = mapped_column(
        Enum(TipoMovimiento, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad_anterior: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad_nueva: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    referencia: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    producto: Mapped["Producto"] = relationship("Producto", back_populates="movimientos")

    def __repr__(self) -> str:
        return f"<MovimientoInventario(id={self.id}, producto_id={self.producto_id}, tipo='{self.tipo}')>"


# ============================================================
# Registro de Ventas
# ============================================================


class MetodoPago(str, PyEnum):
    """Payment method enum."""

    EFECTIVO = "efectivo"
    TARJETA = "tarjeta"
    TRANSFERENCIA = "transferencia"
    OTRO = "otro"


class TipoVenta(str, PyEnum):
    """Sale type enum."""

    PRODUCTO = "producto"
    SERVICIO = "servicio"
    MIXTA = "mixta"


class Venta(Base):
    """Sales table."""

    __tablename__ = "ventas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ficha_cliente_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("fichas_clientes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cita_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("citas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tipo: Mapped[TipoVenta] = mapped_column(
        Enum(TipoVenta, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)
    descuento: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    metodo_pago: Mapped[MetodoPago] = mapped_column(
        Enum(MetodoPago, values_callable=lambda x: [e.value for e in x]),
        default=MetodoPago.EFECTIVO,
    )
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vendedor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    ficha_cliente: Mapped[Optional["FichaCliente"]] = relationship("FichaCliente", back_populates="ventas")
    cita: Mapped[Optional["Cita"]] = relationship("Cita", back_populates="ventas")
    detalles: Mapped[List["DetalleVenta"]] = relationship(
        "DetalleVenta", back_populates="venta", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Venta(id={self.id}, total={self.total})>"


class DetalleVenta(Base):
    """Sale line items table."""

    __tablename__ = "detalles_venta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    producto_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("productos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Float, nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    venta: Mapped["Venta"] = relationship("Venta", back_populates="detalles")
    producto: Mapped[Optional["Producto"]] = relationship("Producto", back_populates="detalles_venta")

    def __repr__(self) -> str:
        return f"<DetalleVenta(id={self.id}, descripcion='{self.descripcion}')>"
