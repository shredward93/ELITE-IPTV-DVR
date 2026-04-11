<original_task>
Troubleshoot and fix ExoPlayer live HLS playback issues:
- Video playing faster than 1× speed
- Green overlay flashes
- Periodic skipping and halting
</original_task>

<work_completed>
## Architecture migration (completed last session)
Rewrote the entire DVR pipeline from manual `.ts` segment polling → proper HLS:
- **core/dvr_manager.py**: FFmpeg now runs `-f hls` with `-hls_time 4`, `hls_list_size 75`, `delete_segments+omit_endlist+program_date_time`. Rolling 5-minute manifest window. `_clear_buffer()` kills orphaned `ffmpeg.exe` on Windows before deleting files.
- **core/web_server.py**: Added `/dvr/playlist.m3u8` route (serves manifest with `no-cache`), segment serving on `/dvr/seg_*.ts`.
- **android/app/build.gradle.kts**: Added `media3-exoplayer-hls:1.3.0`.
- **android/app/.../api/ApiClient.kt**: Replaced `dvrSegmentUrl()` with `dvrPlaylistUrl()` → `/dvr/playlist.m3u8`.
- **android/app/.../ui/player/PlayerScreen.kt**: Single HLS `MediaItem` with `LiveConfiguration` (targetOffset=20s, speed locked 1.0/1.0). `DefaultLoadControl` (15s min, 60s max, 4s start, 8s rebuffer). Focus nudge loop every 750ms.

## Bugs fixed
| Bug | Root cause | Fix applied |
|-----|-----------|-------------|
| 30-sec video freeze every 2 min | H.264 decoder reset at segment boundaries (raw .ts playlist) | Switched to HLS architecture |
| No audio | Source AC3, emulator has no AC3 decoder | `-c:a aac -b:a 192k -ac 2` transcode |
| Audio/video speed ramp | `LiveConfiguration` `maxPlaybackSpeed=1.03f` caused ExoPlayer to speed up after decoder resets | Locked both min/max to `1.0f` |
| Black screen + 30-min pre-filled timeline | `hls_list_size=5400` → thousands of listed segments, early ones deleted → 404 cascade | Reduced to `hls_list_size=75` |
| `append_list` continuation bug | FFmpeg continued sequence numbers from old session → 404s on new session | Removed `append_list` flag |
| Orphaned FFmpeg on Windows | Old server's FFmpeg held `.ts` files open, `_clear_buffer()` silently failed | Added `taskkill /F /IM ffmpeg.exe` before deletion |
| Fast-forward every ~9s | `onPlayerError` recovery called `seekToDefaultPosition()` on every emulator audio stall (`UnexpectedDiscontinuityException`) | Removed `onPlayerError` listener entirely |
| Green overlay flashes | Missing SPS/PPS at segment boundaries | Added `-bsf:v dump_extra` to FFmpeg command |

## Current FFmpeg command (dvr_manager.py)
```python
cmd = [
    "ffmpeg", "-y",
    "-reconnect", "1", "-reconnect_at_eof", "1",
    "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
    "-timeout", "15000000",
    "-fflags", "+discardcorrupt",
    "-avoid_negative_ts", "make_zero",
    "-i", stream_url,
    "-c:v", "copy",
    "-bsf:v", "dump_extra",
    "-c:a", "aac", "-b:a", "192k", "-ac", "2",
    "-f", "hls",
    "-hls_time", "4",
    "-hls_list_size", "75",
    "-hls_flags", "delete_segments+omit_endlist+program_date_time",
    "-hls_segment_type", "mpegts",
    "-hls_segment_filename", seg_pattern,
    playlist,
]
```

## APK state
Built and installed on emulator last session. Server has NOT been restarted after `-bsf:v dump_extra` was added.
</work_completed>

<work_remaining>
## Immediate: Apply pending fix
1. **Restart Python server** — `-bsf:v dump_extra` is in code but server is still running the old command. Must restart to take effect.
2. **Retest green flash** — after restart, play a channel for 5+ minutes; confirm green flashes stop.

## Troubleshoot "playing too fast"
Current hypothesis: source PTS discontinuities interacting with `avoid_negative_ts make_zero` cause the HLS muxer to write broken DTS in segments, which ExoPlayer interprets as fast playback.

Steps to investigate (in order):
1. **ffprobe 5–6 consecutive segments** — check PTS/DTS continuity across segment boundaries:
   ```
   ffprobe -v quiet -print_format json -show_packets -select_streams v:0 dvr_buffer/seg_000075.ts | head -60
   ```
   Look for: large DTS jumps, negative values, or DTS not matching previous segment's last DTS + frame_duration.
2. **Try removing `avoid_negative_ts make_zero`** — if source has clean PTS, this flag can introduce drift. Remove it and retest.
3. **Try different channel** — rule out whether "fast" is stream-specific (some providers have timing issues on certain channels).
4. **Add A/V resync** — if AC3→AAC drift is causing the perception of fast video:
   ```
   "-af", "aresample=async=1000"
   ```
   Add to FFmpeg command after `-ac 2`.
