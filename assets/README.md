# Application artwork

Save the supplied artwork here:

- `icon.png`: large square application icon (recommended 1024 × 1024).
- `tray-icon.png`: small square tray icon (recommended 64 × 64).

The app loads these images directly. Larger square originals are accepted and
resized during packaging without cropping or changing the background.

Run `uv run --extra build python packaging/prepare_icons.py` to generate
`build/icons/icon.icns`, `icon.ico`, and the 512 px Linux `icon.png`.
The PyInstaller spec also runs this step automatically when `icon.png` exists.

将大图保存为 `icon.png`，小图保存为 `tray-icon.png`。保留原图；生成的平台图标在 `build/icons/`，不提交到 Git。彩色托盘图标不会被作为 macOS 单色模板处理。
