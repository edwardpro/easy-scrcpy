# Easy Scrcpy v0.1.0

Easy Scrcpy is an independent, cross-platform GUI and system tray companion for [scrcpy](https://github.com/Genymobile/scrcpy).

## Highlights

- **Bundled tools:** Includes scrcpy 5.0, ADB 37.0.1, and companion files. No separate Python, scrcpy, or ADB installation is required for packaged apps.
- **Tray integration:** Runs in the macOS menu bar or Windows / Ubuntu system tray. Closing the device panel keeps the app running.
- **USB device detection:** Detects Android devices and asks whether to start mirroring once authorized.
- **Multiple devices:** Mirror several phones in independent windows; stop one session or all sessions.
- **Disconnect cleanup:** Stops the corresponding mirroring process when a device is unplugged or goes offline.
- **Per-device quality:** Choose Smooth, Standard, High quality, Custom, or Global settings. Adjust resolution limits, frame rate, and video bit rate. Changing quality restarts only that device's session without disabling USB debugging.
- **Login startup:** Optional startup at user login on macOS, Windows, and Ubuntu.
- **Five languages:** English, Simplified Chinese, French, German, and Japanese, with automatic system-language detection and live switching.
- **Optional USB debugging shutdown:** Disabled by default. When enabled, manual Stop attempts to disable USB debugging before stopping mirroring. If successful, you must re-enable USB debugging on the phone before the next session.
- **Diagnostics:** Device status, bounded logs, error messages, and single-instance protection.

## Downloads and installation

Download the package that matches your operating system and CPU architecture from this release's assets.

| Platform | Package | How to run |
| --- | --- | --- |
| macOS | `.zip` containing `EasyScrcpy.app` | Extract and open the app. You may move it to Applications. |
| Windows | `.zip` containing the complete `EasyScrcpy` folder | Extract all files and run `EasyScrcpy.exe`. Keep its companion files in place. |
| Ubuntu | `.tar.gz` containing the complete `EasyScrcpy` folder | Extract and run `./EasyScrcpy/EasyScrcpy` from the extraction directory. |

These are portable application packages, not DMG, MSI, or DEB installers. Available architectures depend on the assets attached to this release; packages are not universal binaries.

## Phone setup

1. Enable developer options and **USB debugging** on your Android phone.
2. Connect it with a USB cable that supports data transfer.
3. Accept the computer's debugging authorization prompt on the phone.
4. Start Easy Scrcpy and accept the mirroring prompt, or select **Start mirroring** in the device panel.

Android 5.0 or later is required. Audio forwarding requires Android 11 or later. ADB cannot enable USB debugging before a debugging connection exists or bypass phone authorization.

## Known limitations

- Packages are not yet signed / notarized for public distribution; macOS or Windows may display security warnings.
- Some Windows devices need OEM USB drivers. Ubuntu requires appropriate USB permissions / udev rules and desktop graphics libraries.
- Some Ubuntu GNOME environments need an AppIndicator extension to display tray icons. Wayland controls whether prompts receive focus.
- Disabling USB debugging is device-dependent and may be denied. Even when the command returns successfully, verify the setting on the phone. It affects all ADB connections to that phone, not just Easy Scrcpy.
- Ubuntu ARM64 bundles are not currently supported. Other architectures are available only when matching packages are attached.
- Real-device compatibility and platform-specific behavior should be verified on your hardware; automated tests do not replace end-to-end device testing.

## Maintainers

The repository includes a verified dependency update script, cross-platform GitHub Actions builds, and 45 automated tests passing locally at the time these notes were written.

Before public binary distribution, complete signing / notarization as appropriate and review third-party license obligations, including corresponding source and relinking materials for statically linked LGPL dependencies. See `packaging/THIRD_PARTY_NOTICES.md`.

Easy Scrcpy is an unofficial GUI, not an official Genymobile product. scrcpy and other bundled components remain the property of their respective authors and are distributed under their own licenses.