5. **Check `#EXT-X-PROGRAM-DATE-TIME` timestamps** — open `dvr_buffer/playlist.m3u8` and verify `PROGRAM-DATE-TIME` values increment by ~4s per segment and match wall clock.

## Troubleshoot skipping/halting
These may be emulator-only artifacts (audio HAL stalls → `UnexpectedDiscontinuityException`). Steps:
1. Check logcat for `ExoPlayerImpl` or `AudioTrack` errors during a stall:
   ```
   adb logcat -s ExoPlayerImpl AudioTrack MediaCodecVideoRenderer
   ```
2. If stalls correlate with `device stall time corrected` in logcat → emulator-only, will not occur on real hardware.
3. If stalls occur independently → increase `minBufferMs` in `DefaultLoadControl` from 15s to 30s.

## Verification checklist
- [ ] No green flashes after server restart
- [ ] Playback speed appears 1× (news ticker/clock on screen confirm)
- [ ] No stalls for 10+ consecutive minutes
- [ ] Audio in sync with video
</work_remaining>

<attempted_approaches>
## Fast-forward cause — ruled out
- `onPlayerError` → `seekToDefaultPosition()` on every `UnexpectedDiscontinuityException` (emulator audio stalls ~every 9s). This was confirmed as the cause of the apparent fast-forward in the previous session and was removed. However fast playback persisted → root cause is upstream of the error handler.
- `LiveConfiguration` speed ramp (`maxPlaybackSpeed=1.03f`) — also caused speed issues; fixed by locking to 1.0/1.0, but fast play is still reported, so a second cause remains.

## Approaches NOT yet tried
- Removing `avoid_negative_ts make_zero`
- Adding `aresample=async=1000`
- Testing a different channel
- Checking PTS with ffprobe
</attempted_approaches>

<critical_context>
## Key architecture facts
- HLS manifest is at `dvr_buffer/playlist.m3u8`. It's a rolling 5-minute window (75 × 4s segments). `delete_segments` removes old `.ts` files from disk; `omit_endlist` keeps it a live stream (no `#EXT-X-ENDLIST`).
- `program_date_time` flag is critical — ExoPlayer uses `#EXT-X-PROGRAM-DATE-TIME` to calculate live offset. Without it, `LiveConfiguration.targetOffsetMs` has no anchor and ExoPlayer defaults to live edge (causes stalling).
- `dump_extra` injects SPS/PPS before every keyframe so each segment is independently decodable. Without it, segments after the first produce green frames until the next IDR.
- AC3 audio is transcoded to AAC because Android/emulator lacks an AC3 decoder. This transcode introduces ~20–40ms A/V drift per segment boundary, which compounds over time and may cause perceived speed differences.
- `avoid_negative_ts make_zero` was added to handle streams where PTS starts at a large non-zero value. It forces the first PTS to 0. On streams where PTS is already clean this can introduce a discontinuity.
- Emulator: `http://10.0.2.2:8080` → PC. Real TV on LAN: `http://192.168.2.81:8080`.

## Files to touch for player fixes
- `core/dvr_manager.py` — FFmpeg command tweaks (avoid_negative_ts, aresample)
- `android/app/src/main/java/com/elite/iptv/dvr/ui/player/PlayerScreen.kt` — ExoPlayer config (LoadControl, LiveConfiguration)
- No other files should need changes for playback issues.

## What NOT to change
- `hls_list_size=75` — this was carefully chosen after the 5400→75 disaster. Don't increase it.
- `onPlayerError` listener — was removed intentionally. Do not add it back.
- `LiveConfiguration` min/max speed `1.0f/1.0f` — locked intentionally. Do not allow speed ramp.
</critical_context>

<current_state>
## File status
| File | State |
|------|-------|
| `core/dvr_manager.py` | Modified, not committed. `-bsf:v dump_extra` added. `avoid_negative_ts make_zero` still present. |
| `android/.../PlayerScreen.kt` | Modified, not committed. `onPlayerError` listener removed. `LiveConfiguration` locked 1.0x. |
| `android/.../ApiClient.kt` | Modified, not committed. `dvrPlaylistUrl()` added. |
| `android/app/build.gradle.kts` | Modified, not committed. `media3-exoplayer-hls` added. |

## Runtime state
- Python server: RUNNING (old code — `-bsf:v dump_extra` not yet active)
- Android emulator: RUNNING, app installed (latest APK with removed `onPlayerError` listener)
- APK: Built and installed. Current on emulator.

## Symptoms remaining after all fixes
1. Video plays faster than 1× — root cause not yet isolated
2. Green overlay flashes — fix deployed in code but server not restarted to apply
3. Periodic skipping/halting — may be emulator audio simulation artifact

## Next action
Restart Python server → retest → ffprobe segment PTS analysis → remove `avoid_negative_ts` if PTS clean.
</current_state>
