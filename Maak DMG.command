#!/bin/bash
# ═══════════════════════════════════════════════════════
#  OSRS GE Scout — DMG Builder
#  Dubbelklik om een installatiebestand (.dmg) te maken
#  dat je kunt delen met anderen.
# ═══════════════════════════════════════════════════════

set -e
cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   OSRS GE Scout — DMG Builder         ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

APP_NAME="OSRS GE Scout"
APP_PATH="/tmp/${APP_NAME}.app"
DMG_NAME="OSRS GE Scout"
DMG_PATH="${SCRIPT_DIR}/${DMG_NAME}.dmg"
STAGING="/tmp/dmg_staging"

# ── Check benodigde bestanden ──
if [ ! -f "$SCRIPT_DIR/osrs_webapp.py" ]; then
    echo "❌ osrs_webapp.py niet gevonden in dezelfde map."
    read -p "Druk Enter om te sluiten..."
    exit 1
fi
if [ ! -f "$SCRIPT_DIR/osrs_app.py" ]; then
    echo "❌ osrs_app.py niet gevonden in dezelfde map."
    read -p "Druk Enter om te sluiten..."
    exit 1
fi

# ── 1. Bouw de .app bundle ──
echo "⏳ App bouwen..."
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Kopieer python bestanden
cp "$SCRIPT_DIR/osrs_webapp.py" "$APP_PATH/Contents/Resources/"
cp "$SCRIPT_DIR/osrs_app.py" "$APP_PATH/Contents/Resources/"
cp "$SCRIPT_DIR/OSRS_GE_SCOUT.png" "$APP_PATH/Contents/Resources/" 2>/dev/null || true

# ── Info.plist ──
cat > "$APP_PATH/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>OSRS GE Scout</string>
    <key>CFBundleDisplayName</key>
    <string>OSRS GE Scout</string>
    <key>CFBundleIdentifier</key>
    <string>com.osrs.gescout</string>
    <key>CFBundleVersion</key>
    <string>2.0</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# ── Launcher script ──
# De truc: exec vervangt bash door python, waardoor pywebview's
# NSApplication het hoofdproces wordt → Dock-icoon + bolletje
cat > "$APP_PATH/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash
RESOURCES_DIR="$(dirname "$0")/../Resources"
LOG_FILE="/tmp/osrs_agent.log"
FIRST_RUN_FILE="$HOME/.osrs_agent/.installed"

# ── Homebrew PATH (Apple Silicon + Intel) ──
if [ -f "/opt/homebrew/bin/brew" ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -f "/usr/local/bin/brew" ]; then
    eval "$(/usr/local/bin/brew shellenv)"
fi

# ── Progress notificatie helper ──
show_progress() {
    osascript -e "display notification \"$1\" with title \"OSRS GE Scout — Setup\"" 2>/dev/null
}

# ── Installatie ──
install_dependencies() {
    if ! command -v python3 &> /dev/null; then
        if ! command -v brew &> /dev/null; then
            osascript -e 'display dialog "OSRS GE Scout heeft Python nodig.\n\nDit wordt nu automatisch geïnstalleerd via Homebrew.\nJe Mac wachtwoord kan gevraagd worden.\n\nDit duurt 2-5 minuten (alleen de eerste keer)." buttons {"Installeren"} default button 1 with title "OSRS GE Scout — Setup" with icon caution' 2>/dev/null
            show_progress "Homebrew wordt geïnstalleerd... Dit duurt 2-5 minuten."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" < /dev/null 2>&1 | tee /tmp/osrs_brew_install.log
            if [ -f "/opt/homebrew/bin/brew" ]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            elif [ -f "/usr/local/bin/brew" ]; then
                eval "$(/usr/local/bin/brew shellenv)"
            fi
            if ! command -v brew &> /dev/null; then
                osascript -e 'display alert "Installatie mislukt" message "Homebrew kon niet worden geïnstalleerd.\nInstalleer Python handmatig via python.org" as critical' 2>/dev/null
                exit 1
            fi
        fi
        show_progress "Python wordt geïnstalleerd..."
        brew install python3 2>&1 | tee /tmp/osrs_python_install.log
        if ! command -v python3 &> /dev/null; then
            osascript -e 'display alert "Installatie mislukt" message "Python kon niet worden geïnstalleerd." as critical' 2>/dev/null
            exit 1
        fi
    fi
    NEED_PIP=0
    python3 -c "import flask" 2>/dev/null || NEED_PIP=1
    python3 -c "import requests" 2>/dev/null || NEED_PIP=1
    python3 -c "import webview" 2>/dev/null || NEED_PIP=1
    if [ $NEED_PIP -eq 1 ]; then
        show_progress "Packages installeren (Flask, pywebview)... ~1 minuut."
        pip3 install flask requests pywebview --break-system-packages 2>/tmp/osrs_pip_install.log || pip3 install flask requests pywebview 2>>/tmp/osrs_pip_install.log
        # Check of alles geinstalleerd is
        if ! python3 -c "import flask; import requests; import webview" 2>/dev/null; then
            osascript -e 'display alert "Installatie mislukt" message "Packages konden niet worden geïnstalleerd.\nBekijk /tmp/osrs_pip_install.log voor details." as critical' 2>/dev/null
            exit 1
        fi
    fi
    mkdir -p "$HOME/.osrs_agent"
    touch "$FIRST_RUN_FILE"
}

