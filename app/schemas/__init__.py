"""
Pydantic schemas for request/response validation.
"""

from app.schemas.schemas import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatus,
    AppointmentUpdate,
    AvailabilityCheck,
    AvailabilityResponse,
    ChatwootAttachment,
    ChatwootContact,
    ChatwootConversation,
    ChatwootEventType,
    ChatwootMessage,
    ChatwootMessageType,
    ChatwootSender,
    ChatwootWebhookPayload,
    DailyStatistics,
    DetalleVentaCreate,
    DetalleVentaResponse,
    FichaClienteCreate,
    FichaClienteResponse,
    FichaClienteUpdate,
    LeadCreate,
    LeadResponse,
    LeadUpdate,
    MovimientoCreate,
    MovimientoResponse,
    ProductoCreate,
    ProductoResponse,
    ProductoUpdate,
    SalonInfoResponse,
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
    StylistCreate,
    StylistResponse,
    StylistScheduleResponse,
    StylistUpdate,
    TimeSlot,
    VentaCreate,
    VentaResponse,
    WeeklyReport,
)

__all__ = [
    # Chatwoot
    "ChatwootWebhookPayload",
    "ChatwootMessage",
    "ChatwootConversation",
    "ChatwootContact",
    "ChatwootSender",
    "ChatwootAttachment",
    "ChatwootMessageType",
    "ChatwootEventType",
    # Services
    "ServiceCreate",
    "ServiceUpdate",
    "ServiceResponse",
    # Stylists
    "StylistCreate",
    "StylistUpdate",
    "StylistResponse",
    "StylistScheduleResponse",
    # Appointments
    "AppointmentStatus",
    "AppointmentCreate",
    "AppointmentUpdate",
    "AppointmentResponse",
    # Availability
    "AvailabilityCheck",
    "AvailabilityResponse",
    "TimeSlot",
    # Salon Info
    "SalonInfoResponse",
    # Statistics
    "DailyStatistics",
    "WeeklyReport",
    # Fichas
    "FichaClienteCreate",
    "FichaClienteUpdate",
    "FichaClienteResponse",
    # Inventario
    "ProductoCreate",
    "ProductoUpdate",
    "ProductoResponse",
    "MovimientoCreate",
    "MovimientoResponse",
    # Ventas
    "DetalleVentaCreate",
    "DetalleVentaResponse",
    "VentaCreate",
    "VentaResponse",
    # Leads
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
]
