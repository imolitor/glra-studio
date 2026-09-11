# Third-party components

The MIT license in this repository applies to GLRA Studio's own source code.
Dependencies retain their own licenses. Their source and license notices are
available from the projects below; no vendor JavaScript bundle is redistributed.

| Component | Version | Upstream and license information |
|---|---|---|
| PySide6 / Qt for Python | 6.10.2 | [Qt for Python](https://doc.qt.io/qtforpython-6/index.html), LGPLv3/GPLv3 or commercial terms |
| Qt | bundled by PySide6 | [Open-source licensing](https://www.qt.io/licensing/open-source-lgpl-obligations) |
| cython-hidapi | 0.15.0 | [Source and licenses](https://github.com/trezor/cython-hidapi) |
| HIDAPI | bundled by cython-hidapi | [Upstream license alternatives](https://github.com/libusb/hidapi#license) |

GLRA Studio uses Qt Core, Gui, QML, Quick and Quick Controls. Packaging a binary
must preserve applicable third-party license notices and comply with the terms
of the bundled dependencies. This initial release distributes source and a
Python wheel, not a signed or notarized macOS application bundle.

GLRA Studio is an independent community project, not an official product of
G-LRA, Shenzhen Hengchengyi, Qt, or Apple. Device names identify compatibility.
