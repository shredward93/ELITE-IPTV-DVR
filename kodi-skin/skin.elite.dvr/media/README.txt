ELITE IPTV DVR Skin - Media Assets
==================================

Required PNG images to create:

1. panel_rounded.png - Rounded rectangle for panels (18px radius corners)
   - Size: ~40x40 with transparent corners
   - Used for: category panels, dialog backgrounds

2. card_rounded.png - Smaller rounded rectangle for cards (6px radius)
   - Size: ~24x24 with transparent corners
   - Used for: channel items, program cells, buttons

3. pill_rounded.png - Fully rounded pill shape
   - Size: ~48x48 fully rounded
   - Used for: category chips, menu items

4. button_rounded.png - Button background
   - Size: ~48x48 with 22px radius
   - Used for: all button controls

5. circle.png - Solid circle
   - Size: ~100x100
   - Used for: logo background, loading dots

6. white.png - 1x1 white pixel (for color tinting)

7. elite_logo.png - Your logo (copy from Android app)
   - Recommended: 200x200 for startup, 100x100 for header

8. elite_logo_small.png - Smaller version for header
   - Size: 60x60

9. bg_primary.png - Main Kodi background image for the skin
   - Source: copy your `kodi bg.png` file here and rename it to `bg_primary.png`
   - Used for: Home screen, dialogs, and all non-boot skin windows
   - Note: the boot screen keeps using `elite_home_bg.png`

10. icons/*.png - Menu icons (optional):
   - guide.png
   - livetv.png
   - recordings.png
   - timers.png
   - search.png
   - settings.png

Creating these assets:
----------------------
You can use the Android app's drawable assets as templates.
The color tinting is handled by Kodi's colordiffuse attribute,
so most assets can be white/gray and will be tinted at runtime.

Installation:
-------------
1. Zip the skin.elite.dvr folder
2. In Kodi: Settings > Add-ons > Install from zip file
3. Select the skin zip
4. Activate: Settings > Interface > Skin > ELITE IPTV DVR
