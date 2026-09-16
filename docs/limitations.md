# Limitations

This page exists because the honest answer to "why doesn't it show my camera's
count?" is usually "because nobody has documented how to read it", and that
deserves a straight explanation rather than a shrug.

## Most cameras will report NOT AVAILABLE

That is the expected result, not a bug. As of the current registry:

- **Nikon** and **Pentax/Ricoh** write a documented actuation counter into
  their MakerNotes, so an original file from most of their bodies yields an
  exact count.
- A few **Canon** models (EOS R5, R6, R6 Mark II, R8, R50) have a documented
  counter in a model-specific table.
- **Fujifilm, Olympus/OM System, Panasonic, Leica, Sigma, Hasselblad and Phase
  One** have no documented actuation counter at all in the sources searched.
  Not a hidden one - none.
- **Sony** has several candidate fields, but the source marks some of them as
  valid only for certain models. Until that is resolved per model, Sony bodies
  report unavailable rather than risk a wrong number.

See [manufacturer-support.md](manufacturer-support.md), which is generated from
the registry.

## Reading from the camera is narrower than reading from a file

Most documented counters live in image metadata, not in a property the camera
will hand over on USB. So for many cameras the working route is:

```
camera-count exif <an original file from that camera>
```

rather than plugging the camera in. The tool says which applies.

## A file must be an original

A count read from an edited, exported, converted or re-saved file means
nothing, so files are checked first: camera identification, MakerNotes present,
no editing software recorded, a format a camera writes, dimensions matching
what the camera recorded, and no metadata warnings. A file that fails is
reported as `NOT AN ORIGINAL CAMERA FILE` and yields no count.

Consequences worth knowing:

- A photo sent through a messaging app, social network or cloud gallery will
  almost always fail. Those services strip metadata.
- A DNG produced by Adobe DNG Converter is a conversion, not an original.
- The dimension check is applied only to JPEG and HEIC. In a raw file the EXIF
  dimensions can legitimately describe an embedded preview, and a check that
  misfires would be worse than no check.

## What a count does not tell you

- **A counter may have been reset.** Some manufacturers document that servicing
  can reset it. An exact count is exact about what the counter says, not about
  the camera's whole life.
- **Counters count different things.** One camera's counter includes electronic
  shutter exposures; another's excludes live view and video. The report states
  which, from the source.
- **A shutter is not the only wearing part.** A low count is not a clean bill of
  health.

## Technical limits

- **Windows only.** Windows 10 and 11, x64.
- **No driver changes.** Cameras are reached through Windows Portable Devices.
  A camera that only works through a vendor WinUSB driver needs the optional
  `winusb` extra and a driver you installed yourself.
- **Mass-storage mode gives nothing.** Switch the camera to PTP / PC Remote /
  MTP.
- **A camera another program is holding cannot be read.** The tool names the
  holder rather than forcing it free.
- **No network access anywhere**, so there is no online database of counts to
  fall back on. That is a deliberate trade.
- **Releases are unsigned**, so SmartScreen will warn on first run.

## Things this program will never do

Estimate, extrapolate, interpolate, average, or infer a count. Derive one from
image numbers or file counts. Add counters together. Attach a confidence score.
Write anything to a camera. Send anything anywhere.
