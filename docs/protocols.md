# Protocols

Every constant this program sends or interprets is transcribed from a published
definition, and the file and line it came from is recorded next to it. Nothing
is discovered by trying codes to see what happens: that is how you write to a
camera by accident.

## Windows Portable Devices (the normal path)

A camera in PTP or MTP mode is claimed by the Windows portable device driver.
Rather than replace that driver, the program talks through WPD, which is the
supported route and leaves the machine exactly as it was.

### Identity

Read from the standard device properties on the device object, as defined in
`PortableDevice.h`:

| Property | Key | Source |
|---|---|---|
| Manufacturer | `{26D4979A-E643-4626-9E2B-736DC0C92FDC}\7` | PortableDevice.h:1164 |
| Model | `...\8` | PortableDevice.h:1168 |
| Serial number | `...\9` | PortableDevice.h:1172 |
| Firmware | `...\3` | PortableDevice.h:1148 |

### Read-only access, declared to Windows

The device is opened with `WPD_CLIENT_DESIRED_ACCESS`
(`{204D9F0C-2292-4080-9F42-40664E70F859}\9`, PortableDevice.h:952) set to
`GENERIC_READ`. The read-only promise is not only enforced inside this program;
it is what the program asks the operating system for.

### Vendor device properties

The Microsoft MTP driver exposes a vendor-extended MTP device property as a WPD
property key built from a fixed GUID plus the MTP property code:

> "Microsoft MTP driver combines this GUID and any vendor-extended MTP device
> property code (as pid) to construct a WPD PROPERTYKEY... For example, vendor
> extended device prop code, 0xD001, will be reported as WPD PROPERTYKEY:
> `{4D545058-8900-40b3-8F1D-DC246E1E8370}\D001`"
>
> - `WpdMtpExtensions.h:134-143`

So a registry method of type `ptp_property` with identifier `0xD1A3` becomes a
read of `{4D545058-8900-40B3-8F1D-DC246E1E8370}\D1A3`.

### Vendor operation passthrough

`ptp_operation` methods use the MTP extension commands in
`WpdMtpExtensions.h`, all under the category
`{4D545058-1A2E-4106-A357-771E0819FC56}`:

| Command | Id | Source |
|---|---|---|
| Execute without data phase | 12 | WpdMtpExtensions.h:42 |
| Execute with data to read | 13 | WpdMtpExtensions.h:54 |
| Read data | 15 | WpdMtpExtensions.h:76 |
| End data transfer | 17 | WpdMtpExtensions.h:96 |

The write-side commands exist in the header - "execute with data to write" (14)
and "write data" (16) - and are **deliberately not defined anywhere in this
package**. Code that does not know a command's key cannot send it.

## PTP over USB (the optional WinUSB path)

Used only when a user has installed a WinUSB or libusb driver themselves. The
container format is `length(4) | type(2) | code(2) | transaction_id(4)` followed
by the payload.

Constants are transcribed from libgphoto2's PTP header, used strictly as
reference material for numbers that come from the PTP standard
(ISO 15740 / PIMA 15740:2000). No libgphoto2 code is copied or linked.

| Constant | Value | Source |
|---|---|---|
| Container: command / data / response / event | 1 / 2 / 3 / 4 | ptp.h:160-164 |
| Bulk header length | 12 | ptp.h:121 |
| Maximum command parameters | 5 | ptp.h:124 |
| GetDeviceInfo | 0x1001 | ptp.h:224 |
| OpenSession | 0x1002 | ptp.h:225 |
| CloseSession | 0x1003 | ptp.h:226 |
| GetDevicePropDesc | 0x1014 | ptp.h:243 |
| GetDevicePropValue | 0x1015 | ptp.h:244 |
| Response codes | 0x2000-0x2023 | ptp.h:1118-1154 |
| Data type codes | 0x0000-0xFFFF | ptp.h:1910-1935 |

Reference file: `libgphoto2/camlibs/ptp2/ptp.h`, retrieved 2026-09-16 from
<https://raw.githubusercontent.com/gphoto/libgphoto2/master/camlibs/ptp2/ptp.h>.

Those five operations are the entire standard allow-list, and all five are
reads. USB Still Image class is 6 / 1 / 1, from the USB Device Class Definition
for Still Image Capture Devices, version 1.0.

## The allow-list

`PtpSession.execute` and `WpdSession.execute_read_operation` check the opcode
against an allow-list **before** handing anything to the transport. A refused
operation is written to the transaction log as `REFUSED BY ALLOW-LIST` and
never sent.

Adapters start with an empty vendor allow-list. A test asserts that they all
still do, so adding a vendor operation is a visible change that must arrive
with a citation.

## Bounds on untrusted input

| Bound | Value |
|---|---|
| Maximum container length | 1 MiB |
| Maximum array elements | 65,536 |
| Maximum string characters | 255 |
| Per-transfer timeout | 5 s |

Every one is checked before anything is allocated or sliced.
