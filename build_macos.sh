#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This build script must run on macOS."
  exit 1
fi

python3 -m venv .build-venv
source .build-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-build.txt

python -m PyInstaller --noconfirm --clean KeyboardLanguageGuard.spec

APP_PATH="$PROJECT_DIR/dist/Keyboard Language Guard.app"
ZIP_PATH="$PROJECT_DIR/dist/Keyboard-Language-Guard-macOS.zip"
DMG_PATH="$PROJECT_DIR/dist/Keyboard-Language-Guard-macOS.dmg"
DMG_STAGE="$PROJECT_DIR/build/dmg-stage"

# Free ad-hoc signing keeps the bundle internally consistent. It is not a
# substitute for paid Developer ID signing and Apple notarization.
codesign --force --deep --sign - "$APP_PATH"

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

mkdir -p "$DMG_STAGE"
ditto "$APP_PATH" "$DMG_STAGE/Keyboard Language Guard.app"
ln -sfn /Applications "$DMG_STAGE/Applications"
hdiutil create \
  -volname "Keyboard Language Guard" \
  -srcfolder "$DMG_STAGE" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo
echo "Build completed:"
echo "  $APP_PATH"
echo "  $ZIP_PATH"
echo "  $DMG_PATH"
