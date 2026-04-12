# Server-Side Stream Normalization Fallback

## Why this exists

If Android TV playback remains unreliable even when the PC is doing the heavy lifting, the next fallback is to make the PC do one more job:

- Receive the original IPTV stream
- Normalize it into a stable output format
- Feed Android TV a stream profile that hardware decoders usually handle well

This is not the first-choice architecture. It is the "make the stream boring and predictable" option when client-side tuning is not enough.

## Core idea

Instead of exposing the raw provider stream directly to the TV, the PC becomes a media gateway:

1. **Input**: provider channel URL / live stream
2. **Normalize**: remux or transcode as needed
3. **Output**: a single Android-friendly stream profile
4. **Playback**: Android TV consumes only the normalized output

The goal is to reduce the number of variables the TV has to tolerate.

## Recommended output profile

For maximum compatibility, target:

- **Container**: HLS
- **Video**: H.264 / AVC
- **Audio**: AAC-LC
- **Frame rate**: stable, ideally constant
- **Keyframes**: regular and predictable
- **Segments**: short, fixed duration
- **Audio passthrough**: avoid it unless you are sure the TV supports it

This profile is usually safer than passing through odd TS streams, exotic codecs, or inconsistent timestamps.

## Two operating modes

### 1. Remux mode

Use remuxing when the source is already acceptable:

- Source video is already H.264
- Source audio is already AAC
- Only the container / segmentation needs cleanup

Benefits:

- Low CPU cost
- Lower latency
- Better quality retention

### 2. Transcode mode

Use transcoding when the source is problematic:

- HEVC / H.265
- MPEG-TS weirdness
- AC3 / EAC3 audio issues
- Timestamp discontinuities
- Broken GOP structure
- Streams that trigger decoder resets on Android TV

Benefits:

- Highest compatibility
- More consistent playback on weak or picky TVs

Tradeoffs:

- Higher CPU / GPU cost
- More latency
- Potential quality loss if configured poorly

## Decision tree

A practical decision tree could look like this:

1. **Try pass-through HLS**
   - If the source already behaves well, just repack it cleanly
2. **If the TV stutters, remux to a strict profile**
   - Normalize timestamps
   - Use predictable HLS segmentation
3. **If the TV still fails, transcode to H.264 + AAC**
   - Favor compatibility over efficiency
4. **Keep a per-channel override list**
   - Some channels can pass through
   - Problem channels get forced into normalize/transcode mode

## Suggested server-side pipeline

### Input handling

- Open the source stream on the PC
- Probe codec, audio type, and container behavior
- Detect whether the stream is already Android-friendly

### Normalization step

If the source is good enough:

- Remux to HLS
- Keep codec intact
- Clean up timestamps and segment boundaries

If the source is not good enough:

- Transcode video to H.264
- Transcode audio to AAC-LC
- Emit HLS segments with stable cadence

### Output step

Expose a local HTTP endpoint for Android TV, such as:

- `/api/stream/live?channel_id=...`
- `/api/stream/hls?channel_id=...`

The client should only ever see the normalized stream.

## Why this can help Android TV

Android TV playback issues often come from decoder and renderer sensitivity, not raw bitrate alone.

A server-side normalization layer can hide problems like:

- Timestamp drift
- Bad segment boundaries
- Codec profile mismatch
- Audio codec incompatibility
- Decoder resets on live edge transitions
- Variable frame pacing

That means the TV gets a stream that is more likely to behave like a regular broadcast feed instead of a raw internet feed.

## Risks and costs

This approach is powerful, but it is not free:

- **CPU/GPU load** goes up
- **Latency** can increase
- **Channel switching** can get slower
- **Quality** can drop if transcode settings are too aggressive
- **Operational complexity** increases because each channel may need a different treatment

## Best-fit strategy

The best version of this idea is not "transcode everything all the time".

A smarter strategy is:

- **Pass through** streams that are already clean
- **Remux** streams that only need packaging cleanup
- **Transcode** only the channels that break Android TV playback

That gives you a compatibility fallback without paying the full transcode cost for every channel.

## Fit with the current architecture

This idea matches the current PC-brain / thin-client direction:

- PC keeps credentials and stream handling
- Android TV remains a simple player
- The TV does not need to understand provider-specific quirks
- The server becomes the compatibility layer

If the current direct-play approach still fails, this is the next architecture to try.

## Implementation notes to explore later

Possible next steps if this becomes real:

- Add a per-channel playback mode setting
- Add FFmpeg probing before starting playback
- Create a normalized HLS endpoint for Android TV
- Add hardware encoding support where available
- Cache per-channel codec decisions so probing is not repeated constantly
- Log which streams required remux vs transcode so the behavior can be tuned over time

## Success criteria

This idea is worth pursuing if it produces:

- Fewer decoder stalls
- Fewer audio sync issues
- Fewer green flashes / artifact bursts
- Faster recovery after channel changes
- More consistent playback across different Android TV devices

If the client still struggles after normalization, the issue is probably deeper in device-specific decoder behavior or stream quality upstream.
