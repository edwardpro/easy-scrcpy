# Application artwork

Save the supplied artwork here:

- `icon.png`: large square application icon (recommended 1024 × 1024).
- `tray-icon.png`: small square tray icon (recommended 64 × 64).
- `tray-icon-mac.png`: monochrome macOS tray artwork. White areas become
  transparent at runtime; black areas form a template automatically tinted by
  macOS for light / dark menu bars. Windows and Ubuntu use `tray-icon.png`.

The app loads these images directly. Larger square originals are accepted and
resized during packaging without cropping or changing the background.

Run `uv run --extra build python packaging/prepare_icons.py` to generate
`build/icons/icon.icns`, `icon.ico`, and the 512 px Linux `icon.png`.
The PyInstaller spec also runs this step automatically when `icon.png` exists.

将大图保存为 `icon.png`，彩色小图保存为 `tray-icon.png`，macOS 单色小图保存为 `tray-icon-mac.png`。保留原图；生成的平台图标在 `build/icons/`，不提交到 Git。macOS 单色图的白色区域转为透明，并使用系统模板着色；其他平台仍使用彩色图。
