"""
Chatwoot service for sending messages and managing conversations.
"""

import structlog
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = structlog.get_logger(__name__)


class ChatwootService:
    """Service for interacting with Chatwoot API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_token: Optional[str] = None,
        account_id: Optional[int] = None,
        inbox_id: Optional[int] = None,
    ):
        """Initialize the Chatwoot service. Accepts per-tenant overrides."""
        self.base_url = (base_url or settings.chatwoot_base_url).rstrip("/")
        self.api_token = api_token or settings.chatwoot_api_token
        self.account_id = account_id or settings.chatwoot_account_id
        self.inbox_id = inbox_id or settings.chatwoot_inbox_id

        self.headers = {
            "api_access_token": self.api_token,
            "Content-Type": "application/json",
        }
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create a persistent HTTP client for connection pooling."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close the persistent HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.close()
            self._http_client = None

    def _get_api_url(self, endpoint: str) -> str:
        """Get the full API URL for an endpoint."""
        return f"{self.base_url}/api/v1/accounts/{self.account_id}/{endpoint}"

    async def send_message(
        self,
        conversation_id: int,
        message: str,
        private: bool = False,
        content_type: str = "text",
        content_attributes: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Send a message to a Chatwoot conversation.

        Args:
            conversation_id: The Chatwoot conversation ID
            message: The message content
            private: Whether the message is private (internal note)
            content_type: The content type (text, input_select, etc.)
            content_attributes: Additional content attributes

        Returns:
            The message response or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}/messages")

        payload = {
            "content": message,
            "message_type": "outgoing",
            "private": private,
            "content_type": content_type,
        }

        if content_attributes:
            payload["content_attributes"] = content_attributes

        try:
            client = await self._get_http_client()
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            logger.info(
                "Message sent to Chatwoot",
                conversation_id=conversation_id,
                message_id=result.get("id"),
            )
            return result
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to send message to Chatwoot",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            from app.services.telegram_notifier import notify_error
            await notify_error(
                "chatwoot_api",
                f"Failed to send message: HTTP {e.response.status_code}",
                conversation_id=conversation_id,
            )
            return None
        except Exception as e:
            logger.error(
                "Error sending message to Chatwoot",
                conversation_id=conversation_id,
                error=str(e),
            )
            from app.services.telegram_notifier import notify_error
            await notify_error(
                "chatwoot_api",
                f"Error sending message: {str(e)}",
                conversation_id=conversation_id,
            )
            return None

    async def get_conversation(
        self, conversation_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: The Chatwoot conversation ID

        Returns:
            The conversation data or None if not found
        """
        url = self._get_api_url(f"conversations/{conversation_id}")

        try:
            client = await self._get_http_client()
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get conversation",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error getting conversation",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def get_contact(self, contact_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a contact by ID.

        Args:
            contact_id: The Chatwoot contact ID

        Returns:
            The contact data or None if not found
        """
        url = self._get_api_url(f"contacts/{contact_id}")

        try:
            client = await self._get_http_client()
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get contact",
                contact_id=contact_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error getting contact",
                contact_id=contact_id,
                error=str(e),
            )
            return None

    async def update_conversation_status(
        self, conversation_id: int, status: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update conversation status.

        Args:
            conversation_id: The Chatwoot conversation ID
            status: The new status ('open', 'resolved', 'pending', 'snoozed')

        Returns:
            The updated conversation or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}")

        payload = {"status": status}

        try:
            client = await self._get_http_client()
            response = await client.patch(url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(
                "Conversation status updated",
                conversation_id=conversation_id,
                status=status,
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to update conversation status",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error updating conversation status",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def add_labels(
        self, conversation_id: int, labels: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Add labels to a conversation.

        Args:
            conversation_id: The Chatwoot conversation ID
            labels: List of labels to add

        Returns:
            The updated conversation or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}/labels")

        payload = {"labels": labels}

        try:
            client = await self._get_http_client()
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(
                "Labels added to conversation",
                conversation_id=conversation_id,
                labels=labels,
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to add labels",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error adding labels",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def get_conversation_labels(self, conversation_id: int) -> List[str]:
        """Get current labels on a conversation."""
        url = self._get_api_url(f"conversations/{conversation_id}/labels")
        try:
            client = await self._get_http_client()
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("payload", [])
        except Exception as e:
            logger.error("Error getting labels", conversation_id=conversation_id, error=str(e))
            return []

    async def remove_labels(
        self, conversation_id: int, labels_to_remove: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Remove specific labels from a conversation (keeps others)."""
        current = await self.get_conversation_labels(conversation_id)
        updated = [l for l in current if l not in labels_to_remove]
        if len(updated) == len(current):
            return None  # nothing to remove
        return await self.add_labels(conversation_id, updated)

    async def update_contact_custom_attributes(
        self, contact_id: int, custom_attributes: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update custom attributes on a Chatwoot contact.

        Args:
            contact_id: The Chatwoot contact ID
            custom_attributes: Dict of custom attributes to set/update

        Returns:
            The updated contact or None if failed
        """
        url = self._get_api_url(f"contacts/{contact_id}")

        payload = {"custom_attributes": custom_attributes}

        try:
            client = await self._get_http_client()
            response = await client.put(url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(
                "Contact custom attributes updated",
                contact_id=contact_id,
                attributes=list(custom_attributes.keys()),
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Failed to update contact custom attributes",
                contact_id=contact_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.warning(
                "Error updating contact custom attributes",
                contact_id=contact_id,
                error=str(e),
            )
            return None

    async def assign_agent(
        self, conversation_id: int, agent_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Assign an agent to a conversation.

        Args:
            conversation_id: The Chatwoot conversation ID
            agent_id: The agent ID to assign

        Returns:
            The updated conversation or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}/assignments")

        payload = {"assignee_id": agent_id}

        try:
            client = await self._get_http_client()
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(
                "Agent assigned to conversation",
                conversation_id=conversation_id,
                agent_id=agent_id,
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to assign agent",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error assigning agent",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def get_messages(
        self, conversation_id: int, before: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: The Chatwoot conversation ID
            before: Get messages before this message ID

        Returns:
            List of messages or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}/messages")

        params = {}
        if before:
            params["before"] = before

        try:
            client = await self._get_http_client()
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("payload", [])
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get messages",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error getting messages",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def download_attachment(
        self, attachment_url: str, _retries: int = 3, _retry_delay: float = 3.0
    ) -> Optional[bytes]:
        """
        Download an attachment from Chatwoot with size limit and retry on 404.

        Some reverse proxies block Active Storage paths, so we try
        downloading via the internal Docker URL (CHATWOOT_INTERNAL_URL) first,
        which bypasses the proxy and goes directly to Rails.

        Args:
            attachment_url: The URL of the attachment

        Returns:
            The attachment content as bytes or None if failed/too large
        """
        import asyncio
        from urllib.parse import urlparse, urlunparse

        # Handle relative URLs
        if attachment_url.startswith("/"):
            attachment_url = f"{self.base_url}{attachment_url}"

        max_size = settings.max_attachment_size_bytes

        # Build list of URLs to try, prioritizing internal URL
        urls_to_try = []

        # Strategy 1: Use internal Docker URL (bypasses reverse proxy)
        if settings.chatwoot_internal_url:
            parsed = urlparse(attachment_url)
            internal_parsed = urlparse(settings.chatwoot_internal_url)
            internal_url = urlunparse((
                internal_parsed.scheme,
                internal_parsed.netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            ))
            urls_to_try.append(("internal", internal_url))

        # Strategy 2: Original external URL (fallback)
        urls_to_try.append(("external", attachment_url))

        for strategy, url in urls_to_try:
            result = await self._try_download(
                url, strategy, max_size, _retries, _retry_delay
            )
            if result is not None:
                return result

        logger.error(
            "All download strategies failed",
            url=attachment_url[:100],
        )
        return None

    async def _try_download(
        self,
        url: str,
        strategy: str,
        max_size: int,
        retries: int,
        retry_delay: float,
    ) -> Optional[bytes]:
        """Try downloading from a specific URL with retries."""
        import asyncio

        headers = {"api_access_token": self.api_token}

        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, max_redirects=5) as client:
                    async with client.stream(
                        "GET", url, headers=headers
                    ) as response:
                        response.raise_for_status()

                        # Check Content-Length header if available
                        content_length = response.headers.get("content-length")
                        if content_length and int(content_length) > max_size:
                            logger.warning(
                                "Attachment too large",
                                url=url[:100],
                                size=content_length,
                                max_size=max_size,
                            )
                            return None

                        # Stream and enforce size limit
                        chunks = []
                        total_size = 0
                        async for chunk in response.aiter_bytes():
                            total_size += len(chunk)
                            if total_size > max_size:
                                logger.warning(
                                    "Attachment exceeded size limit during download",
                                    url=url[:100],
                                    downloaded=total_size,
                                    max_size=max_size,
                                )
                                return None
                            chunks.append(chunk)

                        logger.info(
                            "Attachment downloaded successfully",
                            strategy=strategy,
                            size=total_size,
                        )
                        return b"".join(chunks)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404 and attempt < retries - 1:
                    delay = retry_delay * (attempt + 1)
                    logger.info(
                        "Attachment not ready, retrying",
                        strategy=strategy,
                        url=url[:100],
                        attempt=attempt + 1,
                        retry_in=delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                # For non-404 errors or final 404, try next strategy
                logger.debug(
                    "Download strategy failed",
                    strategy=strategy,
                    status_code=e.response.status_code,
                )
                return None
            except Exception as e:
                logger.debug(
                    "Download strategy error",
                    strategy=strategy,
                    error=str(e),
                )
                return None

        return None

    async def search_contacts(
        self, query: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Search for contacts.

        Args:
            query: Search query (name, email, phone)

        Returns:
            List of matching contacts or None if failed
        """
        url = self._get_api_url("contacts/search")

        params = {"q": query}

        try:
            client = await self._get_http_client()
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("payload", [])
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to search contacts",
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error searching contacts",
                error=str(e),
            )
            return None

    async def send_message_to_phone(
        self, phone_number: str, message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Send a message to a phone number (creates conversation if needed).

        Args:
            phone_number: The phone number to message
            message: The message content

        Returns:
            The message response or None if failed
        """
        # First, search for existing contact
        contacts = await self.search_contacts(phone_number)

        if contacts and len(contacts) > 0:
            contact_id = contacts[0]["id"]
        else:
            # Create new contact
            contact = await self._create_contact(phone_number)
            if not contact:
                return None
            contact_id = contact["id"]

        # Get or create conversation
        conversation = await self._get_or_create_conversation(contact_id)
        if not conversation:
            return None

        # Send message
        return await self.send_message(conversation["id"], message)

    async def _create_contact(
        self, phone_number: str, name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new contact."""
        url = self._get_api_url("contacts")

        payload = {
            "inbox_id": self.inbox_id,
            "phone_number": phone_number,
        }

        if name:
            payload["name"] = name

        try:
            client = await self._get_http_client()
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json().get("payload", {}).get("contact")
        except Exception as e:
            logger.error(
                "Error creating contact",
                phone=phone_number[-4:] if phone_number else None,
                error=str(e),
            )
            return None

    async def _get_or_create_conversation(
        self, contact_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get or create a conversation for a contact."""
        url = self._get_api_url("conversations")

        payload = {
            "source_id": str(contact_id),
            "inbox_id": self.inbox_id,
            "contact_id": contact_id,
        }

        try:
            client = await self._get_http_client()
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(
                "Error creating conversation",
                contact_id=contact_id,
                error=str(e),
            )
            return None


# Default singleton instance (uses global settings — backward compatible)
chatwoot_service = ChatwootService()

# Tenant-specific instances cache: {tenant_id: ChatwootService}
_tenant_chatwoot_services: Dict[int, ChatwootService] = {}


async def get_chatwoot_service(tenant_id: Optional[int] = None) -> ChatwootService:
    """
    Get a ChatwootService instance for a tenant.
    Returns the default singleton when tenant_id is None or tenant has no Chatwoot credentials.
    Caches tenant instances in memory.
    """
    if tenant_id is None:
        return chatwoot_service

    if tenant_id in _tenant_chatwoot_services:
        return _tenant_chatwoot_services[tenant_id]

    # Load tenant credentials from DB
    from app.database import get_session_context
    from app.models import Tenant
    from sqlalchemy import select

    async with get_session_context() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()

    if not tenant or not tenant.chatwoot_api_token:
        # No tenant-specific credentials — use default
        return chatwoot_service

    svc = ChatwootService(
        base_url=settings.chatwoot_base_url,  # shared Chatwoot instance
        api_token=tenant.chatwoot_api_token,
        account_id=tenant.chatwoot_account_id,
        inbox_id=tenant.chatwoot_inbox_id,
    )
    _tenant_chatwoot_services[tenant_id] = svc
    logger.info("Created tenant-specific ChatwootService", tenant_id=tenant_id)
    return svc


def invalidate_chatwoot_service_cache(tenant_id: int) -> None:
    """Remove a cached tenant ChatwootService (e.g., after tenant credentials update)."""
    _tenant_chatwoot_services.pop(tenant_id, None)
