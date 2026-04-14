"""
Google Calendar service for managing appointments.
"""

import asyncio
import structlog
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz

from app.config import settings, get_google_credentials

logger = structlog.get_logger(__name__)

# Required scopes for Google Calendar API
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Timeout for Google Calendar API calls (seconds)
GCAL_TIMEOUT_SECONDS = 30


class GoogleCalendarService:
    """Service for interacting with Google Calendar API."""

    def __init__(self):
        """Initialize the Google Calendar service."""
        self.calendar_id = settings.google_calendar_id
        self.timezone = pytz.timezone(settings.calendar_timezone)
        self._service = None
        self._init_lock = asyncio.Lock()

    async def _get_service_async(self):
        """Get or create the Google Calendar service (async-safe)."""
        if self._service is not None:
            return self._service
        async with self._init_lock:
            if self._service is None:
                try:
                    credentials = get_google_credentials(SCOPES)
                    self._service = build("calendar", "v3", credentials=credentials)
                    logger.info("Google Calendar service initialized")
                except Exception as e:
                    logger.error("Failed to initialize Google Calendar service", error=str(e))
                    raise
        return self._service

    def _get_service(self):
        """Get or create the Google Calendar service (sync, for use inside to_thread)."""
        if self._service is None:
            try:
                credentials = get_google_credentials(SCOPES)
                self._service = build("calendar", "v3", credentials=credentials)
                logger.info("Google Calendar service initialized")
            except Exception as e:
                logger.error("Failed to initialize Google Calendar service", error=str(e))
                raise
        return self._service

    async def _execute_with_timeout(self, request, timeout: int = GCAL_TIMEOUT_SECONDS):
        """Execute a Google API request in a thread with timeout."""
        return await asyncio.wait_for(
            asyncio.to_thread(request.execute),
            timeout=timeout,
        )

    def _format_datetime(self, dt: datetime) -> Dict[str, str]:
        """Format a datetime for the Google Calendar API."""
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
        return {
            "dateTime": dt.isoformat(),
            "timeZone": settings.calendar_timezone,
        }

    def _resolve_calendar_id(self, calendar_id: Optional[str] = None) -> str:
        """Return the given calendar_id or fall back to the global default."""
        return calendar_id or self.calendar_id

    async def check_availability(
        self,
        start_time: datetime,
        end_time: datetime,
        calendar_ids: Optional[List[str]] = None,
        calendar_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check availability using the FreeBusy API.

        Args:
            start_time: Start of the period to check
            end_time: End of the period to check
            calendar_ids: List of calendar IDs to check (defaults to main calendar)

        Returns:
            Dictionary with availability info
        """
        try:
            service = self._get_service()

            if calendar_ids is None:
                calendar_ids = [self._resolve_calendar_id(calendar_id)]

            body = {
                "timeMin": self._format_datetime(start_time)["dateTime"],
                "timeMax": self._format_datetime(end_time)["dateTime"],
                "timeZone": settings.calendar_timezone,
                "items": [{"id": cal_id} for cal_id in calendar_ids],
            }

            result = await self._execute_with_timeout(
                service.freebusy().query(body=body)
            )

            calendars = result.get("calendars", {})
            busy_periods = []

            for cal_id in calendar_ids:
                cal_info = calendars.get(cal_id, {})
                busy_periods.extend(cal_info.get("busy", []))

            # Check if the requested time slot is free
            is_available = len(busy_periods) == 0

            # Parse busy periods
            parsed_busy = []
            for period in busy_periods:
                parsed_busy.append({
                    "start": datetime.fromisoformat(period["start"].replace("Z", "+00:00")),
                    "end": datetime.fromisoformat(period["end"].replace("Z", "+00:00")),
                })

            logger.info(
                "Availability checked",
                start=start_time.isoformat(),
                end=end_time.isoformat(),
                is_available=is_available,
                busy_periods=len(parsed_busy),
            )

            return {
                "available": is_available,
                "busy_periods": parsed_busy,
            }

        except asyncio.TimeoutError:
            logger.error("Google Calendar availability check timed out")
            from app.services.telegram_notifier import notify_error
            await notify_error("google_calendar", "Availability check timed out")
            return {"available": False, "error": "Timeout checking calendar", "busy_periods": []}
        except HttpError as e:
            logger.error("Google Calendar API error", error=str(e))
            from app.services.telegram_notifier import notify_error
            await notify_error("google_calendar", f"API error on availability check: {str(e)}")
            return {"available": False, "error": "Error al verificar el calendario", "busy_periods": []}
        except Exception as e:
            logger.error("Error checking availability", error=str(e))
            return {"available": False, "error": "Error al verificar el calendario", "busy_periods": []}

    async def get_available_slots(
        self,
        date: datetime,
        duration_minutes: int,
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None,
        slot_interval: Optional[int] = None,
        calendar_id: Optional[str] = None,
    ) -> List[Dict[str, datetime]]:
        """
        Get available time slots for a specific date.

        Args:
            date: The date to check
            duration_minutes: Duration of the appointment in minutes
            start_hour: Start of business hours
            end_hour: End of business hours
            slot_interval: Interval between slot start times in minutes

        Returns:
            List of available time slots
        """
        try:
            # Apply defaults from settings
            if start_hour is None:
                start_hour = settings.default_business_start_hour
            if end_hour is None:
                end_hour = settings.default_business_end_hour
            if slot_interval is None:
                slot_interval = settings.default_slot_interval

            # Set up the time range for the day
            if date.tzinfo is None:
                date = self.timezone.localize(date)

            day_start = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            day_end = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)

            # Get busy periods for the day
            result = await self.check_availability(day_start, day_end, calendar_id=calendar_id)
            busy_periods = result.get("busy_periods", [])

            # Generate all possible slots
            available_slots = []
            current_slot = day_start

            while current_slot + timedelta(minutes=duration_minutes) <= day_end:
                slot_end = current_slot + timedelta(minutes=duration_minutes)

                # Check if slot overlaps with any busy period
                is_available = True
                for busy in busy_periods:
                    busy_start = busy["start"]
                    busy_end = busy["end"]

                    # Convert to same timezone for comparison
                    if busy_start.tzinfo != current_slot.tzinfo:
                        busy_start = busy_start.astimezone(self.timezone)
                        busy_end = busy_end.astimezone(self.timezone)

                    # Check for overlap
                    if current_slot < busy_end and slot_end > busy_start:
                        is_available = False
                        break

                if is_available:
                    available_slots.append({
                        "start": current_slot,
                        "end": slot_end,
                    })

                current_slot += timedelta(minutes=slot_interval)

            logger.info(
                "Available slots calculated",
                date=date.date().isoformat(),
                slots_found=len(available_slots),
            )

            return available_slots

        except Exception as e:
            logger.error("Error getting available slots", error=str(e))
            return []

    async def create_event(
        self,
        summary: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        attendees: Optional[List[str]] = None,
        calendar_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a calendar event.

        Args:
            summary: Event title
            description: Event description
            start_time: Start time
            end_time: End time
            attendees: List of attendee emails

        Returns:
            The created event or None if failed
        """
        try:
            service = self._get_service()

            event = {
                "summary": summary,
                "description": description,
                "start": self._format_datetime(start_time),
                "end": self._format_datetime(end_time),
            }

            if attendees:
                event["attendees"] = [{"email": email} for email in attendees]

            result = await self._execute_with_timeout(
                service.events().insert(
                    calendarId=self._resolve_calendar_id(calendar_id),
                    body=event,
                    sendUpdates="all" if attendees else "none",
                )
            )

            logger.info(
                "Calendar event created",
                event_id=result.get("id"),
                summary=summary,
            )

            return result

        except HttpError as e:
            logger.error("Failed to create calendar event", error=str(e))
            from app.services.telegram_notifier import notify_error
            await notify_error("google_calendar", f"Failed to create event: {str(e)}")
            return None
        except Exception as e:
            logger.error("Error creating calendar event", error=str(e))
            from app.services.telegram_notifier import notify_error
            await notify_error("google_calendar", f"Error creating event: {str(e)}")
            return None

    async def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        calendar_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update a calendar event.

        Args:
            event_id: The event ID to update
            summary: New event title
            description: New event description
            start_time: New start time
            end_time: New end time

        Returns:
            The updated event or None if failed
        """
        try:
            service = self._get_service()

            # Get current event
            resolved_cal_id = self._resolve_calendar_id(calendar_id)

            event = await self._execute_with_timeout(
                service.events().get(
                    calendarId=resolved_cal_id,
                    eventId=event_id,
                )
            )

            # Update fields
            if summary:
                event["summary"] = summary
            if description:
                event["description"] = description
            if start_time:
                event["start"] = self._format_datetime(start_time)
            if end_time:
                event["end"] = self._format_datetime(end_time)

            result = await self._execute_with_timeout(
                service.events().update(
                    calendarId=resolved_cal_id,
                    eventId=event_id,
                    body=event,
                )
            )

            logger.info(
                "Calendar event updated",
                event_id=event_id,
            )

            return result

        except HttpError as e:
            logger.error("Failed to update calendar event", event_id=event_id, error=str(e))
            return None
        except Exception as e:
            logger.error("Error updating calendar event", event_id=event_id, error=str(e))
            return None

    async def delete_event(self, event_id: str, calendar_id: Optional[str] = None) -> bool:
        """
        Delete a calendar event.

        Args:
            event_id: The event ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            service = self._get_service()

            await self._execute_with_timeout(
                service.events().delete(
                    calendarId=self._resolve_calendar_id(calendar_id),
                    eventId=event_id,
                )
            )

            logger.info("Calendar event deleted", event_id=event_id)
            return True

        except HttpError as e:
            logger.error("Failed to delete calendar event", event_id=event_id, error=str(e))
            return False
        except Exception as e:
            logger.error("Error deleting calendar event", event_id=event_id, error=str(e))
            return False

    async def get_event(self, event_id: str, calendar_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a calendar event by ID.

        Args:
            event_id: The event ID

        Returns:
            The event or None if not found
        """
        try:
            service = self._get_service()

            event = await self._execute_with_timeout(
                service.events().get(
                    calendarId=self._resolve_calendar_id(calendar_id),
                    eventId=event_id,
                )
            )

            return event

        except HttpError as e:
            if e.resp.status == 404:
                return None
            logger.error("Failed to get calendar event", event_id=event_id, error=str(e))
            return None
        except Exception as e:
            logger.error("Error getting calendar event", event_id=event_id, error=str(e))
            return None

    async def list_events(
        self,
        start_time: datetime,
        end_time: datetime,
        max_results: int = 100,
        calendar_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List events in a time range.

        Args:
            start_time: Start of the range
            end_time: End of the range
            max_results: Maximum number of events to return

        Returns:
            List of events
        """
        try:
            service = self._get_service()

            result = await self._execute_with_timeout(
                service.events().list(
                    calendarId=self._resolve_calendar_id(calendar_id),
                    timeMin=self._format_datetime(start_time)["dateTime"],
                    timeMax=self._format_datetime(end_time)["dateTime"],
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
            )

            events = result.get("items", [])

            logger.info(
                "Events listed",
                start=start_time.isoformat(),
                end=end_time.isoformat(),
                count=len(events),
            )

            return events

        except HttpError as e:
            logger.error("Failed to list calendar events", error=str(e))
            return []
        except Exception as e:
            logger.error("Error listing calendar events", error=str(e))
            return []



# Singleton instance
google_calendar_service = GoogleCalendarService()
