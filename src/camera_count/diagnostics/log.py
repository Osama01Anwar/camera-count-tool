"""The protocol transaction log.

Every displayed number must trace back to an entry here: which operation was
sent, what came back, and the raw bytes it was parsed from. The log is also
what makes a bug report useful, so it is exportable - with serial numbers
redacted unless the user opts in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

#: Raw payloads are kept for evidence, but a single entry is capped.
MAX_LOGGED_BYTES: Final = 4096

REDACTED: Final = "[redacted]"


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    """One protocol exchange, as it happened."""

    reference: str
    index: int
    timestamp: datetime
    transport: str
    operation: str
    opcode: int
    parameters: tuple[int, ...]
    response_code: int | None
    response_name: str
    response_parameters: tuple[int, ...]
    data: bytes = field(repr=False, default=b"")
    truncated: bool = False
    duration_ms: float = 0.0
    note: str | None = None

    def data_hex(self) -> str:
        return self.data.hex()

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "index": self.index,
            "timestamp": self.timestamp.isoformat(),
            "transport": self.transport,
            "operation": self.operation,
            "opcode": f"0x{self.opcode:04X}",
            "parameters": [f"0x{value:08X}" for value in self.parameters],
            "response": self.response_name,
            "response_code": None if self.response_code is None else f"0x{self.response_code:04X}",
            "response_parameters": [f"0x{value:08X}" for value in self.response_parameters],
            "data_hex": self.data_hex(),
            "data_truncated": self.truncated,
            "duration_ms": round(self.duration_ms, 3),
            "note": self.note,
        }


class TransactionLog:
    """An append-only log of protocol exchanges for one session."""

    def __init__(self, *, transport: str = "unknown") -> None:
        self._records: list[TransactionRecord] = []
        self._secrets: set[str] = set()
        self._transport = transport

    # -- recording ------------------------------------------------------------

    def record(
        self,
        *,
        operation: str,
        opcode: int,
        parameters: tuple[int, ...] = (),
        response_code: int | None = None,
        response_name: str = "",
        response_parameters: tuple[int, ...] = (),
        data: bytes = b"",
        duration_ms: float = 0.0,
        note: str | None = None,
    ) -> TransactionRecord:
        index = len(self._records)
        truncated = len(data) > MAX_LOGGED_BYTES
        record = TransactionRecord(
            reference=f"txn-{index:04d}",
            index=index,
            timestamp=datetime.now(UTC),
            transport=self._transport,
            operation=operation,
            opcode=opcode,
            parameters=parameters,
            response_code=response_code,
            response_name=response_name,
            response_parameters=response_parameters,
            data=data[:MAX_LOGGED_BYTES],
            truncated=truncated,
            duration_ms=duration_ms,
            note=note,
        )
        self._records.append(record)
        return record

    def register_secret(self, value: str | None) -> None:
        """Mark a string - typically a serial number - for redaction on export."""
        if value and len(value) >= 3:
            self._secrets.add(value)

    # -- reading --------------------------------------------------------------

    @property
    def records(self) -> tuple[TransactionRecord, ...]:
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def find(self, reference: str) -> TransactionRecord | None:
        for record in self._records:
            if record.reference == reference:
                return record
        return None

    def summary(self) -> str:
        if not self._records:
            return "No protocol transactions were performed."
        lines = [
            f"{record.reference}  {record.operation:<24} {record.response_name}"
            for record in self._records
        ]
        return "\n".join(lines)

    # -- export ---------------------------------------------------------------

    def _redact_text(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return text

    def _redact_hex(self, hex_text: str) -> str:
        for secret in self._secrets:
            for encoding in ("ascii", "utf-16-le"):
                try:
                    encoded = secret.encode(encoding).hex()
                except UnicodeEncodeError:
                    continue
                if encoded and encoded in hex_text:
                    hex_text = hex_text.replace(encoded, "ff" * (len(encoded) // 2))
        return hex_text

    def export(self, *, include_serials: bool = False) -> dict[str, Any]:
        """Export the log. Serial numbers are redacted unless asked for."""
        entries: list[dict[str, Any]] = []
        for record in self._records:
            item = record.to_dict()
            if not include_serials:
                item["data_hex"] = self._redact_hex(item["data_hex"])
                if item["note"]:
                    item["note"] = self._redact_text(item["note"])
            entries.append(item)
        return {
            "transport": self._transport,
            "transaction_count": len(entries),
            "serials_included": include_serials,
            "transactions": entries,
        }
