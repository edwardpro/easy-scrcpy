"""Small bundled translation catalog; no runtime files or network required."""

LANGUAGES = {"auto": "System / 系统", "en": "English", "zh": "简体中文", "fr": "Français",
             "de": "Deutsch", "ja": "日本語"}
_language = "zh"

# Chinese source text, then English / French / German / Japanese.
ROWS = [
    ("重新投屏", "Restart", "Redémarrer", "Neustarten", "再起動"),
    ("通知权限…", "Notification permissions…", "Autorisations de notification…", "Benachrichtigungsrechte…", "通知の許可…"),
    ("设备通知不可用：{error}", "Device notifications unavailable: {error}", "Notifications indisponibles : {error}", "Gerätebenachrichtigungen nicht verfügbar: {error}", "デバイス通知は利用できません：{error}"),
    ("音频码率", "Audio bit rate", "Débit audio", "Audio-Bitrate", "音声ビットレート"),
    ("画质", "Quality", "Qualité", "Bildqualität", "画質"),
    ("跟随全局设置", "Global settings", "Paramètres globaux", "Globale Einstellungen", "全体設定に従う"),
    ("流畅", "Smooth", "Fluide", "Flüssig", "スムーズ"),
    ("标准", "Standard", "Standard", "Standard", "標準"),
    ("高清", "High quality", "Haute qualité", "Hohe Qualität", "高画質"),
    ("自定义", "Custom", "Personnalisé", "Benutzerdefiniert", "カスタム"),
    ("自定义画质", "Custom quality", "Qualité personnalisée", "Benutzerdefinierte Bildqualität", "画質のカスタマイズ"),
    ("调整…", "Adjust…", "Régler…", "Anpassen…", "調整…"),
    ("视频码率", "Video bit rate", "Débit vidéo", "Video-Bitrate", "映像ビットレート"),
    ("画质参数超出范围", "Quality options are invalid or out of range", "Paramètres de qualité invalides ou hors limites", "Bildqualitätsparameter ungültig oder außerhalb des Bereichs", "画質設定が不正または範囲外です"),
    ("修改画质会重启该设备投屏，不会关闭 USB 调试；只影响投屏画面，不修改手机屏幕分辨率。", "Changing quality restarts this device's mirror without disabling USB debugging. It affects only the mirrored image, not the phone's display resolution.", "Modifier la qualité redémarre la recopie de cet appareil sans désactiver le débogage USB. Seule l’image recopiée change, pas la résolution de l’écran du téléphone.", "Änderungen starten nur die Spiegelung dieses Geräts neu, ohne USB-Debugging zu deaktivieren. Die Bildschirmauflösung des Telefons bleibt unverändert.", "画質変更はこの端末のミラーリングのみを再起動します。USBデバッグは無効化せず、端末の画面解像度も変更しません。"),
    ("画质参数：最大边长 {size}，{fps} FPS，{bitrate} Mbps", "Quality: max dimension {size}, {fps} FPS, {bitrate} Mbps", "Qualité : dimension max. {size}, {fps} FPS, {bitrate} Mbps", "Bildqualität: maximale Kante {size}, {fps} FPS, {bitrate} Mbps", "画質：最大辺長{size}、{fps} FPS、{bitrate} Mbps"),
    ("正在重启设备投屏以应用画质：{serial}", "Restarting mirror to apply quality: {serial}", "Redémarrage de la recopie pour appliquer la qualité : {serial}", "Spiegelung für neue Bildqualität wird neu gestartet: {serial}", "画質を適用するためミラーリングを再起動：{serial}"),
    ("USB 调试", "USB debugging", "Débogage USB", "USB-Debugging", "USBデバッグ"),
    ("停止投屏时尝试关闭 USB 调试", "Try to disable USB debugging when stopping mirroring", "Essayer de désactiver le débogage USB à l’arrêt de la recopie", "Beim Stoppen USB-Debugging zu deaktivieren versuchen", "停止時にUSBデバッグの無効化を試みる"),
    ("默认关闭。部分手机会拒绝；成功后影响该手机的所有 ADB 连接，下次需在手机上手动开启 USB 调试。", "Off by default. Some phones deny this request. If successful, all ADB connections to this phone are affected; re-enable USB debugging manually on the phone next time.", "Désactivé par défaut. Certains téléphones refusent. En cas de succès, toutes les connexions ADB du téléphone sont affectées ; réactivez le débogage USB manuellement sur le téléphone.", "Standardmäßig aus. Manche Telefone lehnen dies ab. Bei Erfolg sind alle ADB-Verbindungen zum Telefon betroffen; USB-Debugging muss danach am Telefon manuell aktiviert werden.", "既定では無効です。拒否される端末もあります。成功すると端末のすべてのADB接続に影響します。次回は端末でUSBデバッグを手動で有効にしてください。"),
    ("无法关闭 USB 调试 ({serial})：找不到 ADB；仍会停止投屏。", "Cannot disable USB debugging ({serial}): ADB not found. Mirroring will still stop.", "Impossible de désactiver le débogage USB ({serial}) : ADB introuvable. La recopie sera arrêtée.", "USB-Debugging kann nicht deaktiviert werden ({serial}): ADB fehlt. Spiegelung wird dennoch gestoppt.", "USBデバッグを無効化できません（{serial}）：ADBがありません。ミラーリングは停止します。"),
    ("无法确认 USB 调试已关闭 ({serial})：{error}；仍会停止投屏。请在手机上检查。", "Cannot confirm USB debugging is disabled ({serial}): {error}. Mirroring will still stop. Check on your phone.", "Impossible de confirmer la désactivation du débogage USB ({serial}) : {error}. La recopie sera arrêtée. Vérifiez sur le téléphone.", "Deaktivierung von USB-Debugging nicht bestätigt ({serial}): {error}. Spiegelung wird dennoch gestoppt. Bitte am Telefon prüfen.", "USBデバッグの無効化を確認できません（{serial}）：{error}。ミラーリングは停止します。端末で確認してください。"),
    ("请求超时", "Request timed out", "Délai de requête dépassé", "Zeitüberschreitung", "要求がタイムアウトしました"),
    ("已发送关闭 USB 调试请求 ({serial})；请在手机上确认，下次投屏需手动开启。", "USB debugging disable request sent ({serial}). Check on your phone; manually re-enable it for the next session.", "Demande de désactivation du débogage USB envoyée ({serial}). Vérifiez sur le téléphone ; réactivez-le manuellement pour la prochaine session.", "Deaktivierung von USB-Debugging angefordert ({serial}). Am Telefon prüfen; für die nächste Sitzung manuell aktivieren.", "USBデバッグ無効化を要求しました（{serial}）。端末で確認し、次回は手動で有効にしてください。"),
    ("正在尝试关闭 USB 调试 ({serial})…", "Trying to disable USB debugging ({serial})…", "Tentative de désactivation du débogage USB ({serial})…", "USB-Debugging wird zu deaktivieren versucht ({serial})…", "USBデバッグの無効化を試行中（{serial}）…"),
    ("Easy Scrcpy · USB 设备投屏", "Easy Scrcpy · USB mirroring", "Easy Scrcpy · Recopie USB", "Easy Scrcpy · USB-Spiegelung", "Easy Scrcpy · USBミラーリング"),
    ("正在检查运行环境…", "Checking environment…", "Vérification de l’environnement…", "Umgebung wird geprüft…", "実行環境を確認中…"),
    ("设备", "Device", "Appareil", "Gerät", "デバイス"),
    ("序列号", "Serial number", "Numéro de série", "Seriennummer", "シリアル番号"),
    ("状态", "Status", "État", "Status", "状態"),
    ("操作", "Actions", "Actions", "Aktionen", "操作"),
    ("连接手机 → 开启开发者选项 / USB 调试 → 在手机上允许此电脑调试。\n未开启 USB 调试的手机可能不会出现在列表中。拒绝投屏后可在这里手动启动。", "Connect your phone → Enable developer options / USB debugging → Authorize this computer on your phone.\nPhones without USB debugging may not appear. You can start mirroring here after declining the prompt.", "Connectez le téléphone → Activez les options développeur / le débogage USB → Autorisez cet ordinateur sur le téléphone.\nSans débogage USB, le téléphone peut ne pas apparaître. Vous pouvez lancer la recopie ici après avoir refusé l’invite.", "Telefon verbinden → Entwickleroptionen / USB-Debugging aktivieren → Diesen Computer am Telefon autorisieren.\nOhne USB-Debugging erscheint das Telefon möglicherweise nicht. Nach Ablehnen der Nachfrage können Sie die Spiegelung hier starten.", "スマートフォンを接続 → 開発者向けオプション／USBデバッグを有効化 → スマートフォンでこのPCを許可。\nUSBデバッグが無効だと表示されない場合があります。確認を断った後もここから開始できます。"),
    ("USB 设备", "USB devices", "Appareils USB", "USB-Geräte", "USBデバイス"),
    ("运行日志", "Logs", "Journaux", "Protokoll", "ログ"),
    ("设置", "Settings", "Paramètres", "Einstellungen", "設定"),
    ("停止全部投屏", "Stop all mirroring", "Arrêter toutes les recopies", "Alle Spiegelungen stoppen", "すべて停止"),
    ("退出应用", "Quit application", "Quitter l’application", "Anwendung beenden", "アプリを終了"),
    ("退出", "Quit", "Quitter", "Beenden", "終了"),
    ("已就绪", "Ready", "Prêt", "Bereit", "準備完了"),
    ("请在手机上授权", "Authorize on your phone", "Autorisez sur le téléphone", "Am Telefon autorisieren", "スマートフォンで許可してください"),
    ("离线", "Offline", "Hors ligne", "Offline", "オフライン"),
    ("缺少 USB 权限（检查 udev 规则）", "USB permission missing (check udev rules)", "Permission USB manquante (vérifiez les règles udev)", "USB-Berechtigung fehlt (udev-Regeln prüfen)", "USB権限がありません（udevルールを確認）"),
    ("正在停止…", "Stopping…", "Arrêt en cours…", "Wird gestoppt…", "停止中…"),
    ("正在停止", "Stopping", "Arrêt en cours", "Wird gestoppt", "停止中"),
    ("投屏中", "Mirroring", "Recopie en cours", "Spiegelung läuft", "ミラーリング中"),
    ("停止投屏", "Stop mirroring", "Arrêter la recopie", "Spiegelung stoppen", "ミラーリングを停止"),
    ("开始投屏", "Start mirroring", "Lancer la recopie", "Spiegelung starten", "ミラーリングを開始"),
    ("ADB 路径", "ADB path", "Chemin d’ADB", "ADB-Pfad", "ADBのパス"),
    ("scrcpy 路径", "scrcpy path", "Chemin de scrcpy", "scrcpy-Pfad", "scrcpyのパス"),
    ("留空使用内置版本；可指定外部可执行文件", "Leave blank to use bundled tools; or choose an external executable", "Laissez vide pour utiliser les outils intégrés, ou choisissez un exécutable externe", "Leer lassen für integrierte Tools oder externe Programmdatei wählen", "空欄で内蔵版を使用。外部の実行ファイルも指定できます"),
    ("浏览…", "Browse…", "Parcourir…", "Durchsuchen…", "参照…"),
    ("用户登录后自动启动并常驻托盘", "Start in the tray when you sign in", "Démarrer dans la zone de notification à la connexion", "Bei Anmeldung im Infobereich starten", "ログイン時に起動しトレイに常駐"),
    ("登录自启动", "Start at login", "Démarrage à la connexion", "Autostart bei Anmeldung", "ログイン時に起動"),
    ("USB 设备就绪时询问是否投屏", "Ask to mirror when a USB device is ready", "Proposer la recopie lorsqu’un appareil USB est prêt", "Bei bereitem USB-Gerät nach Spiegelung fragen", "USBデバイスの準備完了時に開始を確認"),
    ("设备连接", "Device connection", "Connexion d’appareil", "Geräteverbindung", "デバイス接続"),
    ("原始分辨率", "Original resolution", "Résolution d’origine", "Originalauflösung", "元の解像度"),
    ("最大画面边长", "Maximum screen dimension", "Dimension maximale de l’écran", "Maximale Bildschirmkante", "画面の最大辺長"),
    ("最大帧率", "Maximum frame rate", "Fréquence d’images maximale", "Maximale Bildrate", "最大フレームレート"),
    ("转发音频（需要 Android 11 或更高）", "Forward audio (Android 11 or later)", "Transférer l’audio (Android 11 ou ultérieur)", "Audio übertragen (Android 11 oder neuer)", "音声転送（Android 11以降）"),
    ("音频", "Audio", "Audio", "Audio", "音声"),
    ("关闭窗口仍会常驻托盘。投屏参数修改对下一次启动生效。\n自启动使用当前安装位置；移动应用或虚拟环境后请重新设置。", "Closing the window keeps the app in the tray. Mirroring changes apply to the next session.\nLogin startup uses the current installation path; reconfigure it after moving the app or virtual environment.", "Fermer la fenêtre laisse l’application dans la zone de notification. Les paramètres de recopie s’appliquent à la prochaine session.\nLe démarrage utilise le chemin actuel ; reconfigurez-le après avoir déplacé l’application ou l’environnement virtuel.", "Beim Schließen bleibt die App im Infobereich. Spiegelungsänderungen gelten für die nächste Sitzung.\nAutostart verwendet den aktuellen Installationspfad; nach Verschieben der App oder Umgebung neu einstellen.", "ウィンドウを閉じてもトレイに常駐します。投屏設定は次回の開始時に適用されます。\n自動起動には現在の配置パスを使用します。アプリや仮想環境を移動した場合は再設定してください。"),
    ("语言", "Language", "Langue", "Sprache", "言語"),
    ("跟随系统", "System default", "Langue du système", "Systemsprache", "システムに従う"),
    ("保存", "Save", "Enregistrer", "Speichern", "保存"),
    ("取消", "Cancel", "Annuler", "Abbrechen", "キャンセル"),
    ("是", "Yes", "Oui", "Ja", "はい"),
    ("否", "No", "Non", "Nein", "いいえ"),
    ("确定", "OK", "OK", "OK", "OK"),
    ("选择 {name} 可执行文件", "Choose {name} executable", "Choisir l’exécutable {name}", "Programmdatei für {name} wählen", "{name}の実行ファイルを選択"),
    ("路径无效", "Invalid path", "Chemin invalide", "Ungültiger Pfad", "無効なパス"),
    ("{name} 路径不是可执行文件。", "The {name} path is not an executable file.", "Le chemin de {name} ne désigne pas un fichier exécutable.", "Der {name}-Pfad ist keine ausführbare Datei.", "{name}のパスは実行ファイルではありません。"),
    ("无法保存设置", "Could not save settings", "Impossible d’enregistrer les paramètres", "Einstellungen konnten nicht gespeichert werden", "設定を保存できません"),
    ("\n自启动恢复失败：{error}", "\nCould not restore login startup: {error}", "\nImpossible de rétablir le démarrage : {error}", "\nAutostart konnte nicht wiederhergestellt werden: {error}", "\n自動起動の復元に失敗：{error}"),
    ("系统托盘不可用：保留主窗口；Ubuntu GNOME 可能需要 AppIndicator 扩展。", "System tray unavailable: keeping the main window open. Ubuntu GNOME may need the AppIndicator extension.", "Zone de notification indisponible : la fenêtre reste ouverte. Ubuntu GNOME peut nécessiter l’extension AppIndicator.", "Infobereich nicht verfügbar: Hauptfenster bleibt offen. Ubuntu GNOME benötigt eventuell AppIndicator.", "トレイが利用できないためメイン画面を表示します。Ubuntu GNOMEではAppIndicator拡張が必要な場合があります。"),
    ("尚未找到 scrcpy：请检查内置依赖是否完整，开发环境先运行依赖准备脚本。", "scrcpy not found: check the bundled tools. In development, run the dependency preparation script first.", "scrcpy introuvable : vérifiez les outils intégrés. En développement, lancez d’abord le script de préparation.", "scrcpy nicht gefunden: integrierte Tools prüfen. In der Entwicklung zuerst das Vorbereitungsskript ausführen.", "scrcpyが見つかりません。内蔵ファイルを確認してください。開発時は依存関係準備スクリプトを先に実行してください。"),
    ("Easy Scrcpy · {devices} 台设备 · {mirrors} 路投屏", "Easy Scrcpy · {devices} device(s) · {mirrors} mirror(s)", "Easy Scrcpy · {devices} appareil(s) · {mirrors} recopie(s)", "Easy Scrcpy · {devices} Gerät(e) · {mirrors} Spiegelung(en)", "Easy Scrcpy · デバイス{devices}台 · ミラーリング{mirrors}件"),
    ("打开设备面板", "Open device panel", "Ouvrir le panneau des appareils", "Geräteübersicht öffnen", "デバイスパネルを開く"),
    ("未发现 USB Android 设备", "No USB Android devices found", "Aucun appareil Android USB détecté", "Keine USB-Android-Geräte gefunden", "USB Androidデバイスが見つかりません"),
    ("设置…", "Settings…", "Paramètres…", "Einstellungen…", "設定…"),
    ("设备断开或失去就绪状态：{serial}，停止对应投屏。", "Device disconnected or no longer ready: {serial}. Stopping its mirror.", "Appareil déconnecté ou indisponible : {serial}. Arrêt de sa recopie.", "Gerät getrennt oder nicht mehr bereit: {serial}. Spiegelung wird gestoppt.", "デバイス切断または準備状態喪失：{serial}。対応するミラーリングを停止します。"),
    ("请在手机上授权 USB 调试", "Authorize USB debugging on your phone", "Autorisez le débogage USB sur le téléphone", "USB-Debugging am Telefon autorisieren", "スマートフォンでUSBデバッグを許可してください"),
    ("发现 Android 设备", "Android device detected", "Appareil Android détecté", "Android-Gerät erkannt", "Androidデバイスを検出"),
    ("{device}\n\n是否开始投屏？", "{device}\n\nStart mirroring?", "{device}\n\nLancer la recopie ?", "{device}\n\nSpiegelung starten?", "{device}\n\nミラーリングを開始しますか？"),
    ("设置已保存；新的投屏参数在下一次启动时生效。", "Settings saved. New mirroring options apply to the next session.", "Paramètres enregistrés. Les options de recopie s’appliqueront à la prochaine session.", "Einstellungen gespeichert. Neue Spiegelungsoptionen gelten für die nächste Sitzung.", "設定を保存しました。新しいミラーリング設定は次回の開始時に適用されます。"),
    ("应用已经运行，请通过系统托盘打开。", "The app is already running. Open it from the system tray.", "L’application est déjà en cours d’exécution. Ouvrez-la depuis la zone de notification.", "Die App läuft bereits. Öffnen Sie sie über den Infobereich.", "アプリはすでに起動しています。システムトレイから開いてください。"),
    ("读取设置失败，暂用默认值（原文件未修改）：{error}", "Could not read settings; using defaults (original file unchanged): {error}", "Lecture des paramètres impossible ; valeurs par défaut utilisées (fichier inchangé) : {error}", "Einstellungen nicht lesbar; Standardwerte werden verwendet (Originaldatei unverändert): {error}", "設定を読み込めません。既定値を使用します（元のファイルは変更していません）：{error}"),
    ("正在监听 USB Android 设备", "Watching for USB Android devices", "Détection des appareils Android USB", "USB-Android-Geräte werden überwacht", "USB Androidデバイスを監視中"),
    ("找不到 ADB：内置依赖可能缺失，请重新安装应用或在设置中指定路径。", "ADB not found: bundled tools may be missing. Reinstall the app or specify a path in Settings.", "ADB introuvable : les outils intégrés sont peut-être absents. Réinstallez l’application ou indiquez un chemin.", "ADB nicht gefunden: integrierte Tools fehlen möglicherweise. App neu installieren oder Pfad einstellen.", "ADBが見つかりません。内蔵ファイルが欠落している可能性があります。再インストールするか設定でパスを指定してください。"),
    ("ADB 查询超时；保留上次设备状态，稍后重试。", "ADB query timed out; keeping previous device state and retrying later.", "Délai ADB dépassé ; état précédent conservé, nouvelle tentative ultérieure.", "ADB-Abfrage abgelaufen; letzter Gerätestatus bleibt erhalten, erneuter Versuch folgt.", "ADB照会がタイムアウトしました。前回の状態を保持し、後で再試行します。"),
    ("无法启动 ADB：{error}", "Could not start ADB: {error}", "Impossible de démarrer ADB : {error}", "ADB konnte nicht gestartet werden: {error}", "ADBを起動できません：{error}"),
    ("ADB 查询失败：{error}", "ADB query failed: {error}", "Échec de la requête ADB : {error}", "ADB-Abfrage fehlgeschlagen: {error}", "ADB照会に失敗：{error}"),
    ("设备尚未就绪，请在手机上开启 USB 调试并确认授权。", "Device not ready. Enable USB debugging and authorize this computer on your phone.", "Appareil indisponible. Activez le débogage USB et autorisez cet ordinateur sur le téléphone.", "Gerät nicht bereit. USB-Debugging aktivieren und Computer am Telefon autorisieren.", "デバイスが未準備です。スマートフォンでUSBデバッグを有効にし、このPCを許可してください。"),
    ("找不到 scrcpy 或 ADB：请检查应用包是否完整，或在设置中指定外部路径。", "scrcpy or ADB not found. Check the app bundle or specify external paths in Settings.", "scrcpy ou ADB introuvable. Vérifiez l’application ou indiquez des chemins externes.", "scrcpy oder ADB nicht gefunden. App-Paket prüfen oder externe Pfade einstellen.", "scrcpyまたはADBが見つかりません。アプリのファイルを確認するか設定で外部パスを指定してください。"),
    ("无法启动 scrcpy ({serial})：{error}", "Could not start scrcpy ({serial}): {error}", "Impossible de démarrer scrcpy ({serial}) : {error}", "scrcpy konnte nicht gestartet werden ({serial}): {error}", "scrcpyを起動できません（{serial}）：{error}"),
    ("投屏异常退出 ({serial})，退出码 {code}\n{output}", "Mirroring exited unexpectedly ({serial}), exit code {code}\n{output}", "Recopie interrompue ({serial}), code de sortie {code}\n{output}", "Spiegelung unerwartet beendet ({serial}), Exit-Code {code}\n{output}", "ミラーリングが異常終了（{serial}）、終了コード{code}\n{output}"),
    ("设置文件必须为 JSON 对象", "Settings must be a JSON object", "Les paramètres doivent être un objet JSON", "Einstellungen müssen ein JSON-Objekt sein", "設定ファイルはJSONオブジェクトである必要があります"),
    ("设置类型错误：{key}", "Invalid setting type: {key}", "Type de paramètre invalide : {key}", "Ungültiger Einstellungstyp: {key}", "設定の型が不正：{key}"),
    ("投屏分辨率或帧率设置超出范围", "Mirroring resolution or frame rate is out of range", "Résolution ou fréquence d’images hors limites", "Spiegelungsauflösung oder Bildrate außerhalb des Bereichs", "解像度またはフレームレートが範囲外です"),
    ("不支持的语言：{language}", "Unsupported language: {language}", "Langue non prise en charge : {language}", "Nicht unterstützte Sprache: {language}", "未対応の言語：{language}"),
]

