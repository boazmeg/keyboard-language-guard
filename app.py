import os
import platform
import threading
import time
import tkinter as tk
from tkinter import ttk

import pyperclip
from pynput import keyboard, mouse

from detector import detect_wrong_layout

try:
    import objc
    from Foundation import NSObject
    from AppKit import (
        NSMenu,
        NSMenuItem,
        NSStatusBar,
        NSVariableStatusItemLength,
    )
except ImportError:
    objc = None
    NSObject = object

MAX_BUFFER = 220
MIN_CHECK_CHARS = 8
COOLDOWN_SECONDS = 4
IDLE_CHECK_MS = 1400
PUNCTUATION_CHECK_MS = 850
ENTER_CHECK_MS = 350
POPUP_WIDTH = 500
POPUP_HEIGHT = 205


if objc:
    class MacMenuDelegate(NSObject):
        def initWithGuard_(self, guard):
            self = objc.super(MacMenuDelegate, self).init()
            if self is not None:
                self.guard = guard
            return self

        @objc.IBAction
        def toggle_(self, sender):
            self.guard.toggle_enabled()

        @objc.IBAction
        def quit_(self, sender):
            self.guard.root.after(0, self.guard.quit)


class LanguageGuard:
    def __init__(self):
        self.buffer = ''
        self.lock = threading.RLock()
        self.last_alert_at = 0.0
        self.alert_open = False
        self.suppress_input = False
        self.enabled = True
        self.pending_check_id = 0
        self.controller = keyboard.Controller()
        self.mouse_controller = mouse.Controller()
        self.is_mac = platform.system() == 'Darwin'
        self.previous_app = None

        self.root = tk.Tk()
        self.root.withdraw()
        self._configure_as_background_app()
        self._setup_menu_bar()
        self.listener = keyboard.Listener(on_press=self.on_press)

    def _setup_menu_bar(self):
        """Add a small macOS menu-bar controller for Pause and Quit."""
        self.status_item = None
        self.menu_delegate = None
        self.toggle_menu_item = None
        if not self.is_mac or not objc:
            return
        try:
            self.menu_delegate = MacMenuDelegate.alloc().initWithGuard_(self)
            self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
                NSVariableStatusItemLength
            )
            self.status_item.button().setTitle_('⌨︎')
            self.status_item.button().setToolTip_('Keyboard Language Guard')

            menu = NSMenu.alloc().init()
            self.toggle_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                'השהה זיהוי', 'toggle:', ''
            )
            self.toggle_menu_item.setTarget_(self.menu_delegate)
            menu.addItem_(self.toggle_menu_item)
            menu.addItem_(NSMenuItem.separatorItem())

            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                'סגור את Keyboard Language Guard', 'quit:', 'q'
            )
            quit_item.setTarget_(self.menu_delegate)
            menu.addItem_(quit_item)
            self.status_item.setMenu_(menu)
        except Exception as exc:
            print(f'Could not create menu-bar icon: {exc}')

    def toggle_enabled(self):
        with self.lock:
            self.enabled = not self.enabled
            self.buffer = ''
            self.pending_check_id += 1
            enabled = self.enabled
        if self.toggle_menu_item is not None:
            self.toggle_menu_item.setTitle_('השהה זיהוי' if enabled else 'הפעל זיהוי')
        if self.status_item is not None:
            self.status_item.button().setTitle_('⌨︎' if enabled else '⌨︎⏸')

    def quit(self):
        try:
            self.listener.stop()
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()

    def _configure_as_background_app(self):
        """On macOS, keep Python/Tk out of the normal app-switching flow."""
        if not self.is_mac:
            return
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApplication.sharedApplication().setActivationPolicy_(
                NSApplicationActivationPolicyAccessory
            )
        except Exception:
            # The guard still works without AppKit; focus restoration below is a fallback.
            pass

    def _frontmost_app(self):
        if not self.is_mac:
            return None
        try:
            from AppKit import NSWorkspace
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            # Do not remember our own Python process as the typing application.
            if app and app.processIdentifier() != os.getpid():
                return app
        except Exception:
            return None
        return None

    @staticmethod
    def _activate_app(app):
        if app is None:
            return
        try:
            from AppKit import NSApplicationActivateIgnoringOtherApps
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        except Exception:
            pass

    def _caret_screen_position(self):
        """Return the focused text caret in global screen coordinates on macOS.

        Not every editor exposes AXBoundsForRange. In that case, fall back to
        the mouse pointer, which is still better than a fixed screen corner.
        """
        if self.is_mac:
            try:
                from ApplicationServices import (
                    AXUIElementCreateSystemWide,
                    AXUIElementCopyAttributeValue,
                    AXUIElementCopyParameterizedAttributeValue,
                    kAXBoundsForRangeParameterizedAttribute,
                    kAXFocusedUIElementAttribute,
                    kAXSelectedTextRangeAttribute,
                )
                from Quartz import AXValueGetValue, kAXValueCGRectType

                system = AXUIElementCreateSystemWide()
                err, focused = AXUIElementCopyAttributeValue(
                    system, kAXFocusedUIElementAttribute, None
                )
                if err == 0 and focused is not None:
                    err, selected_range = AXUIElementCopyAttributeValue(
                        focused, kAXSelectedTextRangeAttribute, None
                    )
                    if err == 0 and selected_range is not None:
                        err, bounds_value = AXUIElementCopyParameterizedAttributeValue(
                            focused,
                            kAXBoundsForRangeParameterizedAttribute,
                            selected_range,
                            None,
                        )
                        if err == 0 and bounds_value is not None:
                            success, rect = AXValueGetValue(
                                bounds_value, kAXValueCGRectType, None
                            )
                            if success:
                                return int(rect.origin.x), int(
                                    rect.origin.y + rect.size.height
                                )
            except Exception:
                pass

        try:
            x, y = self.mouse_controller.position
            return int(x), int(y)
        except Exception:
            return 80, 80

    def _popup_geometry(self, anchor_x, anchor_y):
        """Place the card below the caret, or above it near screen edges."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = anchor_x + 14
        y = anchor_y + 18
        if x + POPUP_WIDTH > screen_w - 16:
            x = screen_w - POPUP_WIDTH - 16
        if y + POPUP_HEIGHT > screen_h - 24:
            y = anchor_y - POPUP_HEIGHT - 18
        return max(12, x), max(12, y)

    def _keep_popup_above(self, win):
        """Keep the suggestion visible above the active editor on macOS."""
        try:
            win.lift()
            win.attributes('-topmost', True)
        except tk.TclError:
            return

        if not self.is_mac:
            return
        try:
            from AppKit import (
                NSApplication,
                NSPopUpMenuWindowLevel,
                NSWindowCollectionBehaviorCanJoinAllSpaces,
                NSWindowCollectionBehaviorFullScreenAuxiliary,
            )

            for native_window in NSApplication.sharedApplication().windows():
                if native_window.title() == 'Keyboard Language Guard Suggestion':
                    native_window.setLevel_(NSPopUpMenuWindowLevel)
                    native_window.setHidesOnDeactivate_(False)
                    native_window.setCollectionBehavior_(
                        NSWindowCollectionBehaviorCanJoinAllSpaces
                        | NSWindowCollectionBehaviorFullScreenAuxiliary
                    )
                    break
        except Exception:
            # Tk's topmost behavior remains as the cross-platform fallback.
            pass

    def run(self):
        self.listener.start()
        print('Keyboard Language Guard is running. Press Ctrl+C in this terminal to quit.')
        self.root.mainloop()

    def schedule_check(self, delay_ms=IDLE_CHECK_MS):
        """Debounce checks: only the latest pause in typing may trigger detection."""
        with self.lock:
            self.pending_check_id += 1
            check_id = self.pending_check_id

        def wait_then_check():
            time.sleep(delay_ms / 1000)
            with self.lock:
                if check_id != self.pending_check_id:
                    return
            self.maybe_check()

        threading.Thread(target=wait_then_check, daemon=True).start()

    def on_press(self, key):
        with self.lock:
            if self.suppress_input or not self.enabled:
                return
            if key == keyboard.Key.backspace:
                self.buffer = self.buffer[:-1]
                self.schedule_check()
                return
            if key in (keyboard.Key.enter, keyboard.Key.tab):
                self.buffer += '\n' if key == keyboard.Key.enter else '\t'
                self.schedule_check(ENTER_CHECK_MS)
                return
            if key == keyboard.Key.space:
                self.buffer += ' '
                self.schedule_check()
                return
            if key in (keyboard.Key.esc, keyboard.Key.delete):
                self.buffer = ''
                self.pending_check_id += 1
                return

            try:
                ch = key.char
            except AttributeError:
                ch = None
            if not ch or ord(ch) < 32:
                return

            self.buffer += ch
            self.buffer = self.buffer[-MAX_BUFFER:]
            delay = PUNCTUATION_CHECK_MS if ch in '.?!;:' else IDLE_CHECK_MS
            self.schedule_check(delay)

    def candidate_segment(self, text):
        # Work on the current paragraph. Leading/trailing whitespace is excluded
        # from the replacement so surrounding formatting remains untouched.
        cut = max(text.rfind('\n'), text.rfind('\t'))
        segment = text[cut + 1:][-180:]
        return segment.strip()

    def maybe_check(self):
        with self.lock:
            if self.alert_open or time.time() - self.last_alert_at < COOLDOWN_SECONDS:
                return
            snapshot = self.buffer
            segment = self.candidate_segment(snapshot)

        if len(segment) < MIN_CHECK_CHARS:
            return
        detection = detect_wrong_layout(segment)
        if not detection:
            return

        with self.lock:
            # Typing may have resumed while detection was running. In that case,
            # the newer scheduled check will handle the longer text.
            if snapshot != self.buffer:
                return
            self.last_alert_at = time.time()
            self.alert_open = True
            self.previous_app = self._frontmost_app()

        self.root.after(0, lambda d=detection: self.show_alert(d))

    def show_alert(self, detection):
        anchor_x, anchor_y = self._caret_screen_position()
        popup_x, popup_y = self._popup_geometry(anchor_x, anchor_y)

        win = tk.Toplevel(self.root, takefocus=False)
        win.title('Keyboard Language Guard Suggestion')
        win.attributes('-topmost', True)
        win.resizable(False, False)
        win.overrideredirect(True)
        win.geometry(f'{POPUP_WIDTH}x{POPUP_HEIGHT}+{popup_x}+{popup_y}')
        win.configure(bg='#D9E5FF')

        # A tool-style window is less likely to activate the Python process.
        try:
            win.attributes('-toolwindow', True)
        except tk.TclError:
            pass

        target = 'עברית' if detection.target_lang == 'he' else 'English'
        card = tk.Frame(
            win,
            bg='#F7F9FF',
            highlightbackground='#9BB7FF',
            highlightthickness=1,
            padx=18,
            pady=15,
        )
        card.pack(fill='both', expand=True, padx=2, pady=2)

        header = tk.Frame(card, bg='#F7F9FF')
        header.pack(fill='x')
        tk.Label(
            header,
            text='Aa  עב',
            bg='#4F6BED',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=8,
            pady=3,
        ).pack(side='left')
        tk.Label(
            header,
            text=f'נראה שהמקלדת הייתה בשפה הלא נכונה · {target}',
            bg='#F7F9FF',
            fg='#25304A',
            font=('Arial', 13, 'bold'),
        ).pack(side='right')

        preview = tk.Text(
            card,
            height=3,
            wrap='word',
            takefocus=False,
            relief='flat',
            borderwidth=0,
            bg='#EAF0FF',
            fg='#17213A',
            font=('Arial', 14),
            padx=10,
            pady=8,
        )
        preview.insert('1.0', detection.converted)
        preview.configure(state='disabled')
        preview.pack(fill='x', pady=(12, 12))

        buttons = tk.Frame(card, bg='#F7F9FF')
        buttons.pack(fill='x')

        def ignore():
            with self.lock:
                self.alert_open = False
            win.destroy()
            self._activate_app(self.previous_app)

        def replace():
            win.destroy()
            self._activate_app(self.previous_app)
            # Give macOS enough time to return focus before sending key events.
            self.root.after(
                220,
                lambda: self.replace_visible_text(detection.original, detection.converted)
            )

        def copy_only():
            # Copy is intentional here, so unlike Replace we leave the corrected
            # text on the clipboard for the user to paste wherever they want.
            pyperclip.copy(detection.converted)
            with self.lock:
                self.alert_open = False
            win.destroy()
            self._activate_app(self.previous_app)

        tk.Button(
            buttons,
            text='החלף',
            command=replace,
            bg='#4F6BED',
            fg='white',
            activebackground='#3F58C7',
            activeforeground='white',
            relief='flat',
            borderwidth=0,
            padx=18,
            pady=6,
            font=('Arial', 12, 'bold'),
            cursor='hand2',
        ).pack(side='right', padx=(8, 0))
        tk.Button(
            buttons,
            text='העתק',
            command=copy_only,
            bg='#DDE6FF',
            fg='#304BA8',
            activebackground='#C9D7FF',
            relief='flat',
            borderwidth=0,
            padx=16,
            pady=6,
            font=('Arial', 12, 'bold'),
            cursor='hand2',
        ).pack(side='right')
        tk.Button(
            buttons,
            text='לא עכשיו',
            command=ignore,
            bg='#F7F9FF',
            fg='#65708A',
            activebackground='#EDF1FA',
            relief='flat',
            borderwidth=0,
            padx=12,
            pady=6,
            font=('Arial', 11),
            cursor='hand2',
        ).pack(side='left')
        win.protocol('WM_DELETE_WINDOW', ignore)

        win.update_idletasks()
        self._keep_popup_above(win)
        # Tk may briefly activate itself while mapping the window. Immediately
        # restore the typing application so the next keystroke still goes there.
        self.root.after(20, lambda: self._activate_app(self.previous_app))
        self.root.after(60, lambda: self._keep_popup_above(win))
        self.root.after(250, lambda: self._keep_popup_above(win))

    def replace_visible_text(self, original, converted):
        with self.lock:
            current = self.buffer
            self.suppress_input = True

        # Locate the detected phrase in the current buffer. Any text typed after
        # the alert becomes `trailing` and is skipped over before selecting.
        start = current.rfind(original)
        if start < 0:
            with self.lock:
                self.alert_open = False
                self.suppress_input = False
            return
        end = start + len(original)
        trailing = current[end:]

        old_clipboard = None
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            pass

        try:
            pyperclip.copy(converted)
            time.sleep(0.05)

            for _ in range(len(trailing)):
                self.controller.press(keyboard.Key.left)
                self.controller.release(keyboard.Key.left)

            with self.controller.pressed(keyboard.Key.shift):
                for _ in range(len(original)):
                    self.controller.press(keyboard.Key.left)
                    self.controller.release(keyboard.Key.left)

            modifier = keyboard.Key.cmd if self.is_mac else keyboard.Key.ctrl
            with self.controller.pressed(modifier):
                self.controller.press('v')
                self.controller.release('v')

            # Return the caret to where the user had continued typing.
            for _ in range(len(trailing)):
                self.controller.press(keyboard.Key.right)
                self.controller.release(keyboard.Key.right)
            time.sleep(0.12)
        finally:
            if old_clipboard is not None:
                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass

        with self.lock:
            self.buffer = current[:start] + converted + trailing
            self.alert_open = False
            self.suppress_input = False


if __name__ == '__main__':
    LanguageGuard().run()
