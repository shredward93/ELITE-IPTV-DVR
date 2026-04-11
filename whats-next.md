<original_task>
Two tasks for this session:
1. Make the Android app persist/save the PC server URL across restarts.
2. Add an EPG category browser with a full TV guide grid interface (channels × time).
</original_task>

<work_completed>
## Task 1: PC Location Saving — Already Implemented (no code changes needed)
- `MainViewModel.kt`: SharedPreferences on init, `savePcUrl()` persists via `.apply()`
- `Navigation.kt` line 39: skips Pair screen if `pcUrl` non-empty on app launch
- `PairScreen.kt`: pre-populates URL field from `viewModel.pcUrl`
- Settings button → navigates to Pair screen with URL pre-filled

## Task 2: EPG Category Browser + Full TV Guide Grid — COMPLETE

### PC backend (`core/web_server.py`)
- Fixed `/api/epg`: now calls `decode_epg_text()` on `title` and `description` before returning JSON (EPG was returning raw base64 strings before)
- Added `from concurrent.futures import ThreadPoolExecutor` and `from core.epg import decode_epg_text`
- New `GET /api/categories`: Xtream `get_live_categories` → `[{category_id, category_name}]`
- New `GET /api/channels/by-category?category_id=X`: Xtream `get_live_streams&category_id=X` → `[{name, id}]`
- New `GET /api/epg/multi?channel_ids=X,Y,Z&limit=N`: parallel fetch via `ThreadPoolExecutor(max_workers=10)`, capped at 30 channels, base64-decoded, returns `[{channel_id, listings[]}]`

### Android Models (`api/Models.kt`)
Added two new data classes:
```kotlin
data class Category(
    @SerializedName("category_id")   val categoryId: String,
    @SerializedName("category_name") val categoryName: String,
)
data class ChannelEpg(
    @SerializedName("channel_id") val channelId: String,
    val listings: List<EpgListing>,
)
```

### Android API (`api/ApiService.kt`)
Added 3 new suspend functions:
```kotlin
@GET("api/categories")
suspend fun getCategories(): List<Category>

@GET("api/channels/by-category")
suspend fun getChannelsByCategory(@Query("category_id") categoryId: String): List<Channel>

@GET("api/epg/multi")
suspend fun getMultiEpg(
    @Query("channel_ids") channelIds: String,
    @Query("limit") limit: Int = 6,
): List<ChannelEpg>
```

### Android ViewModel (`viewmodel/MainViewModel.kt`)
Added state + load functions:
- `var categories`, `var categoryChannels`, `var guideEpg` state variables
- `loadCategories()`, `loadChannelsByCategory(categoryId)`, `loadGuideEpg(channelIds, limit)` functions
- `loadChannelsByCategory` resets both `categoryChannels` and `guideEpg` to empty before fetching

### Android EpgGuideScreen (`ui/guide/EpgGuideScreen.kt`) — NEW FILE
Full TV guide screen with:
- `@file:OptIn(ExperimentalTvMaterial3Api::class)`
- Left sidebar (220dp): `LazyColumn` of `CategoryItem` (TV `Surface`, orange on focus/selected)
- Right panel: header bar + `GuideTimeHeader` + `LazyColumn` of `GuideChannelRow`
- `GuideTimeHeader`: 28dp row, 160dp gutter, time labels every 30 min
- `GuideChannelRow`: 160dp channel name `Surface` (play live) + `LazyRow` of `ProgramCell`
- `ProgramCell`: width = `(durationMin * DP_PER_MIN).dp` clamped to min 60dp; green tint for current programme; `isNow` = startMs <= nowMs && stopMs > nowMs
- `parseEpgMs()`: `ThreadLocal<SimpleDateFormat("yyyyMMddHHmmss", UTC)>` for thread-safe parsing
- `formatEpgTime()` and `epgDurationMins()` declared `internal` (shared with TVGuideScreen in same package)
- Schedule AlertDialog with channel name, time range, confirm/cancel
- Constants: `DP_PER_MIN = 4`, `WINDOW_MINS = 180`, `PRE_MINS = 30`
- LaunchedEffect chain: Unit→loadCategories; selectedCategory→loadChannelsByCategory; categoryChannels→loadGuideEpg(first 30 channels, limit=8)

### Android Navigation (`ui/Navigation.kt`)
- Added `object GuideGrid : Screen("guide_grid")` to sealed class
- Added `composable(Screen.GuideGrid.route)` block wiring `EpgGuideScreen`
- Added `onGuideGridOpen` lambda to `ChannelBrowserScreen` composable call

