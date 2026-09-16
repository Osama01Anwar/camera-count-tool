# Shutter-count methodology

## The rule

A number is shown only when it was read from a source that documents that
field, for that model, as an actuation counter. Everything else is
`EXACT SHUTTER COUNT NOT AVAILABLE` with a reason.

There is no second-best. A count that is probably right is worth less than no
count at all, because someone is about to spend money on it.

## What counts as an authoritative source

1. **A camera's own counter**, read through a documented device property or a
   documented vendor operation.
2. **A manufacturer's documented MakerNotes field**, read from an original
   camera file, where a public source states that this field is the actuation
   count for that model.

A source qualifies when you can point at where it is written down. "A tool I
used showed this number" is a lead, not a source.

## What is never used

- Image numbers, file indexes, file names, or the number of files on a card
- Timestamps, or intervals between them
- Frame or video counters
- Arithmetic across counters, unless the manufacturer documents that the sum
  means something
- Statistics, models, or machine learning of any kind
- Any metadata field not listed in the registry for that exact model

If a non-authoritative counter is present, it is shown under this notice:

> Image counter detected - not an authoritative shutter-count source.

and its value never fills a counter slot.

## Counters are kept separate

Four slots, each independent:

| Slot | Meaning |
|---|---|
| Mechanical shutter | Actuations of the physical shutter |
| Electronic shutter | Exposures made with the electronic shutter |
| Electronic first curtain | EFC actuations |
| Total releases | A manufacturer-defined total |

They are never added together. A camera that reports only a total gets one
populated slot and three that say `NOT AVAILABLE` - which is the honest
picture, because "mechanical = total - electronic" is arithmetic the
manufacturer did not authorise.

Which slot a reading belongs to is decided by the registry entry, not by the
code that read it.

## Verification status

- **`documented`** - a public source defines the field for that model. This is
  enough to display a number.
- **`hardware_verified`** - additionally, a human has confirmed on a physical
  body that the count increases by exactly the number of shutter presses they
  made, and the test is recorded in
  [hardware-test-matrix.md](hardware-test-matrix.md).
- **`unverified`** - a lead. Never displayed.

## Files record history, not the present

A count read from a file is the count *at the moment that frame was taken*. The
camera has been used since. The program says so:

> Historical exact counts found. Current count requires a current authoritative
> source.

## Caveats that belong to particular counters

Some documented counters carry caveats from the source itself, and those
caveats are carried into the report rather than quietly dropped. For example,
the Pentax counter's own documentation notes that it may be reset when a camera
is serviced and that it excludes live-view and video actuations. A count that
is exact is not automatically a count that means what a buyer assumes.

## When two sources disagree

They do not get averaged. Each documented counter is reported on its own, with
its own source, and the reader can see both.
