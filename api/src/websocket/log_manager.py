"""WebSocket log streaming manager for bot output."""

import json
from datetime import datetime

from fastapi import WebSocket


class LogManager:
    """Manages WebSocket connections for streaming bot logs."""

    def __init__(self):
        """Initialize the log manager."""
        self.connections: dict[str, set[WebSocket]] = {}
        self.log_buffers: dict[str, list[dict]] = {}
        self.max_buffer_size = 10000

    async def connect(self, websocket: WebSocket, account_id: str) -> bool:
        """Accept and register a new WebSocket connection.

        Sends buffered logs to new client.

        Returns:
            True if connection was successful, False if it failed.
        """
        try:
            await websocket.accept()
            self.connections.setdefault(account_id, set()).add(websocket)
            print(f"Log WebSocket connected. Total connections: {self.connection_count}")

            # Send buffered logs to new client (or empty history to confirm connection)
            await websocket.send_text(
                json.dumps({
                    "type": "history",
                    "account_id": account_id,
                    "logs": self.log_buffers.get(account_id, []),
                })
            )
            return True
        except Exception as e:
            print(f"Log WebSocket connection failed: {e}")
            for connections in self.connections.values():
                connections.discard(websocket)
            return False

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        empty_accounts: list[str] = []
        for account_id, connections in self.connections.items():
            connections.discard(websocket)
            if not connections:
                empty_accounts.append(account_id)
        for account_id in empty_accounts:
            self.connections.pop(account_id, None)
        print(f"Log WebSocket disconnected. Total connections: {self.connection_count}")

    async def broadcast_log(self, message: str, level: str = "info", account_id: str = "default") -> None:
        """Broadcast a log message to all connected clients.

        Args:
            message: The log message text.
            level: Log level (info, warning, error, bot).
        """
        log_entry = {
            "id": f"{datetime.now().timestamp()}-{id(message)}",
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "account_id": account_id,
        }

        # Add to buffer
        buffer = self.log_buffers.setdefault(account_id, [])
        buffer.append(log_entry)
        if len(buffer) > self.max_buffer_size:
            self.log_buffers[account_id] = buffer[-self.max_buffer_size :]

        # Broadcast to all connections
        data = json.dumps({
            "type": "log",
            "account_id": account_id,
            "log": log_entry,
        })

        disconnected: set[WebSocket] = set()

        for connection in self.connections.get(account_id, set()):
            try:
                await connection.send_text(data)
            except Exception as e:
                print(f"Error sending log to client: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.connections.get(account_id, set()).discard(conn)

    def clear_buffer(self, account_id: str) -> None:
        """Clear the log buffer."""
        self.log_buffers[account_id] = []

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return sum(len(connections) for connections in self.connections.values())


# Global log manager instance
log_manager = LogManager()