### Android ChannelBrowserScreen (`ui/channels/ChannelBrowserScreen.kt`)
- Added `onGuideGridOpen: () -> Unit` parameter
- Added `TvButton("TV Guide", onClick = onGuideGridOpen)` in header Row (before DVR Library)

### Android TVGuideScreen (`ui/guide/TVGuideScreen.kt`)
- Removed duplicate `private fun formatEpgTime()` and `private fun epgDurationMins()` (now `internal` in EpgGuideScreen.kt, same package)
- Added comment noting their new location

## Key decisions
- Used independent `LazyRow` per channel row (not shared `ScrollState`) — D-pad navigation works correctly; trade-off is rows don't pixel-align horizontally when scrolling
- Base64 decoding on PC side, not Android side — keeps Android model simple (plain String)
- `internal` visibility for shared time utilities in same package — avoids duplication without exposing to other packages
- `ThreadLocal<SimpleDateFormat>` for `parseEpgMs()` — thread-safe without synchronization cost
</work_completed>

<work_remaining>
## 1. Build APK
```bash
cd "android" && \
  JAVA_HOME="/c/Program Files/Android/Android Studio/jbr" \
  ANDROID_HOME="/c/Users/eddyd/AppData/Local/Android/Sdk" \
  "/c/Users/eddyd/.gradle/wrapper/dists/gradle-8.2-bin/bbg7u40eoinfdyxsxr3z4i7ta/gradle-8.2/bin/gradle" \
  assembleDebug --no-daemon
```

## 2. Install on emulator
```bash
"/c/Users/eddyd/AppData/Local/Android/Sdk/platform-tools/adb.exe" install -r \
  android/app/build/outputs/apk/debug/app-debug.apk
```

## 3. Start PC server
Ensure PC server is running and IPTV credentials are configured in `config.py`.

## 4. End-to-end test — EpgGuideScreen
- Pair screen: enter `http://10.0.2.2:8080`, confirm connection
- ChannelBrowser: "TV Guide" button appears in header → navigates to EpgGuideScreen
- Select a category → channel list loads with EPG grid
- Programme cells appear at proportional widths; current programme is green-tinted
- Click channel name → plays live stream
- Click programme cell → schedule dialog appears → confirm schedules recording
- Back button returns to ChannelBrowserScreen

## 5. Verify PC endpoints directly
```bash
curl http://localhost:8080/api/categories
curl "http://localhost:8080/api/channels/by-category?category_id=1"
curl "http://localhost:8080/api/epg/multi?channel_ids=1234,5678&limit=8"
```
Confirm: titles are plain text (not base64), listings have valid `start`/`stop` in `yyyyMMddHHmmss` format.

## Optional enhancements (not requested, defer)
- Time window scrubbing: forward/back buttons to shift the 3-hour window
- Lazy-load more channels as user scrolls past first 50 in guide
- Current-time indicator line: `Canvas { drawLine(orange, x=nowOffsetDp) }` overlay
- Synchronized horizontal scroll across all rows (complex, lower priority)
</work_remaining>

<attempted_approaches>
## Synchronized horizontal scroll — rejected
Considered sharing a single `rememberScrollState()` across the time header `Row` and all channel `Row`s via `Modifier.horizontalScroll(sharedHScroll)`. This would give true pixel-aligned grid scrolling. Rejected because:
- Every `LazyRow` item would need to be a non-lazy `Row` with `horizontalScroll`, losing item recycling
- D-pad focus traversal breaks when using `horizontalScroll` on TV — focus can't move between cells correctly
- Chosen approach: independent `LazyRow` per channel row; D-pad works correctly; rows don't share scroll position but each row is independently navigable

## Base64 decoding on Android — rejected
Could have decoded base64 in Android Kotlin. Rejected: better to keep Android models as plain types; PC already has `decode_epg_text()` in `core/epg.py` that handles encoding variants.

## Unused imports removed from EpgGuideScreen.kt
Initially imported `rememberScrollState` and `horizontalScroll` when planning synchronized scroll. Removed after switching to `LazyRow` approach.

## TVGuideScreen.kt private function conflict
`formatEpgTime` and `epgDurationMins` were `private` in `TVGuideScreen.kt`. Making them accessible to `EpgGuideScreen.kt` (same package) required changing to `internal` and moving them to `EpgGuideScreen.kt` as the canonical location.
</attempted_approaches>

<critical_context>
## SDK / Tool Paths

