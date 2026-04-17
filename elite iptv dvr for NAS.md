# ELITE IPTV DVR — NAS Deployment Notes

> **Note:** All NAS deployment plans, Stream Multiplexing, and roadmap items have been consolidated into [`ROADMAP.md`](./ROADMAP.md).
>
> See:
> - **Strategic Goal #4** — NAS Deployment (Synology DS1621xs+)
> - **NAS Deployment** section — Full deployment details
> - **Feature: Stream Multiplexing** — Multi-user stream sharing architecture
>
> This document is kept as a quick reference for the target NAS specs.

---

## Target Hardware: Synology DS1621xs+

- **CPU:** Quad-core Intel Xeon D-1527
- **RAM:** Up to 32GB DDR4 ECC
- **Network:** 10GbE
- **Platform:** Full Docker/Container Manager support
- **Users:** 3 primary (Edward, Kurt/Emmett, Dad) with Kodi devices in different locations

**Why this NAS:** Always-on operation with shared recordings accessible to all users simultaneously — unlike PC version where recordings are only available when the PC is running.
