# Keyboard Language Guard — macOS MVP v4

The app detects Hebrew/English text typed with the wrong keyboard layout and offers **Replace**, **Copy**, or **Ignore**. All analysis happens locally; typed text is not sent to a server.

## What changed in v3

- A macOS menu-bar icon (`⌨︎`) with **Pause/Resume** and **Quit**.
- A repeatable Mac build that creates a standalone `.app`, `.zip`, and `.dmg`.
- The finished app contains Python and its dependencies, so users do not need Terminal or Python.
- Free ad-hoc signing for private testing before purchasing an Apple Developer membership.

## What changed in v4

- The suggestion is anchored next to the active text caret when the editor exposes its location through macOS Accessibility.
- If the caret location is unavailable, the suggestion appears next to the mouse pointer instead of a fixed corner.
- The suggestion is now a compact blue card with a highlighted correction and clearer actions.

## What changed in v2

- Detection waits until typing pauses instead of interrupting after every space.
- A sentence-ending character uses a shorter pause, but continuing to type cancels that check.
- On macOS the suggestion returns focus to the app in which you were typing.
- You may continue typing after the suggestion appears. **Replace** changes only the detected gibberish and keeps the later text intact.
- **Copy** puts the corrected sentence on the clipboard without changing the text already typed.
- The clipboard is restored after replacement, and `Cmd+Z` can undo the edit in the target application.

Default timing:

- Normal typing pause: 1.4 seconds
- After `.`, `?`, `!`, `;` or `:`: 0.85 seconds
- After Enter/Tab: 0.35 seconds

These values can be changed near the top of `app.py`.

## Install and run

Requires Python 3.10+.

```bash
cd keyboard_language_guard_v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Build a standalone Mac app

Run this on a Mac:

```bash
chmod +x build_macos.sh
./build_macos.sh
```

The first build downloads its dependencies and may take several minutes. It creates these files in `dist/`:

```text
Keyboard Language Guard.app
Keyboard-Language-Guard-macOS.zip
Keyboard-Language-Guard-macOS.dmg
```

Open the `.dmg`, drag the app to **Applications**, and launch it. The keyboard icon in the menu bar confirms that it is running.

This free test build is ad-hoc signed rather than signed with a paid Apple Developer ID. On another Mac, right-click the app and choose **Open**. If macOS still blocks it, use **System Settings → Privacy & Security → Open Anyway**.

If you already installed the previous version, you can copy these files over it and run:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## macOS permissions

Enable the Terminal/Python process under:

- **System Settings → Privacy & Security → Accessibility**
- **System Settings → Privacy & Security → Input Monitoring**

Restart Terminal after changing permissions.

When running the standalone app, grant the permissions to **Keyboard Language Guard** itself rather than Terminal, then quit and reopen the app.

## Test

Open Notes, switch the keyboard to English, and type the physical keys for a Hebrew sentence. Stop typing for about 1.4 seconds. The suggestion should appear without taking typing focus.

Click **Replace** to replace the detected phrase in Notes. If you typed more text after the suggestion appeared, that later text should remain in place.

Click **Copy** to keep the original text untouched and place the corrected sentence on the clipboard.

Run the core tests with:

```bash
python test_core.py
```

## Current limitations

- Standard US-QWERTY ↔ Hebrew layouts only.
- Replacement depends on the target app supporting normal keyboard selection and paste events.
- Clicking the suggestion necessarily activates it momentarily; the app then returns focus to the original editor before replacing.
- Mouse clicks that move the caret to a different location are not tracked yet. Ignore the suggestion if you moved the caret after it appeared.
- The build normally targets the architecture of the Mac/Python used to create it. Early testers should use the same Mac architecture; later releases can provide Intel and Apple Silicon builds separately.
- Before broad public distribution, password-field exclusion and a clearer first-run privacy screen should be added and tested.

## Upload for testers

Create a GitHub repository, open **Releases → Draft a new release**, and upload the `.dmg` and/or `.zip` from `dist/`. Testers should download these release assets rather than GitHub's automatic source-code archives.
