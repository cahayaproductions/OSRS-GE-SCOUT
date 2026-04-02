#!/bin/bash
# ═══════════════════════════════════════════════════════
#  OSRS GE Scout — App Builder (PyInstaller)
#  Dubbelklik om een standalone .app + .pkg te bouwen.
#  De .pkg kun je delen — werkt op elke Mac zonder Python.
# ═══════════════════════════════════════════════════════

set -e
cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   OSRS GE Scout — App Builder            ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

APP_NAME="OSRS GE Scout"
PKG_PATH="${SCRIPT_DIR}/${APP_NAME}.pkg"

# ── Check benodigde bestanden ──
if [ ! -f "$SCRIPT_DIR/osrs_webapp.py" ]; then
    echo "❌ osrs_webapp.py niet gevonden."
    read -p "Druk Enter om te sluiten..."
    exit 1
fi
if [ ! -f "$SCRIPT_DIR/osrs_app.py" ]; then
    echo "❌ osrs_app.py niet gevonden."
    read -p "Druk Enter om te sluiten..."
    exit 1
fi

# ── Homebrew PATH ──
if [ -f "/opt/homebrew/bin/brew" ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -f "/usr/local/bin/brew" ]; then
    eval "$(/usr/local/bin/brew shellenv)"
fi

# ── Check/install Python ──
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 niet gevonden. Installeer via: brew install python3"
    read -p "Druk Enter om te sluiten..."
    exit 1
fi

# ── Check/install PyInstaller + dependencies ──
echo "⏳ Dependencies checken..."
python3 -c "import PyInstaller" 2>/dev/null || {
    echo "⏳ PyInstaller installeren..."
    pip3 install pyinstaller --break-system-packages 2>/dev/null || pip3 install pyinstaller
}
python3 -c "import flask" 2>/dev/null || {
    echo "⏳ Flask installeren..."
    pip3 install flask --break-system-packages 2>/dev/null || pip3 install flask
}
python3 -c "import requests" 2>/dev/null || {
    echo "⏳ Requests installeren..."
    pip3 install requests --break-system-packages 2>/dev/null || pip3 install requests
}
python3 -c "import webview" 2>/dev/null || {
    echo "⏳ PyWebView installeren..."
    pip3 install pywebview --break-system-packages 2>/dev/null || pip3 install pywebview
}
echo "✅ Dependencies OK"

# ── App icoon bouwen ──
ICON_PNG="$SCRIPT_DIR/osrs_icon.png"
ICNS_FILE=""
if [ -f "$ICON_PNG" ]; then
    echo "⏳ App-icoon bouwen..."
    ICONSET_DIR="/tmp/AppIcon.iconset"
    rm -rf "$ICONSET_DIR"
    mkdir -p "$ICONSET_DIR"
    sips -z 16 16     "$ICON_PNG" --out "$ICONSET_DIR/icon_16x16.png"      > /dev/null 2>&1
    sips -z 32 32     "$ICON_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png"   > /dev/null 2>&1
    sips -z 32 32     "$ICON_PNG" --out "$ICONSET_DIR/icon_32x32.png"      > /dev/null 2>&1
    sips -z 64 64     "$ICON_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png"   > /dev/null 2>&1
    sips -z 128 128   "$ICON_PNG" --out "$ICONSET_DIR/icon_128x128.png"    > /dev/null 2>&1
    sips -z 256 256   "$ICON_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png" > /dev/null 2>&1
    sips -z 256 256   "$ICON_PNG" --out "$ICONSET_DIR/icon_256x256.png"    > /dev/null 2>&1
    sips -z 512 512   "$ICON_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png" > /dev/null 2>&1
    sips -z 512 512   "$ICON_PNG" --out "$ICONSET_DIR/icon_512x512.png"    > /dev/null 2>&1
    cp "$ICON_PNG"                       "$ICONSET_DIR/icon_512x512@2x.png"
    ICNS_FILE="/tmp/AppIcon.icns"
    iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE" 2>/dev/null && echo "✅ Icoon gebouwd" || {
        echo "⚠️  Icoon kon niet worden gebouwd"
        ICNS_FILE=""
    }
    rm -rf "$ICONSET_DIR"
fi

