# FAQ

### It says EXACT SHUTTER COUNT NOT AVAILABLE. Is it broken?

No. That is a correct result. It means no source documents how to read an
actuation counter for that camera, or the file you gave it is not an original.
The reason is printed underneath.

### Another tool showed me a number for the same camera. Who is right?

Possibly both, possibly neither. The question to ask that other tool is *where
did that number come from?* If it can point at a documented field for your
exact model, that is a source worth adding here - please
[open an issue](https://github.com/Osama01Anwar/camera-count-tool/issues/new/choose)
with the citation. If it cannot, it may be reading an image counter, a field
that means something else on your model, or a guess.

### Why does my camera work with an image file but not over USB?

Most documented counters live in image metadata rather than in a property the
camera exposes over USB. Run `camera-count exif` on an original file from that
camera.

### Why was my photo rejected as "not an original camera file"?

Something rewrote it. Messaging apps, social networks, cloud galleries, editors
and converters all strip or rewrite metadata. Use a file copied straight off the
memory card or out of the camera.

The tool prints which check failed and what it saw, so you can tell the
difference between "this was resized" and "this was saved by Lightroom".

### It was rejected for software made by the camera's own manufacturer. Really?

Yes. Nikon Capture, NX Studio, Canon Digital Photo Professional, Sony Imaging
Edge and their equivalents rewrite the file when they save it. Once that has
happened the camera is no longer the author of the metadata, and the whole basis
for trusting a field in it is gone.

The count in such a file is often still correct - but "often" is not what this
tool is for. Ask for a file copied straight off the card.

### Does it work with raw files?

Yes - NEF, CR2, CR3, ARW, RAF, RW2, ORF, PEF, DNG and the rest. Raw files are
usually the best evidence because they are the least likely to have been
rewritten.

### Can it damage my camera or delete my photos?

No. It never writes to the camera: no settings, no shutter release, no file
changes, no formatting, no firmware, no counter resets. Every operation is
checked against a read-only allow-list before it is sent, the transport has no
way to send data to the device, and the device is opened with read-only access.

### Does it send my data anywhere?

No. There is no network code in the program at all, and a test fails the build
if any appears. Everything stays on your machine.

### What is stored on my machine?

Inspection results in a local SQLite database under your app data folder, plus
any report you save. The only personal data is whatever you type into a report
as a seller or buyer note.

### Why does Windows warn when I run it?

Releases are not code-signed. Check the SHA-256 against `SHA256SUMS.txt` in the
release, then choose **More info → Run anyway**.

### Why does it need ExifTool?

Reading manufacturer MakerNotes correctly across hundreds of models is a large,
carefully maintained body of work, and ExifTool is that work. Packaged releases
bundle it, so you do not need to install anything.

### My camera shows an "image counter". Is that the shutter count?

No. It counts saved images. Deleting, formatting, shooting raw+JPEG, bracketing
and in-camera processing all break the relationship between images saved and
shutter actuations. The tool shows it under a notice and never in a count slot.

### Can I trust a count from a seller's file?

You can trust that the file says it. Check that the tool reports it as an
original camera file, check the capture date, and remember that the camera has
been used since that frame was taken.

### Can you add my camera?

If you can cite a source that documents the field for that exact model, yes -
see [adding-camera-model.md](adding-camera-model.md). Without a citation, no,
and that is the point of the project.