| Tool | Path |
|------|------|
| Android SDK | `C:\Users\eddyd\AppData\Local\Android\Sdk` |
| ADB | `C:\Users\eddyd\AppData\Local\Android\Sdk\platform-tools\adb.exe` |
| Emulator | `C:\Users\eddyd\AppData\Local\Android\Sdk\emulator\emulator.exe` |
| Gradle binary | `C:\Users\eddyd\.gradle\wrapper\dists\gradle-8.2-bin\bbg7u40eoinfdyxsxr3z4i7ta\gradle-8.2\bin\gradle` |
| Java | `C:\Program Files\Android\Android Studio\jbr` |
| AVD | `Television_1080p` (API 33, Android TV, x86_64) |

## Gradle build — use the binary directly, NOT gradlew (quoting bug on Windows)

## Emulator host alias
From Android emulator: `10.0.2.2` = host PC. Pair screen URL: `http://10.0.2.2:8080`

## tv-material 1.0.0 API (stable)
- `@file:OptIn(ExperimentalTvMaterial3Api::class)` required on all TV screens
- `Surface` from `androidx.tv.material3` (focusable, D-pad-aware) — NOT from `androidx.compose.material3`
- `ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(...))`
- `ClickableSurfaceDefaults.colors(containerColor=..., focusedContainerColor=...)`
- Standard `LazyColumn`/`LazyRow` (not `TvLazyColumn`)

## Xtream Codes API
- Categories: `action=get_live_categories` → `[{category_id, category_name, parent_id}, ...]`
- Channels by category: `action=get_live_streams&category_id=X` → `[{num, name, stream_id, ...}, ...]`
- EPG: `action=get_short_epg&stream_id=X&limit=N` → `{epg_listings: [{title(b64), description(b64), start, end}]}`
- Channel `id` in Android model = Xtream `stream_id`
- EPG title/description are base64-encoded — must decode before returning to Android

## EPG time format
Xtream EPG `start`/`stop` format: `"yyyyMMddHHmmss +0000"` — parse only first 14 chars (trim whitespace first)

## Design tokens
- Background: `Color.Black`
- Accent/orange: `Color(0xFFF89344)`
- Card bg: `Color(0xFF1E1E1E)`, focused: `Color(0xFF2E2E2E)`
- Current programme green: `Color(0xFF1A2E1A)` bg, `Color(0xFF90EE90)` text
- Success: `Color(0xFF2ECC71)`
- Body text min: 18sp, min interactive target: 48dp

## File layout (Android)
```
android/app/src/main/java/com/elite/iptv/dvr/
  api/
    ApiClient.kt    — Retrofit singleton, setBaseUrl()
    ApiService.kt   — Retrofit interface
    Models.kt       — all data classes
  ui/
    Navigation.kt
    channels/ChannelBrowserScreen.kt
    guide/
      TVGuideScreen.kt       — per-channel EPG list (uses internal fns from EpgGuideScreen)
      EpgGuideScreen.kt      — full category+grid TV guide (NEW)
    library/DVRLibraryScreen.kt
    pair/PairScreen.kt
    player/PlayerScreen.kt
  viewmodel/MainViewModel.kt
  MainActivity.kt
```
</critical_context>

<current_state>
## Status

| Item | Status |
|------|--------|
| PC backend (DVR, all prior endpoints) | ✅ Complete |
| All Android screens (prior session) | ✅ Written |
| PC location saving (Android SharedPreferences) | ✅ Already implemented |
| EPG base64 decode fix (`web_server.py`) | ✅ Done |
| PC `/api/categories` endpoint | ✅ Done |
| PC `/api/channels/by-category` endpoint | ✅ Done |
| PC `/api/epg/multi` endpoint | ✅ Done |
| Android `Models.kt` (Category, ChannelEpg) | ✅ Done |
| Android `ApiService.kt` (3 new endpoints) | ✅ Done |
| Android `MainViewModel.kt` (guide state + methods) | ✅ Done |
| `EpgGuideScreen.kt` (full category + grid TV guide) | ✅ Done |
| `Navigation.kt` GuideGrid route | ✅ Done |
| `ChannelBrowserScreen.kt` TV Guide button | ✅ Done |
| `TVGuideScreen.kt` deduplication cleanup | ✅ Done |
| APK rebuilt and tested on emulator | ❌ Not done — next action |

## Next action
Build the APK and test end-to-end on the `Television_1080p` emulator. All code is written; no further edits are expected before testing.
</current_state>
