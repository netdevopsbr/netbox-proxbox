# Version 0.0.25.post1

netbox-proxbox `0.0.25.post1` is the immutable post release for the official
NetBox `v4.7.0` GA compatibility contract. It pairs with `proxbox-api 0.0.20`,
`proxmox-sdk 0.0.13`, and the backend's REST dependency `netbox-sdk 0.0.10`.

Current backend-runtime pairing: netbox-proxbox 0.0.25.post1 <-> proxbox-api 0.0.20 <-> proxmox-sdk 0.0.13 <-> netbox-sdk 0.0.10. This netbox-sdk version is proxbox-api's REST dependency only and does not provide the semantic MCP bridge.

The plugin retains backward-compatible support for NetBox `4.5.8` through
`4.7.0`, including official NetBox `v4.7.0` GA at exact source commit
`5f06007e4c9bacc93ce17c1e645fc1143d60df3d`. The GA Docker evidence uses the
immutable
`netboxcommunity/netbox:v4.7.0-5.1.0@sha256:73a54ff279461170032b59a57a1930929965e3ba15c195af59f4b5f6d39a84a9`
image reference.

This post release gives the GA contract a new package identity after the
previous `0.0.25` artifact, which declared the old NetBox 4.6 ceiling. Upgrade
the plugin package and restart NetBox; no database migration is required for
the compatibility-contract change.

| NetBox | netbox-proxbox | proxbox-api | netbox-sdk | proxmox-sdk |
|---|---|---|---|---|
| 4.5.8-4.7.0 GA | v0.0.25.post1 | v0.0.20 | v0.0.10 | v0.0.13 |

Pre-release NetBox builds remain advisory-only and are not production support.
