"""UserNotifications requires a bundled macOS application identity."""

import sys
import threading
import objc

from Foundation import NSBundle, NSObject
import UserNotifications as UN


class NotificationDelegate(NSObject, protocols=[objc.protocolNamed("UNUserNotificationCenterDelegate")]):
    def userNotificationCenter_didReceiveNotificationResponse_withCompletionHandler_(self, center, response, completion):
        try:
            token = str(response.notification().request().identifier())
            action = str(response.actionIdentifier())
            if action in {"restart", "stop", "settings"}:
                self.activation(token, action)
        finally:
            completion()

    def userNotificationCenter_willPresentNotification_withCompletionHandler_(self, center, notification, completion):
        completion(UN.UNNotificationPresentationOptionBanner | UN.UNNotificationPresentationOptionList)


class MacNotifications:
    def __init__(self, activate, failure):
        if not getattr(sys, "frozen", False) or NSBundle.mainBundle().bundleIdentifier() != "io.easy-scrcpy.app":
            raise RuntimeError("macOS device notifications require the packaged EasyScrcpy.app")
        self.failure = failure
        self.center = UN.UNUserNotificationCenter.currentNotificationCenter()
        self.delegate = NotificationDelegate.alloc().init()
        self.delegate.activation = activate
        self.center.setDelegate_(self.delegate)
        self.tokens = set()
        self.categories = {}
        self.requests = {}
        self.lock = threading.RLock()
        self.closed = False

    def show(self, token, name, actions):
        with self.lock:
            self.tokens.add(token)
            self.requests[token] = (name, actions)
        def checked(settings):
            if settings.authorizationStatus() not in (UN.UNAuthorizationStatusAuthorized, UN.UNAuthorizationStatusProvisional):
                return
            with self.lock:
                if self.closed or token not in self.tokens:
                    return
                # Unique categories preserve the language of each request and do
                # not invalidate other devices' actions.
                category_id = "device-" + token
                native_actions = [UN.UNNotificationAction.actionWithIdentifier_title_options_(action, label, 0)
                                  for action, label in actions]
                category = UN.UNNotificationCategory.categoryWithIdentifier_actions_intentIdentifiers_options_(
                    category_id, native_actions, [], 0)
                self.categories[token] = category
                self.center.setNotificationCategories_(set(self.categories.values()))
                content = UN.UNMutableNotificationContent.alloc().init()
                content.setTitle_(name)
                content.setBody_("Easy Scrcpy")
                content.setCategoryIdentifier_(category_id)
                request = UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(token, content, None)
                self.center.addNotificationRequest_withCompletionHandler_(
                    request, lambda error: self.failure(f"macOS notification failed: {error}") if error else None)
        self.center.getNotificationSettingsWithCompletionHandler_(checked)

    def remove(self, token):
        with self.lock:
            self.tokens.discard(token)
            self.requests.pop(token, None)
            if self.categories:
                self.categories.pop(token, None)
            self.center.removePendingNotificationRequestsWithIdentifiers_([token])
            self.center.removeDeliveredNotificationsWithIdentifiers_([token])

    def request_permission(self):
        def completed(granted, error):
            if error:
                self.failure(f"macOS notification permission: {error}")
            if granted:
                with self.lock:
                    for token, (name, actions) in list(self.requests.items()):
                        if not self.closed:
                            self.show(token, name, actions)
        self.center.requestAuthorizationWithOptions_completionHandler_(
            UN.UNAuthorizationOptionAlert, completed)

    def close(self):
        with self.lock:
            self.closed = True
        self.center.setDelegate_(None)
