"""Windows toast actions work while this tray application is running."""

import ctypes
import winreg

from windows_toasts import InteractableWindowsToaster, Toast, ToastButton
from winrt.windows.ui.notifications import NotificationSetting

AUMID = "io.easy-scrcpy.app"


class WindowsNotifications:
    def __init__(self, activate, failure):
        self.activate = activate
        self.failure = failure
        self.toasts = {}
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, rf"SOFTWARE\Classes\AppUserModelId\{AUMID}") as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Easy Scrcpy")
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(AUMID)
        self.toaster = InteractableWindowsToaster("Easy Scrcpy", notifierAUMID=AUMID)

    def show(self, token, name, actions):
        if self.toaster.toastNotifier.setting != NotificationSetting.ENABLED:
            return
        toast = Toast([name, "Easy Scrcpy"])
        toast.tag = token[:16]
        toast.group = "devices"
        for action, label in actions:
            toast.AddAction(ToastButton(label, action))
        toast.on_activated = lambda event: self.activate(token, event.arguments)
        toast.on_failed = lambda event: self.failure(f"Windows notification failed: {event}")
        self.toasts[token] = toast
        self.toaster.show_toast(toast)

    def remove(self, token):
        toast = self.toasts.pop(token, None)
        if toast:
            self.toaster.remove_toast(toast)

    def request_permission(self):
        # Windows has no toast permission prompt. Let users enable this app in
        # system notification settings instead of overriding their preference.
        import os
        os.startfile("ms-settings:notifications")

    def close(self):
        pass
