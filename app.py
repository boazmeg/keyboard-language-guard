import os
import platform
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import pyperclip
from pynput import keyboard, mouse

from config import SENSITIVITY_PRESETS, Settings
from detector import detect_wrong_layout
from mac_accessibility import is_secure_field_focused

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
        def settings_(self, sender):
            self.guard.root.after(0, self.guard.show_settings)

        @objc.IBAction
        def quit_(self, sender):
            self.guard.root.after(0, self.guard.quit)


class LanguageGuard:
    def __init__(self):
        self.settings = Settings.load()
        self.buffer = ''
        self.lock = threading.RLock()
        self.last_alert_at = 0.0
        self.alert_open = False
        self.suppress_input = False
        self.enabled = self.settings.enabled
        self.pending_check_id = 0
        self.settings_window = None
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

            settings_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                'הגדרות…', 'settings:', ','
            )
            settings_item.setTarget_(self.menu_delegate)
            menu.addItem_(settings_item)
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
        self.settings.enabled = enabled
        self._save_settings_safely()
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

    def _save_settings_safely(self):
        try:
            self.settings.save()
        except Exception as exc:
            print(f'Could not save settings: {exc}')

    def _bring_window_to_front(self, win):
        win.lift()
        win.attributes('-topmost', True)
        if self.is_mac:
            try:
                from AppKit import (
                    NSApplication,
                    NSApplicationActivateIgnoringOtherApps,
                )
                NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            except Exception:
                pass

    def show_settings(self):
        if self.settings_window is not None and tk.Toplevel.winfo_exists(
            self.settings_window
        ):
            self._bring_window_to_front(self.settings_window)
            return

        win = tk.Toplevel(self.root)
        self.settings_window = win
        win.title('הגדרות · Keyboard Language Guard')
        win.configure(bg='#F7F9FF')
        win.resizable(False, False)

        enabled_var = tk.BooleanVar(value=self.enabled)
        secure_var = tk.BooleanVar(value=self.settings.ignore_secure_fields)
        sensitivity_var = tk.StringVar(value=self.settings.sensitivity_label())
        idle_var = tk.IntVar(value=self.settings.idle_check_ms)

        pad = {'padx': 18, 'pady': 6}

        tk.Label(
            win,
            text='הגדרות',
            bg='#F7F9FF',
            fg='#25304A',
            font=('Arial', 16, 'bold'),
        ).grid(row=0, column=0, sticky='e', **pad)

        tk.Checkbutton(
            win,
            text='זיהוי פעיל',
            variable=enabled_var,
            bg='#F7F9FF',
            font=('Arial', 12),
            anchor='e',
        ).grid(row=1, column=0, sticky='ew', **pad)

        tk.Checkbutton(
            win,
            text='התעלם משדות סיסמה (מומלץ)',
            variable=secure_var,
            bg='#F7F9FF',
            font=('Arial', 12),
            anchor='e',
        ).grid(row=2, column=0, sticky='ew', **pad)

        sensitivity_frame = tk.LabelFrame(
            win,
            text='רגישות זיהוי',
            bg='#F7F9FF',
            fg='#25304A',
            font=('Arial', 12, 'bold'),
        )
        sensitivity_frame.grid(row=3, column=0, sticky='ew', **pad)
        labels = {
            'high': 'גבוהה (יותר התרעות)',
            'balanced': 'מאוזנת',
            'strict': 'קפדנית (פחות התרעות)',
        }
        for name in ('high', 'balanced', 'strict'):
            tk.Radiobutton(
                sensitivity_frame,
                text=labels[name],
                value=name,
                variable=sensitivity_var,
                bg='#F7F9FF',
                font=('Arial', 11),
                anchor='e',
            ).pack(fill='x', padx=10, pady=2)

        tk.Label(
            win,
            text='השהיית זיהוי (מילישניות)',
            bg='#F7F9FF',
            fg='#25304A',
            font=('Arial', 12),
        ).grid(row=4, column=0, sticky='e', **pad)
        tk.Scale(
            win,
            from_=600,
            to=2500,
            resolution=50,
            orient='horizontal',
            variable=idle_var,
            bg='#F7F9FF',
            highlightthickness=0,
            length=260,
        ).grid(row=5, column=0, sticky='ew', **pad)

        buttons = tk.Frame(win, bg='#F7F9FF')
        buttons.grid(row=6, column=0, sticky='ew', **pad)

        def save_and_close():
            self.settings.enabled = enabled_var.get()
            self.settings.ignore_secure_fields = secure_var.get()
            self.settings.set_sensitivity(sensitivity_var.get())
            self.settings.idle_check_ms = int(idle_var.get())
            self._save_settings_safely()

            with self.lock:
                self.enabled = self.settings.enabled
                self.buffer = ''
                self.pending_check_id += 1
            if self.toggle_menu_item is not None:
                self.toggle_menu_item.setTitle_(
                    'השהה זיהוי' if self.enabled else 'הפעל זיהוי'
                )
            if self.status_item is not None:
                self.status_item.button().setTitle_('⌨︎' if self.enabled else '⌨︎⏸')
            win.destroy()
            self.settings_window = None

        def cancel():
            win.destroy()
            self.settings_window = None

        tk.Button(
            buttons,
            text='שמור',
            command=save_and_close,
            bg='#4F6BED',
            fg='white',
            activebackground='#3F58C7',
            activeforeground='white',
            relief='flat',
            padx=18,
            pady=6,
            font=('Arial', 12, 'bold'),
            cursor='hand2',
        ).pack(side='right', padx=(8, 0))
        tk.Button(
            buttons,
            text='ביטול',
            command=cancel,
            bg='#DDE6FF',
            fg='#304BA8',
            relief='flat',
            padx=16,
            pady=6,
            font=('Arial', 12),
            cursor='hand2',
        ).pack(side='right')

        win.protocol('WM_DELETE_WINDOW', cancel)
        win.update_idletasks()
        self._bring_window_to_front(win)

    def show_first_run(self):
        win = tk.Toplevel(self.root)
        win.title('ברוכים הבאים · Keyboard Language Guard')
        win.configure(bg='#F7F9FF')
        win.resizable(False, False)

        card = tk.Frame(win, bg='#F7F9FF', padx=24, pady=20)
        card.pack(fill='both', expand=True)

        tk.Label(
            card,
            text='ברוכים הבאים ל‑Keyboard Language Guard',
            bg='#F7F9FF',
            fg='#25304A',
            font=('Arial', 16, 'bold'),
        ).pack(anchor='e', pady=(0, 12))

        message = (
            'האפליקציה מזהה טקסט שהוקלד בפריסת המקלדת הלא נכונה '
            '(עברית/אנגלית) ומציעה לתקן.\n\n'
            'פרטיות: כל הניתוח מתבצע במחשב שלך בלבד. שום טקסט לא נשלח לשרת. '
            'הקלדה בשדות סיסמה מתעלמים ממנה לחלוטין.\n\n'
            'כדי לפעול, האפליקציה זקוקה להרשאות ב‑\n'
            'System Settings → Privacy & Security:\n'
            '  •  Accessibility (נגישות)\n'
            '  •  Input Monitoring (ניטור קלט)\n\n'
            'לאחר אישור ההרשאות, סגור והפעל מחדש את האפליקציה.'
        )
        tk.Label(
            card,
            text=message,
            bg='#F7F9FF',
            fg='#25304A',
            font=('Arial', 12),
            justify='right',
            wraplength=440,
        ).pack(anchor='e')

        def acknowledge():
            self.settings.first_run_completed = True
            self._save_settings_safely()
            win.destroy()

        tk.Button(
            card,
            text='הבנתי, בוא נתחיל',
            command=acknowledge,
            bg='#4F6BED',
            fg='white',
            activebackground='#3F58C7',
            activeforeground='white',
            relief='flat',
            padx=20,
            pady=8,
            font=('Arial', 12, 'bold'),
            cursor='hand2',
        ).pack(anchor='e', pady=(18, 0))

        win.protocol('WM_DELETE_WINDOW', acknowledge)
        win.update_idletasks()
        self._bring_window_to_front(win)

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

    def _popup_geometry(self, anchor_x, anchor_y, popup_height=POPUP_HEIGHT):
        """Place the card below the caret, or above it near screen edges."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = anchor_x + 14
        y = anchor_y + 18
        if x + POPUP_WIDTH > screen_w - 16:
            x = screen_w - POPUP_WIDTH - 16
        if y + popup_height > screen_h - 24:
            y = anchor_y - popup_height - 18
        return max(12, x), max(12, y)

    @staticmethod
    def _wrap_to_width(text, font, max_width):
        """Greedy word-wrap keeping each line within max_width pixels.

        We wrap manually and render each resulting line as its own
        single-line label, because Tk mis-orders right-to-left text when it
        performs its own line wrapping.
        """
        words = text.split()
        if not words:
            return [text]
        lines = []
        current = ''
        for word in words:
            candidate = word if not current else f'{current} {word}'
            if not current or font.measure(candidate) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

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
        if not self.settings.first_run_completed:
            self.root.after(300, self.show_first_run)
        self.root.mainloop()

    def schedule_check(self, delay_ms=None):
        """Debounce checks: only the latest pause in typing may trigger detection."""
        if delay_ms is None:
            delay_ms = self.settings.idle_check_ms
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
        # Never capture keystrokes typed into a password field. Checked outside
        # the lock so the Accessibility query does not block other callbacks.
        if self.enabled and self.settings.ignore_secure_fields and self.is_mac:
            if is_secure_field_focused():
                with self.lock:
                    self.buffer = ''
                    self.pending_check_id += 1
                return

        with self.lock:
            if self.suppress_input or not self.enabled:
                return
            if key == keyboard.Key.backspace:
                self.buffer = self.buffer[:-1]
                self.schedule_check()
                return
            if key in (keyboard.Key.enter, keyboard.Key.tab):
                self.buffer += '\n' if key == keyboard.Key.enter else '\t'
                self.schedule_check(self.settings.enter_check_ms)
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
            delay = (
                self.settings.punctuation_check_ms
                if ch in '.?!;:'
                else self.settings.idle_check_ms
            )
            self.schedule_check(delay)

    def candidate_segment(self, text):
        # Work on the current paragraph. Leading/trailing whitespace is excluded
        # from the replacement so surrounding formatting remains untouched.
        cut = max(text.rfind('\n'), text.rfind('\t'))
        segment = text[cut + 1:][-180:]
        return segment.strip()

    def maybe_check(self):
        with self.lock:
            if self.alert_open or time.time() - self.last_alert_at < self.settings.cooldown_seconds:
                return
            snapshot = self.buffer
            segment = self.candidate_segment(snapshot)

        if len(segment) < self.settings.min_check_chars:
            return
        detection = detect_wrong_layout(
            segment,
            min_chars=self.settings.min_check_chars,
            threshold=self.settings.detection_threshold,
        )
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
        win = tk.Toplevel(self.root, takefocus=False)
        win.title('Keyboard Language Guard Suggestion')
        win.attributes('-topmost', True)
        win.resizable(False, False)
        win.overrideredirect(True)
        # Width is fixed; the final height is set once the content (which may
        # wrap onto several lines) has been laid out, further below.
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

        # Show the correction as non-interactive labels — one per line — so it
        # can never be clicked/edited. We wrap the text ourselves and render
        # each line separately, because Tk mis-orders right-to-left text when
        # it wraps internally, which scrambled the Hebrew letters.
        preview_font = tkfont.Font(family='Arial', size=14)
        preview_lines = self._wrap_to_width(
            detection.converted, preview_font, POPUP_WIDTH - 90
        )
        preview_box = tk.Frame(card, bg='#EAF0FF')
        preview_box.pack(fill='x', pady=(12, 12))
        for line in preview_lines:
            tk.Label(
                preview_box,
                text=line,
                takefocus=0,
                relief='flat',
                borderwidth=0,
                bg='#EAF0FF',
                fg='#17213A',
                font=preview_font,
                anchor='e',
                padx=10,
            ).pack(side='top', fill='x', padx=6, pady=(4, 4))

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

        # Size the window to its content (height grows with wrapped lines),
        # then place it near the caret without overflowing the screen edges.
        win.update_idletasks()
        height = max(POPUP_HEIGHT, win.winfo_reqheight())
        anchor_x, anchor_y = self._caret_screen_position()
        popup_x, popup_y = self._popup_geometry(anchor_x, anchor_y, height)
        win.geometry(f'{POPUP_WIDTH}x{height}+{popup_x}+{popup_y}')

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
