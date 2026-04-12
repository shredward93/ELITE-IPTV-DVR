# ELITE IPTV DVR Kodi Skin

A custom Kodi skin that brings the premium ELITE IPTV DVR Android TV experience to Kodi.

## Features

- **Signature Gold/Orange Accent** (`#F89344`) throughout the interface
- **Dark Theme** matching the Android app palette
- **Rounded Panels & Cards** (18px radius)
- **Pill-shaped Category Chips** (22px radius)
- **Custom Startup Animation** with logo reveal
- **TV-optimized Layout** with safe areas
- **Focused State Highlights** in bright yellow (`#FFD24C`)

## Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Elite Accent | `#F89344` | Buttons, loading, selected items |
| Elite Accent Light | `#FFD24C` | Focus borders |
| Background Primary | `#000000` | Base background |
| Panel Background | `#0F0F0F` | Sidebar panels |
| Card Background | `#1A1A1A` | List items, cards |
| Card Hover | `#262626` | Hover states |
| Text Primary | `#FFFFFF` | Main text |
| Text Secondary | `#E0E0E0` | Subheadings |
| Text Tertiary | `#BDBDBD` | Descriptions |

## Installation

### Method 1: Zip Install

1. Zip the `skin.elite.dvr` folder:
   ```bash
   cd kodi-skin
   zip -r skin.elite.dvr.zip skin.elite.dvr/
   ```

2. In Kodi, go to:
   - Settings > Add-ons > Install from zip file
   - Select `skin.elite.dvr.zip`

3. Activate the skin:
   - Settings > Interface > Skin
   - Select "ELITE IPTV DVR"

### Method 2: Development Install

Copy the skin folder to your Kodi addons directory:

- **Windows**: `%APPDATA%\Kodi\addons\`
- **Linux**: `~/.kodi/addons/`
- **Android**: `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/`
- **macOS**: `~/Library/Application Support/Kodi/addons/`

## Screens Included

- `Home.xml` - Main menu with logo header, TV Guide/Live TV/DVR Library shortcuts
- `Startup.xml` - Branded boot animation with logo
- `DialogConfirm.xml` - Confirmation dialogs with gold accent buttons
- `DialogButtonMenu.xml` - Power menu (Exit, Shutdown, Reboot, etc.)

## Integration with ELITE DVR Backend

To fully integrate your DVR backend, create a Kodi video plugin:

```python
# plugin.video.elitedvr/addon.py
import xbmcplugin
import xbmcgui
import requests

# Fetch from your /api/guide endpoint
response = requests.get('http://your-server/api/guide')
guide_data = response.json()

# Present in Kodi native UI
```

## Customization

### Change Colors
Edit `colors/defaults.xml`:
```xml
<color name="elite_accent">FFYOURCOLOR</color>
```

### Add Your Logo
Copy your `elite_logo.png` to the `media/` folder.

### Modify Layout
Edit XML files in the `xml/` folder. Key attributes:
- `colordiffuse` - Applies color tint to textures
- `border` - Controls rounded corner radius
- `font` - References fonts from Font.xml

## File Structure

```
skin.elite.dvr/
├── addon.xml           # Skin manifest
├── colors/
│   └── defaults.xml    # Color definitions
├── xml/
│   ├── Font.xml        # Typography
│   ├── Includes.xml    # Reusable components
│   ├── Home.xml        # Main menu
│   ├── Startup.xml     # Boot animation
│   └── Dialog*.xml     # Dialog windows
└── media/
    ├── panel_rounded.png
    ├── card_rounded.png
    ├── pill_rounded.png
    ├── elite_logo.png
    └── white.png
```

## Tips

- Use `colordiffuse` liberally - most textures can be white and tinted
- Create placeholder PNGs for textures (even 1x1 white pixels work)
- Test on actual TV from 3+ meters distance
- The focus border color (`elite_accent_light`) should be highly visible

## License

GPL-2.0-or-later
