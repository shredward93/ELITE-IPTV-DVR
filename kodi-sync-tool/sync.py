import os
import shutil
import xbmc
import xbmcgui
import xbmcvfs

# Paths
SOURCE_DIR = "/sdcard/Download/kodi_sync"

# Fix for Kodi 19+ (Python 3)
try:
    DEST_DIR = xbmcvfs.translatePath("special://home/addons")
except AttributeError:
    DEST_DIR = xbmc.translatePath("special://home/addons")

def sync():
    dialog = xbmcgui.DialogProgress()
    dialog.create("ELITE Sync", "Initializing sync...")

    if not os.path.exists(SOURCE_DIR):
        xbmcgui.Dialog().ok("ELITE Sync", f"Source directory not found:\n{SOURCE_DIR}")
        return

    items = os.listdir(SOURCE_DIR)
    # Filter out any hidden files or system files
    items = [i for i in items if i.startswith('skin.') or i.startswith('plugin.')]
    total = len(items)

    if total == 0:
        xbmcgui.Dialog().ok("ELITE Sync", "No ELITE addons found in Download folder.")
        return

    for index, item in enumerate(items):
        src = os.path.join(SOURCE_DIR, item)
        dst = os.path.join(DEST_DIR, item)

        percent = int((index / total) * 100)
        dialog.update(percent, f"Syncing: {item}")

        try:
            # Remove old version if exists
            if os.path.exists(dst):
                xbmc.log(f"ELITE Sync: Removing existing {dst}", xbmc.LOGINFO)
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)

            # Copy new version
            xbmc.log(f"ELITE Sync: Copying {src} to {dst}", xbmc.LOGINFO)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        except Exception as e:
            xbmc.log(f"ELITE Sync ERROR: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("ELITE Sync Error", f"Failed to sync {item}:\n{str(e)}")
            break

    dialog.close()
    xbmcgui.Dialog().notification("ELITE Sync", "Sync Complete! Restarting Kodi...", xbmcgui.NOTIFICATION_INFO, 5000)
    xbmc.sleep(2000)
    # Force Kodi to reload the skin/addons
    xbmc.executebuiltin("UpdateAddonRepos")
    xbmc.executebuiltin("UpdateLocalAddons")
    # Some versions of Kodi don't support RestartApp via script, so we notify the user
    xbmcgui.Dialog().ok("ELITE Sync", "Sync finished! Please RESTART Kodi manually to see changes.")

if __name__ == "__main__":
    sync()
