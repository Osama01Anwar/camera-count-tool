"""Exception hierarchy.

Errors are raised for programmer mistakes and for genuine failures. A camera
that simply cannot give an exact count is *not* an error: that is reported as
an :class:`camera_count.core.models.Unavailable` result with exit code 2.
"""

from __future__ import annotations


class CameraCountError(Exception):
    """Base class for every error raised by this application."""


class ForbiddenConstructionError(CameraCountError):
    """A ShutterReading was constructed outside its guarded factory."""


class UnknownSourceError(CameraCountError):
    """A source id did not resolve to any registry entry."""


class UnverifiedSourceError(CameraCountError):
    """A source id resolved to an entry that is not documented or verified."""


class ValueOutOfBoundsError(CameraCountError):
    """An integer failed validation before it could become a reading."""


class RegistryError(CameraCountError):
    """The camera registry is missing, malformed, or failed schema validation."""


class DeviceAccessError(CameraCountError):
    """A device could not be enumerated, opened, or claimed."""


class ProtocolError(CameraCountError):
    """A protocol-level failure (bad response code, transport failure)."""


class ParseError(ProtocolError):
    """Untrusted bytes violated a bound or a length check while parsing."""


class ForbiddenOperationError(CameraCountError):
    """An operation code was not on the adapter's read-only allow-list.

    Raised *before* anything is sent to the device.
    """


class MetadataError(CameraCountError):
    """Metadata extraction failed."""


class ToolNotFoundError(MetadataError):
    """The bundled/external ExifTool executable could not be located."""