# ── PyInstaller build ──
echo "⏳ App bouwen met PyInstaller... (dit duurt 1-3 minuten)"
BUILD_DIR="/tmp/osrs_build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Kopieer bestanden naar build dir
cp "$SCRIPT_DIR/osrs_app.py" "$BUILD_DIR/"
cp "$SCRIPT_DIR/osrs_webapp.py" "$BUILD_DIR/"
[ -f "$SCRIPT_DIR/OSRS_GE_SCOUT.png" ] && cp "$SCRIPT_DIR/OSRS_GE_SCOUT.png" "$BUILD_DIR/"
[ -f "$SCRIPT_DIR/osrs_icon.png" ] && cp "$SCRIPT_DIR/osrs_icon.png" "$BUILD_DIR/"

cd "$BUILD_DIR"

# PyInstaller spec: bundelt alles in één .app
ICON_FLAG=""
if [ -n "$ICNS_FILE" ] && [ -f "$ICNS_FILE" ]; then
    ICON_FLAG="--icon=$ICNS_FILE"
fi

python3 -m PyInstaller \
    --name "OSRS GE Scout" \
    --windowed \
    --onedir \
    --noconfirm \
    $ICON_FLAG \
    --add-data "osrs_webapp.py:." \
    --add-data "OSRS_GE_SCOUT.png:." \
    --add-data "osrs_icon.png:." \
    --hidden-import flask \
    --hidden-import requests \
    --hidden-import webview \
    --hidden-import webview.platforms.cocoa \
    --hidden-import pkg_resources.extern \
    --collect-all webview \
    --collect-all flask \
    osrs_app.py 2>&1 | while IFS= read -r line; do
        # Toon alleen belangrijke regels
        case "$line" in
            *WARNING*|*ERROR*|*Building*|*Completed*|*INFO:*bundle*)
                echo "  $line"
                ;;
        esac
    done

APP_BUILT="$BUILD_DIR/dist/OSRS GE Scout.app"
if [ ! -d "$APP_BUILT" ]; then
    echo "❌ Build mislukt. Check /tmp/osrs_build voor details."
    read -p "Druk Enter om te sluiten..."
    exit 1
fi

echo "✅ App gebouwd"

# ── Fix: voeg osrs_webapp.py toe aan Resources (voor auto-updater) ──
RESOURCES="$APP_BUILT/Contents/Resources"
cp "$BUILD_DIR/osrs_webapp.py" "$RESOURCES/" 2>/dev/null

# ── Code signing (ad-hoc) ──
echo "⏳ App ondertekenen..."
xattr -cr "$APP_BUILT" 2>/dev/null
codesign --force --deep -s - "$APP_BUILT" 2>/dev/null && echo "✅ App ondertekend" || echo "⚠️  Signing overgeslagen"

# ── Maak PKG installer ──
echo "⏳ Installer (.pkg) aanmaken..."
PKG_STAGING="/tmp/pkg_staging"
PKG_SCRIPTS="/tmp/pkg_scripts"
rm -rf "$PKG_STAGING" "$PKG_SCRIPTS"
mkdir -p "$PKG_STAGING/Applications"
cp -R "$APP_BUILT" "$PKG_STAGING/Applications/"

mkdir -p "$PKG_SCRIPTS"
cat > "$PKG_SCRIPTS/postinstall" << 'POSTINSTALL'
#!/bin/bash
xattr -cr "/Applications/OSRS GE Scout.app" 2>/dev/null
open "/Applications/OSRS GE Scout.app" 2>/dev/null &
exit 0
POSTINSTALL
chmod +x "$PKG_SCRIPTS/postinstall"

rm -f "$PKG_PATH"
pkgbuild \
    --root "$PKG_STAGING" \
    --scripts "$PKG_SCRIPTS" \
    --identifier "com.osrs.gescout" \
    --version "1.0" \
    --install-location "/" \
    "$PKG_PATH" > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "❌ PKG aanmaken mislukt."
    # Fallback: kopieer de .app direct
    echo "⏳ App direct kopiëren..."
    cp -R "$APP_BUILT" "$SCRIPT_DIR/"
    echo "✅ OSRS GE Scout.app staat in dezelfde map."
else
    echo "✅ Installer aangemaakt"
fi

# Cleanup
rm -rf "$PKG_STAGING" "$PKG_SCRIPTS" "$BUILD_DIR"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   ✅ Build compleet!                      ║"
echo "  ║                                          ║"
echo "  ║   Bestand: OSRS GE Scout.pkg          ║"
echo "  ║   Locatie: zelfde map als dit script     ║"
echo "  ║                                          ║"
echo "  ║   Dit bestand kun je delen met anderen.  ║"
echo "  ║   Zij dubbelklikken → installeren.       ║"
echo "  ║   Geen Python installatie nodig!         ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

open "$SCRIPT_DIR"
sleep 3
osascript -e 'tell application "Terminal" to close front window' 2>/dev/null &
