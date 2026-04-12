# skills for this project

MCP	Status	What it gives you
context7	Connected	Latest docs for Jetpack Compose TV, Media3, ExoPlayer — just say "use context7" in a prompt
brave-search	Connected	Web search for GitHub issues, Stack Overflow, community solutions — needs real API key
android-adb	Connected	Logcat, screenshots, UI hierarchy from running emulator

## Android TV App UX/UI Skills (from Spyro-Soft Article)

### Section 1: Master the 10-foot experience and viewing distance
- **Minimum 22px font size** for body text (unreadable below this from 3+ meters)
- **Thicker, substantial typefaces** with increased line spacing (20-30% more)
- **Wider character spacing** for better distance readability
- **Roboto font** recommended (Google-optimized for TV screens)
- **Sans-serif fonts** for labels and longer text
- **Avoid decorative fonts** (hard to read from distance)
- **Test from 3+ meters** in different lighting conditions
- **Consider lighting**: morning glare, evening harsh whites, night high contrast

### Section 2: Prioritise simplicity and reduce visual clutter
- **Ruthless simplification** - TV interfaces must communicate clearly across the room
- **Lean-back experience** - families multitasking, seek entertainment with minimal cognitive load
- **Generous white space** - most powerful design tool at viewing distances
- **Large, clear content tiles** with minimal text overlay
- **Consistent spacing patterns** and limit simultaneous choices
- **Single primary purpose** per screen
- **Content front and centre** - eliminate non-essential elements
- **Limit on-screen complexity** - avoid overwhelming choices
- **Visual hierarchy** - one explicit primary action per screen
- **Minimize text density** - prefer visual elements over descriptions
- **Group related functions** - maintain clean, organized layouts

### Section 3: Master remote control navigation
- **D-pad navigation** - only up/down/left/right/select movement
- **Clear focus states** - instant visual feedback showing selected element
- **Obvious visual distinction** - bold borders, color changes, scaling effects
- **Predictable navigation paths** - logical movement patterns
- **Accessible back button** - always returns to previous screen without confirmations
- **Consistent spacing** - equal distances between focusable elements
- **Avoid blocking exits** with confirmation screens
- **Clear path to previous content or home screen**

### Section 5: Handle safe areas and overscan properly
- **TV screens don't display edge-to-edge** - overscan cuts off borders
- **Platform-specific margins**:
  - **Android TV**: 5% margin - minimum 27px top/bottom, 48px left/right
  - **Apple tvOS**: 60 points top/bottom, 80 points sides
- **Test on actual televisions** - emulators don't replicate real behavior
- **Keep key UI elements within safe boundaries**
- **Use overscan zones only for decorative backgrounds** (can be safely cropped)
- **Older TVs** have aggressive cropping, modern TVs still need safe areas