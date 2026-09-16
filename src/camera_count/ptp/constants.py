"""PTP constants, every one of them traceable to a public definition.

Values are transcribed from the PTP header in libgphoto2, which is used here
strictly as reference material - no libgphoto2 code is copied, linked, or
derived beyond these published protocol numbers, which come from the PTP
standard (ISO 15740 / PIMA 15740:2000) itself.

Reference file, retrieved 2026-09-16:
https://raw.githubusercontent.com/gphoto/libgphoto2/master/camlibs/ptp2/ptp.h

The line numbers in :data:`CITATIONS` point into that file. Nothing in this
module may be invented: if a code is not in a cited source, it does not belong
here.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final

#: Where each constant group comes from, for diagnostics and reports.
PTP_HEADER_REFERENCE: Final = "libgphoto2/camlibs/ptp2/ptp.h"

CITATIONS: Final[dict[str, str]] = {
    "ContainerType": f"{PTP_HEADER_REFERENCE}:160-164",
    "Operation.GET_DEVICE_INFO": f"{PTP_HEADER_REFERENCE}:224",
    "Operation.OPEN_SESSION": f"{PTP_HEADER_REFERENCE}:225",
    "Operation.CLOSE_SESSION": f"{PTP_HEADER_REFERENCE}:226",
    "Operation.GET_STORAGE_IDS": f"{PTP_HEADER_REFERENCE}:227",
    "Operation.GET_DEVICE_PROP_DESC": f"{PTP_HEADER_REFERENCE}:243",
    "Operation.GET_DEVICE_PROP_VALUE": f"{PTP_HEADER_REFERENCE}:244",
    "ResponseCode": f"{PTP_HEADER_REFERENCE}:1118-1154",
    "DataType": f"{PTP_HEADER_REFERENCE}:1910-1935",
    "BULK_HEADER_LENGTH": f"{PTP_HEADER_REFERENCE}:121",
    "MAX_COMMAND_PARAMETERS": f"{PTP_HEADER_REFERENCE}:124",
}


class ContainerType(IntEnum):
    """USB container types. ptp.h:160-164."""

    UNDEFINED = 0x0000
    COMMAND = 0x0001
    DATA = 0x0002
    RESPONSE = 0x0003
    EVENT = 0x0004


class Operation(IntEnum):
    """The only standard operations this program ever sends.

    All five are reads. Nothing that changes device state appears here, and
    nothing may be added without a citation and a review of the read-only
    guarantee.
    """

    GET_DEVICE_INFO = 0x1001
    OPEN_SESSION = 0x1002
    CLOSE_SESSION = 0x1003
    GET_STORAGE_IDS = 0x1004
    GET_DEVICE_PROP_DESC = 0x1014
    GET_DEVICE_PROP_VALUE = 0x1015


class ResponseCode(IntEnum):
    """Standard response codes. ptp.h:1118-1154."""

    UNDEFINED = 0x2000
    OK = 0x2001
    GENERAL_ERROR = 0x2002
    SESSION_NOT_OPEN = 0x2003
    INVALID_TRANSACTION_ID = 0x2004
    OPERATION_NOT_SUPPORTED = 0x2005
    PARAMETER_NOT_SUPPORTED = 0x2006
    INCOMPLETE_TRANSFER = 0x2007
    INVALID_STORAGE_ID = 0x2008
    INVALID_OBJECT_HANDLE = 0x2009
    DEVICE_PROP_NOT_SUPPORTED = 0x200A
    INVALID_OBJECT_FORMAT_CODE = 0x200B
    STORE_FULL = 0x200C
    OBJECT_WRITE_PROTECTED = 0x200D
    STORE_READ_ONLY = 0x200E
    ACCESS_DENIED = 0x200F
    NO_THUMBNAIL_PRESENT = 0x2010
    SELF_TEST_FAILED = 0x2011
    PARTIAL_DELETION = 0x2012
    STORE_NOT_AVAILABLE = 0x2013
    SPECIFICATION_BY_FORMAT_UNSUPPORTED = 0x2014
    NO_VALID_OBJECT_INFO = 0x2015
    INVALID_CODE_FORMAT = 0x2016
    UNKNOWN_VENDOR_CODE = 0x2017
    CAPTURE_ALREADY_TERMINATED = 0x2018
    DEVICE_BUSY = 0x2019
    INVALID_PARENT_OBJECT = 0x201A
    INVALID_DEVICE_PROP_FORMAT = 0x201B
    INVALID_DEVICE_PROP_VALUE = 0x201C
    INVALID_PARAMETER = 0x201D
    SESSION_ALREADY_OPENED = 0x201E
    TRANSACTION_CANCELED = 0x201F
    SPECIFICATION_OF_DESTINATION_UNSUPPORTED = 0x2020


class DataType(IntEnum):
    """Device property data type codes. ptp.h:1910-1935."""

    UNDEF = 0x0000
    INT8 = 0x0001
    UINT8 = 0x0002
    INT16 = 0x0003
    UINT16 = 0x0004
    INT32 = 0x0005
    UINT32 = 0x0006
    INT64 = 0x0007
    UINT64 = 0x0008
    INT128 = 0x0009
    UINT128 = 0x000A
    AINT8 = 0x4001
    AUINT8 = 0x4002
    AINT16 = 0x4003
    AUINT16 = 0x4004
    AINT32 = 0x4005
    AUINT32 = 0x4006
    AINT64 = 0x4007
    AUINT64 = 0x4008
    AINT128 = 0x4009
    AUINT128 = 0x400A
    STR = 0xFFFF


#: ptp.h:1922
ARRAY_MASK: Final = 0x4000

#: 2 * uint32 + 2 * uint16 - ptp.h:121
BULK_HEADER_LENGTH: Final = 12

#: A command container carries at most five 32-bit parameters - ptp.h:124
MAX_COMMAND_PARAMETERS: Final = 5

#: Unsigned integer widths, in bytes, for the scalar data types.
SCALAR_WIDTHS: Final[dict[DataType, int]] = {
    DataType.INT8: 1,
    DataType.UINT8: 1,
    DataType.INT16: 2,
    DataType.UINT16: 2,
    DataType.INT32: 4,
    DataType.UINT32: 4,
    DataType.INT64: 8,
    DataType.UINT64: 8,
    DataType.INT128: 16,
    DataType.UINT128: 16,
}

SIGNED_TYPES: Final[frozenset[DataType]] = frozenset(
    {
        DataType.INT8,
        DataType.INT16,
        DataType.INT32,
        DataType.INT64,
        DataType.INT128,
    }
)

# --- Bounds on untrusted input ----------------------------------------------
# A camera is an unauthenticated peripheral. Every one of these is a hard cap
# enforced before allocation, not a hint.

#: Largest container this program will accept from a device (1 MiB).
MAX_CONTAINER_LENGTH: Final = 1_048_576

#: Largest number of elements in a PTP array.
MAX_ARRAY_ELEMENTS: Final = 65_536

#: PTP strings are length-prefixed by a single byte of character count.
MAX_STRING_CHARS: Final = 255

#: Per-transfer timeout in milliseconds.
DEFAULT_TIMEOUT_MS: Final = 5_000

# --- USB Still Image class ---------------------------------------------------
# USB Device Class Definition for Still Image Capture Devices, version 1.0,
# section 3 (interface descriptor): class 6, subclass 1, protocol 1.
# https://www.usb.org/sites/default/files/usbstillimg10.pdf

USB_CLASS_STILL_IMAGE: Final = 0x06
USB_SUBCLASS_STILL_IMAGE: Final = 0x01
USB_PROTOCOL_PTP: Final = 0x01

#: Class-specific control requests from the same specification, section 5.
USB_REQUEST_CANCEL: Final = 0x64
USB_REQUEST_GET_EXTENDED_EVENT_DATA: Final = 0x65
USB_REQUEST_DEVICE_RESET: Final = 0x66
USB_REQUEST_GET_DEVICE_STATUS: Final = 0x67


def response_name(code: int) -> str:
    """Human-readable name for a response code, or its hex value."""
    try:
        return ResponseCode(code).name
    except ValueError:
        return f"0x{code:04X}"


def operation_name(code: int) -> str:
    try:
        return Operation(code).name
    except ValueError:
        return f"0x{code:04X}"
