# When the camera does not show up

Work down this list. `camera-count detect` tells you what it can see and why a
backend could not run, which is usually enough to find the answer here.

## 1. The basics

- The camera is switched on, and has not gone to sleep.
- The battery is not flat. Some bodies refuse USB below a threshold.
- **The cable carries data.** A charge-only cable is the single most common
  cause. Try a different cable before anything else.
- Try a port directly on the machine rather than through a hub.

## 2. USB mode

Set the camera's USB mode to **PTP**, **PC Remote**, **MTP** or **PC
connection**, depending on the manufacturer's wording. It is usually in the
setup menu under *USB*, *Connection* or *PC connection*.

**Mass storage mode gives no protocol access at all.** The camera appears as a
removable drive and nothing more. The tool reports:

```
PROTOCOL NOT SUPPORTED
The camera is in mass-storage mode, which provides no protocol access.
Switch the camera's USB mode to PTP/PC Remote/MTP and reconnect.
```

## 3. Something else is holding the camera

Windows lets one program own a portable device at a time. If the tool says the
camera is held by another program:

- Close any **File Explorer** window showing the camera.
- Quit importing tools: the Photos app, manufacturer utilities (Nikon NX Studio,
  Canon EOS Utility, Sony Imaging Edge), tethering software, and cloud syncers.
- Check the notification area for something that auto-launched when you plugged
  the camera in.
- Unplug and replug after closing them.

This program will not force another program off a device. Taking a camera away
from software that is mid-import is a good way to damage someone's day.

## 4. Check Windows can see it at all

Open **Device Manager** and look under *Portable Devices*. If the camera is not
there, or shows a warning triangle, it is a Windows-level problem rather than
this program:

- Try another port and cable.
- In Device Manager, right-click the device and choose *Uninstall device*
  (without deleting drivers), then unplug and replug so Windows re-detects it.
- Check Windows Update for optional driver updates.

## 5. Identified, but no count

Detection and identification working while the count says `NOT AVAILABLE` is
usually not a fault. Most documented counters live in image metadata rather than
in a property the camera exposes over USB. Try:

```powershell
camera-count exif "D:\DCIM\100NIKON\DSC_0001.NEF"
```

See [manufacturer-support.md](manufacturer-support.md) for what is documented.

## 6. The optional WinUSB path

If you have deliberately installed a WinUSB or libusb driver for your camera,
install the extra so the tool can use it:

```powershell
uv pip install "camera-count-tool[winusb]"
```

This program will never install, replace or remove a driver for you. Replacing
a camera's driver can stop other software working with it, and that is your
decision to make, not a side effect of running an inspection tool.

## 7. Collecting evidence for a bug report

```powershell
camera-count detect --json
camera-count diagnostics --export log.json
```

Serial numbers are redacted from the export unless you pass
`--include-serials`. Attach both to an issue.
