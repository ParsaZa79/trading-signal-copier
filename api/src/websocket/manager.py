"""WebSocket connection manager."""

import json
from datetime import datetime

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, account_id: str) -> None:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self.active_connections.setdefault(account_id, set()).add(websocket)
        print(f"WebSocket connected. Total connections: {self.connection_count}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
        """
        empty_accounts: list[str] = []
        for account_id, connections in self.active_connections.items():
            connections.discard(websocket)
            if not connections:
                empty_accounts.append(account_id)
        for account_id in empty_accounts:
            self.active_connections.pop(account_id, None)
        print(f"WebSocket disconnected. Total connections: {self.connection_count}")

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        """Send a message to a specific client.

        Args:
            message: The message dict to send.
            websocket: The WebSocket connection to send to.
        """
        try:
            data = json.dumps(message, default=self._json_serializer)
            await websocket.send_text(data)
        except Exception as e:
            print(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, account_id: str, message: dict) -> None:
        """Broadcast a message to all connected clients.

        Args:
            message: The message dict to broadcast.
        """
        data = json.dumps(message, default=self._json_serializer)
        disconnected: set[WebSocket] = set()

        for connection in self.active_connections.get(account_id, set()):
            try:
                await connection.send_text(data)
            except Exception as e:
                print(f"Error broadcasting to client: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections.get(account_id, set()).discard(conn)

    @property
    def account_ids(self) -> list[str]:
        """Get account ids with active WebSocket subscribers."""
        return list(self.active_connections.keys())

    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for objects not serializable by default."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return sum(len(connections) for connections in self.active_connections.values())


# Global connection manager instance
manager = ConnectionManager()
