# Third-party components

Easy Scrcpy is an independent GUI, not an official Genymobile product.
The portable scrcpy distribution is bundled without source code modifications.
The packaging tool may adjust executable architecture / signatures for the app.
Its complete release contents (including libraries, LICENSE and server) are retained.

- scrcpy 5.0: Copyright (C) 2018 Genymobile; Copyright (C) 2018–2026 Romain Vimont.
  Apache-2.0; see ../LICENSE (or LICENSE at the bundle root).
  Source: https://github.com/Genymobile/scrcpy/tree/v5.0
- Android Debug Bridge / platform-tools 37.0.1: Android Open Source Project and
  its contributors. See licenses/platform-tools-NOTICE.txt for the original
  copyright notices and license texts of ADB and its third-party dependencies.
  Source: https://android.googlesource.com/platform/packages/modules/adb/
- FFmpeg 9.0.2: FFmpeg contributors, LGPL-2.1-or-later in the upstream build
  configuration. Source: https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz
- SDL 3.4.18: SDL contributors, zlib license.
  Source: https://github.com/libsdl-org/SDL/tree/release-3.4.18
- dav1d 1.5.4: VideoLAN and contributors, BSD-2-Clause.
  Source: https://code.videolan.org/videolan/dav1d/-/tree/1.5.4
- libusb: libusb contributors, LGPL-2.1-or-later.
  Source and build version: https://github.com/Genymobile/scrcpy/blob/v5.0/app/deps/libusb.sh
- Linux builds additionally include dependencies documented in upstream build scripts:
  https://github.com/Genymobile/scrcpy/tree/v5.0/app/deps
- PySide6 / Qt: The Qt Company and contributors, LGPLv3 / GPLv3 / commercial,
  depending on the module. The GUI uses the dynamically linked PySide6 wheels.
  Source: https://code.qt.io/ ; https://download.qt.io/official_releases/QtForPython/

Version and SHA-256 provenance is recorded in manifest.json. Platform-tools is
downloaded from dl.google.com; scrcpy is downloaded only from Genymobile's GitHub.

This notice is not a substitute for the license obligations of individual
components. Before public redistribution, collect the corresponding source,
all applicable license texts and (for statically linked LGPL libraries) the
materials needed to relink, following the upstream build scripts. Signing and
installation must not prevent a user's LGPL-permitted library replacement.
