# Browser Console Handoff

This document is the canonical `netbox-proxbox` implementation guide for the browser-console handoff. The plugin owns configuration and safe navigation from a NetBox virtual-machine page to NMS. It does not request a Proxmox ticket, open a WebSocket, relay console traffic, or authorize the resulting console session.

The NMS frontend owns the Console tab and noVNC/xterm clients. `nms-backend` owns caller-scoped object authorization and the one-time WebSocket relay. `proxbox-api` owns Proxmox `vncproxy`/`termproxy` ticket acquisition.

## Contents

1. [End-to-end role](#end-to-end-role)
2. [Configuration model and migration](#configuration-model-and-migration)
3. [URL validation](#url-validation)
4. [Settings UI and API](#settings-ui-and-api)
5. [Template extension lifecycle](#template-extension-lifecycle)
6. [Button visibility gates](#button-visibility-gates)
7. [Destination construction](#destination-construction)
8. [Rendered link security](#rendered-link-security)
9. [Authorization boundary](#authorization-boundary)
10. [Failure behavior and diagnosis](#failure-behavior-and-diagnosis)
11. [Regression coverage](#regression-coverage)
12. [Security invariants](#security-invariants)
13. [Change checklist](#change-checklist)

## End-to-end role

```text
NetBox VM detail page
    |
    | PluginTemplateExtension.buttons()
    | safe link containing only NMS origin, route family, and NetBox VM ID
    v
NMS guest detail page
    |
    | operator selects the Console tab
    | authenticated session request with complete Proxmox identity
    v
nms-backend one-time relay -> proxbox-api -> Proxmox
```

The current handoff opens one of these routes:

```text
https://<nms-origin>/virtualization/virtual-machines/<netbox-vm-pk>
https://<nms-origin>/virtualization/lxc-containers/<netbox-vm-pk>
```

It does **not** append `?tab=console`. The current NMS page does not consume that query parameter. The operator selects the Console tab after the guest detail page opens. Do not document or test automatic tab selection unless the NMS implementation is explicitly changed first.

## Configuration model and migration

`ProxboxPluginSettings.console_url` is the single configured browser-console destination. It is an optional `URLField` with an empty default. An empty value disables the handoff by hiding the button.

Migration `0084_proxboxpluginsettings_console_url.py` adds the field to the singleton settings model. The migration follows the repository's idempotent settings-field pattern so installations can upgrade across already-partial schemas safely.

The configured value must be the NMS **origin**, for example:

```text
https://nms.nmulti.cloud
```

Do not configure a guest route, API route, path prefix, query string, fragment, username, password, or Proxmox endpoint.

## URL validation

`netbox_proxbox/models/plugin_settings.py::validate_console_url()` is the shared model/API validator. It allows an empty value and otherwise requires:

- no whitespace anywhere;
- scheme exactly `https`;
- a hostname;
- no username or password;
- path empty or `/` only;
- no query string;
- no fragment; and
- a syntactically valid optional port.

Calling `parsed.port` is deliberate: `urlsplit()` alone can accept a malformed or out-of-range textual port and defer the error until the port property is read.

`ProxboxPluginSettings.clean()` validates the normalized persisted value. The settings form and API serializer repeat validation at their boundaries so unsafe input is rejected before save and partial API updates cannot preserve or introduce an invalid console origin.

The template path validates again at render time. `_console_base_url()` catches settings access errors, strips surrounding whitespace and a trailing slash, rejects embedded whitespace, forces port parsing, and repeats every origin-only rule. This defense means a legacy, manually corrupted, or partially migrated database value hides the link instead of rendering an unsafe destination.

## Settings UI and API

`ProxboxPluginSettingsForm.console_url` renders **Browser console URL** on the plugin settings page. `clean_console_url()` trims the value, removes trailing slashes, validates the HTTPS origin, and returns the normalized string. `ProxboxPluginSettingsView` loads the current value and writes the cleaned value in the settings transaction.

`ProxboxPluginSettingsSerializer` exposes `console_url` through the plugin settings API. Its object-level validation reads either the incoming field or, for partial updates, the existing instance value; it normalizes and calls `validate_console_url()`. This prevents an unrelated PATCH from bypassing the invariant on an existing invalid value.

Relevant files:

| File | Responsibility |
|---|---|
| `netbox_proxbox/migrations/0084_proxboxpluginsettings_console_url.py` | Adds the persistent optional setting. |
| `netbox_proxbox/models/plugin_settings.py` | Field definition, shared validator, and model validation. |
| `netbox_proxbox/forms/settings.py` | Settings-page field, normalization, and form validation. |
| `netbox_proxbox/views/settings.py` | Loads and persists the setting. |
| `netbox_proxbox/api/serializers/settings.py` | API exposure and full/partial-update validation. |
| `netbox_proxbox/templates/netbox_proxbox/settings.html` | Renders the field in the plugin settings UI. |

## Template extension lifecycle

`ProxboxVirtualMachineTemplateExtension` is registered for NetBox `virtualization.virtualmachine` detail pages. NetBox invokes its supported `buttons()` hook while composing the page actions.

`buttons()` builds the complete Proxbox action group in stable order:

1. create or edit Proxmox intent, when permitted;
2. Sync Now, when permitted and routable;
3. operational start/stop/snapshot/migrate controls, when permitted;
4. browser-console handoff, when all console gates pass.

The console implementation stays in `console_button()` so the visibility and route rules can be tested independently, but the method is called from `buttons()`. Rendering only a helper that NetBox never invokes would make the feature silently disappear even though unit tests of the helper passed.

## Button visibility gates

`console_button()` renders nothing unless every condition is true:

1. the detail object is a real NetBox `VirtualMachine`;
2. the requesting user has `permission_enqueue_proxbox_sync()`;
3. the VM has the authoritative reverse one-to-one `proxbox_sync_state` relation;
4. `proxmox_vm_id` on that state is a positive integer;
5. `proxmox_vm_type` normalizes to `qemu` or `lxc`;
6. the runtime-revalidated `console_url` is safe and non-empty; and
7. the VM has a primary key.

`_synced_console_vm_type()` intentionally uses typed sync state rather than legacy custom fields or a VM-name convention. The type determines only the NMS route family; it is not a Proxmox authorization decision.

The button does not require the related endpoint object to be currently enabled or `allow_writes=true`. Endpoint policy is mutable and can be stale on the already loaded NetBox page. The NMS/backend session path re-reads and authorizes current state. Suppressing the safe navigation link based on a stale relation would produce false negatives without improving authorization.

## Destination construction

After all gates pass, `console_button()` selects:

- `virtual-machines` for `vm_type="qemu"`; or
- `lxc-containers` for `vm_type="lxc"`.

It then appends the **NetBox VM primary key**:

```python
console_url = f"{console_base_url}/virtualization/{resource}/{obj.pk}"
```

The path does not include:

- the Proxmox host or port;
- endpoint ID;
- node name;
- Proxmox VMID;
- VNC/terminal ticket;
- TLS policy;
- authentication header or cookie; or
- a console stream token.

NMS resolves the remaining synchronized identity from its authorized data sources. `nms-backend` compares the complete caller-visible identity before it requests a Proxmox ticket.

## Rendered link security

`netbox_proxbox/templates/netbox_proxbox/inc/vm_console_button.html` renders an ordinary anchor:

```html
<a href="{{ console_url }}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
```

`target="_blank"` keeps the NetBox page available. `rel="noopener noreferrer"` prevents the new NMS tab from controlling the NetBox opener and avoids sending the NetBox page URL as a referrer. Django template autoescaping applies to `console_url`.

The button is labeled **Console** with the standard `mdi-console` icon. The template extension joins only HTML rendered from plugin-owned autoescaped templates before marking the final combined fragment safe.

## Authorization boundary

The plugin's permission and sync-state checks decide whether to display a navigation convenience. They do not grant console access.

After navigation, NMS requires an authenticated user and a complete guest identity. `nms-backend` uses that caller's bearer token to read the exact NetBox VM and exactly one Proxbox sync-state row, then compares guest ID, endpoint, VMID, node, and workload type. It creates an origin-bound, single-use relay token only after those checks pass.

Never place a Proxmox ticket or endpoint credential in this plugin's page, URL, context, template, model, or log. The browser handoff is intentionally credential-free.

## Failure behavior and diagnosis

| Symptom | Inspect |
|---|---|
| Console button absent everywhere | `console_url` is empty/invalid, the settings migration is absent, or the user lacks `permission_enqueue_proxbox_sync()`. |
| Button absent for one VM | Missing `proxbox_sync_state`, invalid/missing `proxmox_vm_id`, unsupported/missing `proxmox_vm_type`, or unsaved VM. |
| Button opens QEMU route for a container or the reverse | Authoritative sync-state `proxmox_vm_type`; do not infer from the VM name. |
| Button opens the NMS detail page but not the Console tab | Expected current behavior; the handoff has no `?tab=console`, and the operator selects Console. |
| NMS detail page opens but console is unavailable | Diagnose NMS identity resolution and backend object authorization; the NetBox link is not proof of session authorization. |
| Browser console opens and then fails or stays gray | Diagnose `nms`, `nms-backend`, and `proxbox-api`; this plugin does not handle tickets or transport. |

## Regression coverage

`tests/test_template_content_sync_now.py` covers the console handoff together with the supported NetBox `buttons()` composition:

- QEMU and LXC route-family selection;
- use of the NetBox VM primary key;
- absence of Proxmox endpoint data in the URL;
- composition into `buttons()`;
- unsafe, malformed, whitespace-containing, and empty origins;
- missing or invalid sync state;
- permission gating; and
- deferral of mutable endpoint policy to the management console.

Plugin-settings tests cover model, form, view, serializer, and migration behavior for `console_url`. Run the focused tests with the repository's normal Django test environment, including:

```bash
uv run pytest -q tests/test_template_content_sync_now.py tests/test_settings_view_encryption.py tests/test_settings_view_hardware_discovery.py tests/test_migration_graph_single_leaf.py
```

## Security invariants

- Store only an optional HTTPS management origin, never a guest-specific URL or credential.
- Validate the origin in the model, form, API serializer, and again at render time.
- Hide the button on any invalid, ambiguous, unavailable, or incomplete local state.
- Use typed `proxbox_sync_state` and the NetBox VM primary key.
- Keep the handoff URL free of Proxmox topology, tickets, authentication, and TLS policy.
- Keep `target="_blank"` paired with `rel="noopener noreferrer"`.
- Treat the button permission as display gating, not console authorization.
- Leave current endpoint policy and final object authorization to NMS/backend.
- Do not claim automatic Console-tab selection while the NMS route does not implement it.

## Change checklist

When the handoff changes:

1. update this guide, `README.md`, and the related root/package/model/form/API/migration/test LLM files;
2. confirm the current NMS route and tab-selection behavior before documenting it;
3. retain origin-only validation at every input and render boundary;
4. test both QEMU and LXC destinations and every hide condition;
5. verify the URL contains only the management origin, route family, and NetBox VM ID;
6. keep button composition in NetBox's supported `buttons()` hook;
7. run focused tests plus the repository's normal documentation and quality gates; and
8. coordinate cross-service behavior changes with `nms`, `nms-backend`, and `proxbox-api`.
