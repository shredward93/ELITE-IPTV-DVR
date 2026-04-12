---
description: High-performance Android TV EPG guide rewrite
---

# High-Performance Android TV EPG Guide

This workflow is the implementation blueprint for rewriting the guide from top to bottom while keeping the current UI behavior and playback flow intact.

## Goal

Make the guide feel instant on Android TV:

- Guide screen should open with data already present or become ready in the background.
- Category hover/focus should instantly reveal preloaded channels and listings.
- No category click should be required to load rows.
- No XML parsing, guide downloading, or network fan-out should happen on the UI thread.
- Preserve current UI layout, navigation style, and playback actions.

## Architecture rules

- Treat XMLTV as an ingestion format only.
- Normalize guide data into indexed, query-friendly structures before it reaches the guide UI.
- Keep a memory-backed guide map for fast lookups.
- Cache guide payloads on disk so restarts remain fast.
- Load guide data in the background when the app starts, not when the user first focuses a category.
- Hover/focus should only change visible state; it must not trigger reloads.

## Data model rules

- Channels must remain keyed by provider `id` / `stream_id` and matched by `epg_channel_id` where available.
- Guide listings must be stored as epoch timestamps or pre-normalized strings that are fast to compare.
- Prefer pre-grouped maps:
  - `categoryId -> channels`
  - `channelId / epg_channel_id -> listings`
  - `categoryId -> guide view model rows`
- Preserve existing API response shapes where possible so the Android client does not need a large compatibility rewrite.

## Rewrite phases

### Phase 1: Backend guide source

1. Ensure the backend can build the whole guide bundle from cached guide data.
2. Avoid repeated provider calls per category or per channel in guide rendering paths.
3. Add or expand a consolidated guide endpoint that can serve all guide data needed by Android in one pass.
4. Keep the disk cache and in-memory lookup tables warm across requests.

### Phase 2: Android startup prefetch

1. Start guide prefetch as soon as the app has credentials and the PC backend is reachable.
2. Fetch the guide bundle before the user opens the guide screen.
3. Store all categories and all category channel lists in memory.
4. Keep a progress indicator only as a fallback, not as the primary guide experience.

### Phase 3: Guide screen behavior

1. The guide screen must render instantly from already-loaded state.
2. Category focus/hover should only switch the visible category.
3. Category selection must not fire network requests.
4. Rows should update from in-memory data only.
5. Keep existing actions intact:
   - back
   - play live
   - schedule record
   - browse categories

### Phase 4: UI performance cleanup

1. Remove nested lazy containers where a fixed row/column layout is sufficient.
2. Avoid per-cell focus handlers if row-level navigation can do the same job.
3. Avoid animated scroll calls unless there is a strong UX reason.
4. Use stable keys and content types for list recycling.
5. Limit recompositions by deriving visible rows from memoized data.

### Phase 5: Verification

1. Confirm guide opens with populated data after startup.
2. Confirm category hover changes the rows immediately.
3. Confirm guide navigation remains responsive on D-pad.
4. Confirm no guide reload happens on every hover or focus event.
5. Confirm existing playback and recording actions still work.

## Implementation expectations

- Do not change the visible guide layout unless required for performance.
- Do not remove any current guide features.
- Keep guide categories, channel rows, and play-live behavior intact.
- Favor internal data-flow changes over UI redesign.
- If a feature can be made instantaneous with cached state, do that before introducing a new screen or interaction.

## Done means

- Guide screen opens fast.
- Categories are already loaded or become available in the background.
- Hovering a category reveals its channels immediately.
- The UI stays responsive with D-pad navigation.
- No per-focus reloads, no XML parsing in UI, and no blocking fetches on the main thread.
