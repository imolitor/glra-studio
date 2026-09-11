# Protocol notes

This implementation was derived from public manufacturer JavaScript and
observations on one G-LRA k16_n3, USB `36ae:2475`, protocol 1, internal PID
`246d`, firmware value 100. Do not assume all similarly named pads share it.

## Transport

Vendor interface: usage page `ff00`, usage `02`, unnumbered 64-byte Input and
Output reports, no Feature reports. HIDAPI adds a leading zero report-ID byte
when sending (65 bytes total). Input bytes begin with a vendor header, not a
HID report-ID prefix. The exact report descriptor is checked before protocol I/O.

| Purpose | 64-byte payload prefix (without HIDAPI zero) | Observed reply |
|---|---|---|
| Status | `06 05` | `aa 05`; status starts at byte 5 |
| Assignment read | `06 08 3a offLo offHi 00 profile 00` | `aa 07 3a offLo offHi`; 56 bytes at byte 8 |
| Single assignment | `06 10 07 offLo offHi 00 profile 00 type code1 code2 code3` | `aa 10 01`; assigned value at byte 8 |
| Macro read | `06 0c length offLo offHi` | `aa 0c`; data at byte 8 |
| RGB read | `06 13 3a offLo offHi` | `aa 13`; data at byte 8 |
| Light read | `06 0a` | `aa 0a` |
| URL read | `06 41 length offLo offHi` | No matching reply on the tested firmware |

Unspecified output bytes are zero. Assignment offset is four times the raw
slot index. A standard keyboard assignment is `20 modifierMask usage 00`.
Consumer assignments observed were `30 e2 00 00` (mute), `30 e9 00 00`
(volume up), `30 ea 00 00` (volume down).

## Physical layout

The proposed four keyboard rows map to `[0,1,2,3]`, `[7,8,9,10]`,
`[14,15,16,17]`, `[21,22,23,24]`. Encoder groups (press, clockwise,
counterclockwise) are `(4,5,6)`, `(11,12,13)`, `(18,19,20)`.

Only key 0 and encoder group 4/5/6 were independently programmed and physically
verified during initial development. Other displayed positions are inferred and
require the app's explicit temporary-marker verification before edits.

All three original encoders produced identical media reports. Passive reports
alone cannot identify the physical source when assignments are duplicated.

## Transaction guarantees and limits

Before each assignment write, status and all six 576-byte read windows are
sampled twice. The original data is saved to a new private JSON file, with a
SHA-256 checksum, before USB output. Expected old value, tested firmware and
active profile are checked. Afterward the same windows are read again; exactly
one intended four-byte difference and a matching acknowledgement are required.

The broader windows contain repeated patterns. They are retained for comparison,
not interpreted as proven independent profile memories. No claim of full flash
backup, cross-firmware compatibility or power-cycle persistence is made.

Unknown acknowledgements, stale state and inconsistent readback are errors, not
successes. Failed transactions retain backup/error files. Temporary calibration
also writes a recovery journal before sending its marker and restores only when
the current value is the original or the expected marker.

The macOS HIDAPI manager is initialized on the main thread before the worker
starts. This avoids destroying its originating run loop before HIDAPI's exit
cleanup. Device operations themselves run serially on the worker.

## Sources

Public manufacturer bundle inspected on 2026-09-11:

- [Manufacturer configurator](https://www.sdcx-tech.com/)
- [Application bundle](https://www.sdcx-tech.com/_next/static/chunks/app/page-bb948a9e8b9c0440.js)
- [Comparison layout, different VID](https://www.sdcx-tech.com/_next/static/chunks/9125.a51129fa762fa1ff.js)
- [HIDAPI](https://github.com/libusb/hidapi)
- [Python HIDAPI binding](https://github.com/trezor/cython-hidapi)

No manufacturer code bundle or personal device dump is included in this repository.