if [ ! -f "$FIRST_RUN_FILE" ] || ! command -v python3 &> /dev/null || ! python3 -c "import flask; import webview" 2>/dev/null; then
    install_dependencies
fi

# ── Stop draaiende instantie ──
lsof -ti:5050 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1

# ── Start app ──
cd "$RESOURCES_DIR"
exec python3 osrs_app.py 2>"$LOG_FILE"
LAUNCHER
chmod +x "$APP_PATH/Contents/MacOS/launcher"

# ── App icoon ──
ICON_PNG="$SCRIPT_DIR/osrs_icon.png"
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

    iconutil -c icns "$ICONSET_DIR" -o "$APP_PATH/Contents/Resources/AppIcon.icns" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✅ Icoon ingesteld"
    else
        echo "⚠️  Icoon kon niet worden omgezet (standaard icoon wordt gebruikt)"
    fi
    rm -rf "$ICONSET_DIR"
fi

echo "✅ App gebouwd"

# ── 2. Code signing (ad-hoc) ──
echo "⏳ App ondertekenen..."
chmod +x "$APP_PATH/Contents/MacOS/launcher"
xattr -cr "$APP_PATH" 2>/dev/null
codesign --force --deep -s - "$APP_PATH" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ App ondertekend (ad-hoc)"
else
    echo "⚠️  Code signing overgeslagen (gebruiker moet rechtermuisklik → Open gebruiken)"
fi

# ── 3. Maak PKG installer ──
echo "⏳ Installer (.pkg) aanmaken..."

PKG_PATH="${SCRIPT_DIR}/${DMG_NAME}.pkg"
PKG_STAGING="/tmp/pkg_staging"
PKG_SCRIPTS="/tmp/pkg_scripts"

rm -rf "$PKG_STAGING" "$PKG_SCRIPTS"
mkdir -p "$PKG_STAGING/Applications"
cp -R "$APP_PATH" "$PKG_STAGING/Applications/"

# Post-install script: verwijdert quarantine en maakt launcher executable
mkdir -p "$PKG_SCRIPTS"
cat > "$PKG_SCRIPTS/postinstall" << 'POSTINSTALL'
#!/bin/bash
APP="/Applications/OSRS GE Scout.app"
xattr -cr "$APP" 2>/dev/null
chmod +x "$APP/Contents/MacOS/launcher"
# Open de app na installatie
su "$USER" -c "open \"$APP\"" 2>/dev/null &
exit 0
POSTINSTALL
chmod +x "$PKG_SCRIPTS/postinstall"

# Bouw de .pkg
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
    read -p "Druk Enter om te sluiten..."
    exit 1
fi

rm -rf "$PKG_STAGING" "$PKG_SCRIPTS"
rm -rf "$APP_PATH"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   ✅ Installer aangemaakt!                ║"
echo "  ║                                          ║"
echo "  ║   Bestand: OSRS GE Scout.pkg          ║"
echo "  ║   Locatie: zelfde map als dit script     ║"
echo "  ║                                          ║"
echo "  ║   Dit bestand kun je delen met anderen.  ║"
echo "  ║   Zij dubbelklikken → installeren.       ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

open "$SCRIPT_DIR"
sleep 3
osascript -e 'tell application "Terminal" to close front window' 2>/dev/null &
