# Contributing

Bug reports, device information and small, tested improvements are welcome.

For a device report, include the product name, USB VID/PID, macOS version,
Python version and a redacted report-descriptor summary. Do not publish serial
numbers, private macros or complete dumps without reviewing their contents.

Keep UI text, docstrings and concise code comments in English. Run the test and
formatting commands in the README before submitting a pull request.

New device support needs descriptor/firmware validation, demonstrated read
semantics, a backup before every write, and exact readback checks. Never add
an unknown device to the writer solely because its name or case looks similar.
Document physical mappings as observed or inferred, and retain raw custom
assignments instead of replacing unknown values with zeroes.

Hardware tests that change assignments should be explicit and reversible.
The normal test suite and GUI demo must never access a physical HID device.

Contributions to GLRA Studio are provided under GPL-3.0-only, the project license.
