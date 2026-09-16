"""Windows Portable Devices constants, transcribed from the Windows SDK headers.

Sources, retrieved 2026-09-16:

* ``Include/10.0.16299.0/um/WpdMtpExtensions.h`` - the MTP extension command
  category, its command keys and its parameter keys, and the GUID the Microsoft
  MTP driver combines with a vendor device property code to form a WPD property
  key.
* ``Include/10.0.16299.0/um/PortableDevice.h`` - the common command keys and the
  standard device identity properties.

Mirror used: https://github.com/tpn/winsdk-10

Nothing here is invented. The write-side commands that exist in the header -
``WPD_COMMAND_MTP_EXT_EXECUTE_COMMAND_WITH_DATA_TO_WRITE`` and
``WPD_COMMAND_MTP_EXT_WRITE_DATA`` - are deliberately **not** defined in this
module. Code that does not know a command's key cannot send it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

SDK_MTP_HEADER: Final = "winsdk-10/Include/10.0.16299.0/um/WpdMtpExtensions.h"
SDK_WPD_HEADER: Final = "winsdk-10/Include/10.0.16299.0/um/PortableDevice.h"


@dataclass(frozen=True, slots=True)
class PropertyKey:
    """A WPD PROPERTYKEY: a GUID plus a numeric id."""

    fmtid: str
    pid: int
    name: str = ""
    citation: str = ""

    def as_tuple(self) -> tuple[str, int]:
        return self.fmtid, self.pid

    def __str__(self) -> str:
        return f"{{{self.fmtid}}}\\{self.pid}"


# --- MTP extension category (WpdMtpExtensions.h:22) --------------------------

MTP_EXT_FMTID: Final = "4D545058-1A2E-4106-A357-771E0819FC56"

# Command keys - WpdMtpExtensions.h:32-103. Read-side only, by design.
COMMAND_GET_SUPPORTED_VENDOR_OPCODES: Final = PropertyKey(
    MTP_EXT_FMTID,
    11,
    "WPD_COMMAND_MTP_EXT_GET_SUPPORTED_VENDOR_OPCODES",
    f"{SDK_MTP_HEADER}:32",
)
COMMAND_EXECUTE_WITHOUT_DATA_PHASE: Final = PropertyKey(
    MTP_EXT_FMTID,
    12,
    "WPD_COMMAND_MTP_EXT_EXECUTE_COMMAND_WITHOUT_DATA_PHASE",
    f"{SDK_MTP_HEADER}:42",
)
COMMAND_EXECUTE_WITH_DATA_TO_READ: Final = PropertyKey(
    MTP_EXT_FMTID,
    13,
    "WPD_COMMAND_MTP_EXT_EXECUTE_COMMAND_WITH_DATA_TO_READ",
    f"{SDK_MTP_HEADER}:54",
)
COMMAND_READ_DATA: Final = PropertyKey(
    MTP_EXT_FMTID, 15, "WPD_COMMAND_MTP_EXT_READ_DATA", f"{SDK_MTP_HEADER}:76"
)
COMMAND_END_DATA_TRANSFER: Final = PropertyKey(
    MTP_EXT_FMTID, 17, "WPD_COMMAND_MTP_EXT_END_DATA_TRANSFER", f"{SDK_MTP_HEADER}:96"
)

# Parameter keys - WpdMtpExtensions.h:106-119.
PROPERTY_OPERATION_CODE: Final = PropertyKey(
    MTP_EXT_FMTID, 1001, "WPD_PROPERTY_MTP_EXT_OPERATION_CODE", f"{SDK_MTP_HEADER}:106"
)
PROPERTY_OPERATION_PARAMS: Final = PropertyKey(
    MTP_EXT_FMTID, 1002, "WPD_PROPERTY_MTP_EXT_OPERATION_PARAMS", f"{SDK_MTP_HEADER}:107"
)
PROPERTY_RESPONSE_CODE: Final = PropertyKey(
    MTP_EXT_FMTID, 1003, "WPD_PROPERTY_MTP_EXT_RESPONSE_CODE", f"{SDK_MTP_HEADER}:108"
)
PROPERTY_RESPONSE_PARAMS: Final = PropertyKey(
    MTP_EXT_FMTID, 1004, "WPD_PROPERTY_MTP_EXT_RESPONSE_PARAMS", f"{SDK_MTP_HEADER}:109"
)
PROPERTY_VENDOR_OPERATION_CODES: Final = PropertyKey(
    MTP_EXT_FMTID,
    1005,
    "WPD_PROPERTY_MTP_EXT_VENDOR_OPERATION_CODES",
    f"{SDK_MTP_HEADER}:110",
)
PROPERTY_TRANSFER_CONTEXT: Final = PropertyKey(
    MTP_EXT_FMTID, 1006, "WPD_PROPERTY_MTP_EXT_TRANSFER_CONTEXT", f"{SDK_MTP_HEADER}:111"
)
PROPERTY_TRANSFER_TOTAL_DATA_SIZE: Final = PropertyKey(
    MTP_EXT_FMTID,
    1007,
    "WPD_PROPERTY_MTP_EXT_TRANSFER_TOTAL_DATA_SIZE",
    f"{SDK_MTP_HEADER}:112",
)
PROPERTY_TRANSFER_NUM_BYTES_TO_READ: Final = PropertyKey(
    MTP_EXT_FMTID,
    1008,
    "WPD_PROPERTY_MTP_EXT_TRANSFER_NUM_BYTES_TO_READ",
    f"{SDK_MTP_HEADER}:113",
)
PROPERTY_TRANSFER_NUM_BYTES_READ: Final = PropertyKey(
    MTP_EXT_FMTID,
    1009,
    "WPD_PROPERTY_MTP_EXT_TRANSFER_NUM_BYTES_READ",
    f"{SDK_MTP_HEADER}:114",
)
PROPERTY_TRANSFER_DATA: Final = PropertyKey(
    MTP_EXT_FMTID, 1012, "WPD_PROPERTY_MTP_EXT_TRANSFER_DATA", f"{SDK_MTP_HEADER}:117"
)
PROPERTY_OPTIMAL_TRANSFER_BUFFER_SIZE: Final = PropertyKey(
    MTP_EXT_FMTID,
    1013,
    "WPD_PROPERTY_MTP_EXT_OPTIMAL_TRANSFER_BUFFER_SIZE",
    f"{SDK_MTP_HEADER}:118",
)

# --- Vendor-extended device properties (WpdMtpExtensions.h:134-143) ----------
# "Microsoft MTP driver combines this GUID and any vendor-extended MTP device
#  property code (as pid) to construct a WPD PROPERTYKEY... For example, vendor
#  extended device prop code, 0xD001, will be reported as WPD PROPERTYKEY:
#  {4D545058-8900-40b3-8F1D-DC246E1E8370}\\D001"

MTP_VENDOR_DEVICE_PROPS_FMTID: Final = "4D545058-8900-40B3-8F1D-DC246E1E8370"

# --- Common command keys (PortableDevice.h:1491-1499) ------------------------

COMMON_FMTID: Final = "F0422A9C-5DC8-4440-B5BD-5DF28835658A"
PROPERTY_COMMON_COMMAND_CATEGORY: Final = PropertyKey(
    COMMON_FMTID, 1001, "WPD_PROPERTY_COMMON_COMMAND_CATEGORY", f"{SDK_WPD_HEADER}:1491"
)
PROPERTY_COMMON_COMMAND_ID: Final = PropertyKey(
    COMMON_FMTID, 1002, "WPD_PROPERTY_COMMON_COMMAND_ID", f"{SDK_WPD_HEADER}:1495"
)
PROPERTY_COMMON_HRESULT: Final = PropertyKey(
    COMMON_FMTID, 1003, "WPD_PROPERTY_COMMON_HRESULT", f"{SDK_WPD_HEADER}:1499"
)

# --- Device identity properties (PortableDevice.h:1148-1172) -----------------

DEVICE_FMTID: Final = "26D4979A-E643-4626-9E2B-736DC0C92FDC"
DEVICE_FIRMWARE_VERSION: Final = PropertyKey(
    DEVICE_FMTID, 3, "WPD_DEVICE_FIRMWARE_VERSION", f"{SDK_WPD_HEADER}:1148"
)
DEVICE_MANUFACTURER: Final = PropertyKey(
    DEVICE_FMTID, 7, "WPD_DEVICE_MANUFACTURER", f"{SDK_WPD_HEADER}:1164"
)
DEVICE_MODEL: Final = PropertyKey(DEVICE_FMTID, 8, "WPD_DEVICE_MODEL", f"{SDK_WPD_HEADER}:1168")
DEVICE_SERIAL_NUMBER: Final = PropertyKey(
    DEVICE_FMTID, 9, "WPD_DEVICE_SERIAL_NUMBER", f"{SDK_WPD_HEADER}:1172"
)

# --- Client information (PortableDevice.h:924-952) ---------------------------

CLIENT_FMTID: Final = "204D9F0C-2292-4080-9F42-40664E70F859"
CLIENT_NAME_KEY: Final = PropertyKey(CLIENT_FMTID, 2, "WPD_CLIENT_NAME", f"{SDK_WPD_HEADER}:924")
CLIENT_MAJOR_VERSION_KEY: Final = PropertyKey(
    CLIENT_FMTID, 3, "WPD_CLIENT_MAJOR_VERSION", f"{SDK_WPD_HEADER}:928"
)
CLIENT_MINOR_VERSION_KEY: Final = PropertyKey(
    CLIENT_FMTID, 4, "WPD_CLIENT_MINOR_VERSION", f"{SDK_WPD_HEADER}:932"
)
CLIENT_REVISION_KEY: Final = PropertyKey(
    CLIENT_FMTID, 5, "WPD_CLIENT_REVISION", f"{SDK_WPD_HEADER}:936"
)
CLIENT_DESIRED_ACCESS_KEY: Final = PropertyKey(
    CLIENT_FMTID, 9, "WPD_CLIENT_DESIRED_ACCESS", f"{SDK_WPD_HEADER}:952"
)

#: GENERIC_READ. The device is opened for reading and nothing else, so the
#: read-only guarantee is declared to Windows itself at connection time.
#: winnt.h: #define GENERIC_READ (0x80000000L)
GENERIC_READ: Final = 0x80000000

#: The object id of the device itself, used when reading device properties.
DEVICE_OBJECT_ID: Final = "DEVICE"

#: Upper bound on a single passthrough data transfer, mirroring the PTP bound.
MAX_TRANSFER_BYTES: Final = 1_048_576

#: Chunk size when the device does not state an optimal transfer size.
DEFAULT_CHUNK_BYTES: Final = 4096


def vendor_device_property_key(mtp_property_code: int) -> PropertyKey:
    """Build the WPD key for a vendor-extended MTP device property code.

    The mapping is the one the Microsoft MTP driver documents: the vendor
    device-property GUID with the MTP property code as the id.
    """
    if not 0 <= mtp_property_code <= 0xFFFF:
        raise ValueError(f"MTP property code out of range: {mtp_property_code}")
    return PropertyKey(
        MTP_VENDOR_DEVICE_PROPS_FMTID,
        mtp_property_code,
        f"MTP vendor device property 0x{mtp_property_code:04X}",
        f"{SDK_MTP_HEADER}:134-143",
    )
