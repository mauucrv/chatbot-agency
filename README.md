# chatbot-agency

Chatbot de WhatsApp para una agencia ficticia de consultoría en IA (**AgencyBot**). Demuestra un sistema agentico completo: webhooks de Chatwoot → agente LangChain (GPT-4o-mini) con 12 tools → agendamiento en Google Calendar, respaldado por un panel de administración en React. UX en español.

> Proyecto de portafolio. La marca "AgencyBot" y los datos semilla son ficticios; el código es una versión generalizada de un despliegue real.

## Características

### Mensajería
- Webhook de Chatwoot (texto, audio, imágenes)
- Transcripción de audio con OpenAI Whisper
- Interpretación de imágenes con GPT-4o Vision
- Agrupación de mensajes (acumula mensajes rápidos por 3s antes de responder)
- Rate limiting por teléfono — **fail-closed** (rechaza si Redis cae)

### Agente y Agendamiento
- Agente LangChain con 12 tools: verificar disponibilidad, CRUD de citas, servicios, consultores, información
- Google Calendar FreeBusy API para disponibilidad
- Distributed Redis lock al crear citas para prevenir doble reserva (TOCTOU-safe)
- Ventana de agendamiento configurable (default 90 días)

### Control del Bot
- Se pausa automáticamente cuando un agente humano responde en Chatwoot
- Se reactiva cuando la conversación se marca como resuelta
- Detección de keywords de handoff humano (abre la conversación para un agente)
- Auto-resume de conversaciones pausadas >24h (configurable)

### Jobs Programados
- Recordatorios diarios de citas
- Reporte semanal de estadísticas
- Backup diario de PostgreSQL a Google Drive (cifrado con Fernet)
- Sincronización periódica de Google Calendar

### Seguridad
- Verificación obligatoria de firma de webhooks en producción (HMAC o token URL)
- Validación hard-fail de variables críticas al arrancar en producción
- Autenticación JWT (PyJWT) con blacklist de tokens y rotación de refresh
- Complejidad de contraseña (mín 12 chars + clases) + login timing-safe
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- Parámetros sensibles redactados de los logs
- Usuario no-root en Docker + resource limits
- Backups cifrados antes de subirlos a servicios externos

### Panel de Administración
- React 18 + Vite + TypeScript + Tailwind + shadcn/ui
- ~60 endpoints REST (FastAPI, JWT)
- Roles: `admin` (CRUD completo) / `viewer` (solo lectura)
- Pantallas: Dashboard, Citas, Servicios, Consultores, Clientes, Inventario, Ventas, Información, Estadísticas, Informes

### Observabilidad
- Logs JSON estructurados con `structlog`
- Alertas opcionales de errores por Telegram con deduplicación en Redis

## Stack

| Capa | Tecnología |
|---|---|
| API | FastAPI (async) |
| Agente | LangChain + OpenAI GPT-4o-mini |
| DB | PostgreSQL 15 + SQLAlchemy 2.0 + asyncpg |
| Migraciones | Alembic |
| Cache / Locks / Rate limit | Redis 7 |
| Jobs | APScheduler |
| Validación | Pydantic v2 |
| Google APIs | google-api-python-client |
| Frontend | React 18 + Vite + Tailwind + shadcn/ui |
| Contenedores | Docker + docker-compose |
| Tests | pytest + pytest-asyncio |

## Cómo empezar

### Prerrequisitos
- Docker + Docker Compose
- API key de OpenAI
- Instancia de Chatwoot (self-hosted o cloud)
- Proyecto de Google Cloud con Calendar API habilitada y service account con acceso al calendario

### Ejecutar
```bash
git clone <repo-url>
cd chatbot-agency
cp .env.example .env
chmod 600 .env
# Llenar secrets en .env
docker-compose up -d
```

Las migraciones de Alembic corren automáticamente al arrancar (en dev); en producción, correr manualmente con `alembic upgrade head`.

### Configurar el webhook de Chatwoot
```
URL:    https://tu-dominio/api/webhooks/chatwoot
Events: message_created, conversation_status_changed
Auth:   ?token=<CHATWOOT_WEBHOOK_TOKEN>  (o firma HMAC X-Chatwoot-Signature)
```

## Tests

```bash
pip install -r requirements.txt
pytest tests/ -v --cov=app --cov-report=term-missing
```

## Notas de arquitectura

- UX en español; los nombres de modelos legacy (`ServicioBelleza`, `Estilista`) se mantienen por compatibilidad con migraciones — el código originalmente servía a un caso de uso de salón de belleza antes de ser generalizado.
- Singletons para el agente, message processor y clientes de servicios.
- Todo el I/O es async.
- Temperatura del agente deliberadamente baja (0.3) para consistencia transaccional al agendar.

## Licencia

[PolyForm Noncommercial 1.0.0](./LICENSE) — libre para estudiar, evaluar, experimentar y usar con fines no comerciales (investigación, aprendizaje, proyectos personales, organizaciones sin fines de lucro). El uso comercial requiere autorización del autor.
