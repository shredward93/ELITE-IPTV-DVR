import os
import shutil
import xbmc
import xbmcgui

# Paths
SOURCE_DIR = "/sdcard/Download/kodi_sync"
DEST_DIR = xbmc.translatePath("special://home/addons")

def sync():
    dialog = xbmcgui.DialogProgress()
    dialog.create("ELITE Sync", "Initializing sync...")

    if not os.path.exists(SOURCE_DIR):
        xbmcgui.Dialog().ok("ELITE Sync", f"Source directory not found:\n{SOURCE_DIR}")
        return

    items = os.listdir(SOURCE_DIR)
    total = len(items)

    for index, item in enumerate(items):
        src = os.path.join(SOURCE_DIR, item)
        dst = os.path.join(DEST_DIR, item)

        percent = int((index / total) * 100)
        dialog.update(percent, f"Syncing: {item}")

        try:
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        except Exception as e:
            xbmcgui.Dialog().ok("ELITE Sync Error", f"Failed to sync {item}:\n{str(e)}")
            break

    dialog.close()
    xbmcgui.Dialog().notification("ELITE Sync", "Sync Complete! Restarting Kodi...", xbmcgui.NOTIFICATION_INFO, 5000)
    xbmc.executebuiltin("RestartApp")

if __name__ == "__main__":
    sync()