CATALOG = {lang: {row[0]: row[index] for row in ROWS}
           for index, lang in enumerate(("zh", "en", "fr", "de", "ja"))}


def language_for_locale(name: str) -> str:
    language = name.replace("-", "_").split("_")[0].lower()
    return language if language in CATALOG else "en"


def set_language(language: str):
    global _language
    if language == "auto":
        from PySide6.QtCore import QLocale
        languages = QLocale.system().uiLanguages()
        language = language_for_locale(languages[0] if languages else QLocale.system().name())
    if language not in CATALOG:
        raise ValueError(f"Unsupported language: {language}")
    _language = language


def tr(source: str, **values) -> str:
    text = CATALOG[_language].get(source, source)
    return text.format(**values) if values else text


def translate_widget(root):
    """Remember Chinese static widget sources to permit repeated live switching."""
    from PySide6.QtWidgets import QWidget, QLabel, QAbstractButton, QLineEdit, QSpinBox, QTabWidget, QTableWidget, QComboBox
    for widget in [root, *root.findChildren(QWidget)]:
        if isinstance(widget, QComboBox) and widget.property("i18n_original_resolution"):
            widget.setItemText(widget.findData(0), tr("原始分辨率"))
        attributes = [("windowTitle", "setWindowTitle")]
        if isinstance(widget, (QLabel, QAbstractButton)):
            attributes.append(("text", "setText"))
        if isinstance(widget, QLineEdit):
            attributes.append(("placeholderText", "setPlaceholderText"))
        if isinstance(widget, QSpinBox):
            attributes.append(("specialValueText", "setSpecialValueText"))
        for getter, setter in attributes:
            source = widget.property("i18n_" + getter)
            if source is None:
                source = getattr(widget, getter)()
                if source not in CATALOG["zh"]:
                    continue
                widget.setProperty("i18n_" + getter, source)
            getattr(widget, setter)(tr(source))
        if isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                key = "i18n_tab_" + str(index)
                source = widget.property(key) or widget.tabText(index)
                widget.setProperty(key, source)
                widget.setTabText(index, tr(source))
        if isinstance(widget, QTableWidget):
            for index in range(widget.columnCount()):
                item = widget.horizontalHeaderItem(index)
                if item is not None:
                    key = "i18n_header_" + str(index)
                    source = widget.property(key) or item.text()
                    widget.setProperty(key, source)
                    item.setText(tr(source))


def translate_message_buttons(dialog):
    from PySide6.QtWidgets import QMessageBox
    for button, source in ((QMessageBox.StandardButton.Yes, "是"), (QMessageBox.StandardButton.No, "否"),
                           (QMessageBox.StandardButton.Ok, "确定"), (QMessageBox.StandardButton.Cancel, "取消")):
        widget = dialog.button(button)
        if widget:
            widget.setText(tr(source))
