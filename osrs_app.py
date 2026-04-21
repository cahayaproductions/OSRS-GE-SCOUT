#!/usr/bin/env python3
"""
OSRS GE Scout — Native App Launcher
Start de Flask server + opent een native venster.
Venster sluiten = server stopt = app stopt.
"""

import threading, sys, os, signal, time, socket

def start_server():
    """Start de Flask webapp in een achtergrond-thread."""
    os.environ["OSRS_NO_BROWSER"] = "1"
    # Check of er updates staan in ~/.osrs_agent/updates/
    update_dir = os.path.join(os.path.expanduser("~"), ".osrs_agent", "updates")
    updated_webapp = os.path.join(update_dir, "osrs_webapp.py")
    use_update = False
    if os.path.exists(updated_webapp):
        if update_dir not in sys.path:
            sys.path.insert(0, update_dir)
        use_update = True
    # Fallback: check Resources map (voor niet-PyInstaller builds)
    elif hasattr(sys, '_MEIPASS'):
        exe = os.path.realpath(sys.executable)
        resources = os.path.join(os.path.dirname(os.path.dirname(exe)), "Resources")
        if os.path.exists(os.path.join(resources, "osrs_webapp.py")):
            if resources not in sys.path:
                sys.path.insert(0, resources)
    try:
        import osrs_webapp
        osrs_webapp.app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)
    except Exception as e:
        # Als de update kapot is: verwijder hem en probeer de bundled versie
        if use_update:
            print(f"[OSRS GE Scout] Update kapot ({e}), verwijder en val terug op bundled versie...")
            try:
                os.remove(updated_webapp)
                # Verwijder ook osrs_app.py uit updates als die er staat
                updated_app = os.path.join(update_dir, "osrs_app.py")
                if os.path.exists(updated_app):
                    os.remove(updated_app)
            except: pass
            # Verwijder de update dir uit sys.path en reload
            if update_dir in sys.path:
                sys.path.remove(update_dir)
            # Probeer opnieuw met bundled versie
            if 'osrs_webapp' in sys.modules:
                del sys.modules['osrs_webapp']
            import osrs_webapp
            osrs_webapp.app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)
        else:
            raise

def port_open():
    """Snelle check of poort 5050 luistert."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", 5050))
        s.close()
        return True
    except:
        return False

def kill_server():
    """Stop de Flask server."""
    try:
        import subprocess
        r = subprocess.run(["lsof", "-ti:5050"], capture_output=True, text=True)
        for pid in r.stdout.strip().split("\n"):
            if pid.strip():
                try: os.kill(int(pid.strip()), signal.SIGTERM)
                except: pass
    except:
        pass

def set_macos_app_name(name="OSRS GE Scout"):
    """Zet de macOS menubalk-titel (ipv 'Python')."""
    try:
        from ctypes import cdll, c_char_p, c_int
        lib = cdll.LoadLibrary("/usr/lib/libc.dylib")
        # Pas BSD process naam aan
        lib.setprogname(c_char_p(name.encode()))
    except: pass
    try:
        # NSProcessInfo displayName — zet de menubalk-titel
        from Foundation import NSBundle
        info = NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = name
    except: pass

def main():
    set_macos_app_name()

    # Start Flask server op achtergrond
    server = threading.Thread(target=start_server, daemon=True)
    server.start()

    # Snelle port-check (max 10 sec)
    for _ in range(50):
        if port_open():
            break
        time.sleep(0.2)

    # Open native venster
    import webview
    webview.create_window(
        title="OSRS GE Scout",
        url="http://127.0.0.1:5050",
        width=1280,
        height=820,
        min_size=(900, 600),
    )
    webview.start()

    # Venster dicht → stoppen
    kill_server()
    os._exit(0)

if __name__ == "__main__":
    main()
