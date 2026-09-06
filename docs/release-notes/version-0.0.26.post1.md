# Version 0.0.26.post1

## NetBox 4.7.0 GA compatibility release

Current backend-runtime pairing: netbox-proxbox 0.0.26.post1 <-> proxbox-api 0.0.20 <-> proxmox-sdk 0.0.13 <-> netbox-sdk 0.0.10. This netbox-sdk version is proxbox-api's REST dependency only and does not provide the semantic MCP bridge.

This post release packages the merged NetBox 4.7.0 GA compatibility contract
with a new monotonic package identity.

- Keeps the Emerson-owned Proxbox plugin backward-compatible with NetBox
  `4.5.8` through `4.6.x`.
- Admits official NetBox `4.7.0` GA in the stable tier and keeps pre-release
  builds advisory-only.
- Synchronizes the shared compatibility contract used by the Emerson-owned
  Proxbox-family plugins.
- Retains the normal migration, registration, and verification steps required
  for an easy upgrade from the previous compatible release.

| NetBox | netbox-proxbox | proxbox-api | netbox-sdk | proxmox-sdk |
|---|---|---|---|---|
| 4.5.8-4.7.0 GA | v0.0.26.post1 | v0.0.20 | v0.0.10 | v0.0.13 |
