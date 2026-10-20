# ADAM Consult • VisionXR Sovereign Command Center
## Comprehensive Button & Functionality Reference Manual

This document details **every interactive button, control, and functional trigger** available in the VisionXR AI Command Center. It provides operators and administrators with complete operational clarity on purpose, behavior, security clearance, and downstream impact.

---

## 1. Top Header: Cluster 1 — Master Control & Identity

Located in the top-left navigation ribbon. Provides primary engine states, operator identity, credentials, and subsystem health.

| Button Label | Action Trigger / Function | Required Clearance | Description & Operational Impact |
| :--- | :--- | :--- | :--- |
| **`⏹️ STOP SURVEILLANCE`** / **`▶️ START SURVEILLANCE`** | `toggleEngineState()` | `SUPER_ADMIN` (L4) | **Master Optical Engine Switch.** Toggles the underlying AI inference worker and frame capture loops. When stopped, all video acquisition halts, AI tracking pauses, and the system transitions to safe sleep. |
| **`🔔 SILENCE`** | `silenceAllAlarms()` | `OPERATOR` (L2+) | **Audible Mute & Alarm Clear.** Instantly silences all active sirens, warning buzzers, and audio synthesized alarms without clearing visual telemetry or stopping recording. |
| **`🔇 MUTED`** / **`🔊 AUDIO ON`** | `toggleAudioMute()` | All Users | **Audio Subsystem Toggle.** Enables or suspends the browser WebAudio synthesizer. Prevents audible chimes from disturbing the control room during continuous monitoring. |
| **`🛡️ Sovereign Commander Adity (SUPER_ADMIN L4)`** | `openAdminLoginModal()` | All Users | **Identity & Profile Drawer.** Displays the currently logged-in operator, role, and clearance level. Clicking opens the Admin Identity modal showing system uptime, engine state, and active token hash. |
| **`👥 USERS & ACCESS`** | `openUserGovernanceModal()` | `SUPER_ADMIN` (L4) | **User Management Portal.** Opens the User Governance modal to list active operators, add new users, review the RBAC Clearance Matrix, and manage role assignments. |
| **`🔑 PASSWORDS`** | `openResetPasswordModal()` | All Users | **Cryptographic Password Reset.** Opens the 6-digit cryptographic password reset modal, supporting self-service resets via emergency reset codes or administrative overrides. |
| **`⚙️ RULES`** | `openSafetyRulesModal()` | `SUPER_ADMIN` (L4) | **Safety Rules & Thresholds Engine.** Opens the parameter configuration modal for worker dwell time, Red Zone tolerance, PPE enforcement toggles, forklift speed limits, and curfew schedules. |
| **`🔄 RESET CAMERAS`** | `triggerSubsystemReset()` | `SUPER_ADMIN` (L4) | **Hardware Subsystem Auto-Heal & Re-sync.** Performs a zero-data-loss reset of all V4L2 USB and RTSP video captures. Releases driver file descriptors, re-detects physical devices, and brings all feeds back online without restarting the server or losing logs. |
| **`⚡ BREAK-GLASS`** | `openBreakGlassModal()` | `OPERATOR` (L2+) | **Emergency Elevation Trigger.** Opens the Break-Glass emergency modal to elevate temporary clearance to L4 for 15 minutes during critical incidents (fire, toxic leak, rescue). |
| **`🔒 LOGOUT`** | `handleLogout()` | All Users | **Session Termination.** Revokes the cryptographic session token in `localStorage`, audits the logout event in the tamper-evident ledger, and redirects to the authentication screen. |

---

## 2. Top Header: Cluster 2 — Rapid SecOps & Interlocks

Located in the center-top header. Designed for high-urgency operational interventions.

| Button Label | Action Trigger / Function | Required Clearance | Description & Operational Impact |
| :--- | :--- | :--- | :--- |
| **`🔔 SIREN`** | `toggleSiren()` | `OPERATOR` (L2+) | **Manual Facility Siren Toggle.** Manually activates or deactivates the control room emergency warning siren. Emits visual pulses across the dashboard. |
| **`🛡️ LOCKDOWN`** | `toggleLockdown()` | `SUPER_ADMIN` (L4) | **Facility Isolation Interlock.** Engages physical containment lockouts, seals perimeter entryways, trips SCADA relays, and tags all subsequent tracking entries as critical lockdown alerts. |
| **`👁️ BLUR`** | `togglePrivacy()` | All Users | **DPDP / GDPR Facial Privacy Shield.** Toggles client-side and server-side facial mosaic obfuscation. Replaces recognized worker faces with privacy pixelation blocks to ensure privacy law compliance. |
| **`📲 WHATSAPP`** | `testWhatsApp()` | `SUPER_ADMIN` (L4) | **Emergency Dispatch Integration Test.** Sends an instant cryptographic test alert and snapshot link to the pre-configured supervisor WhatsApp target (`+91-8779639965`). |

---

## 3. Top Header: Cluster 3 — Infrastructure & Hardware Governance

Located in the top-right header cluster. Controls hardware isolation, networking, and forensic audit.

| Button Label | Action Trigger / Function | Required Clearance | Description & Operational Impact |
| :--- | :--- | :--- | :--- |
| **`🌐 IP GUARD`** | `openIPModal()` | `SUPER_ADMIN` (L4) | **Sovereign IP Whitelist Shield.** Opens the IP Access Control list. Restricts dashboard access strictly to whitelisted corporate IPv4/IPv6 addresses. |
| **`📡 SNIFFER`** | `openSnifferModal()` | `SUPER_ADMIN` (L4) | **Local Subnet & ONVIF Device Discovery.** Scans local physical network interfaces (eth0, wlan0) for live IP cameras, RTSP streams, and ONVIF profile endpoints. |
| **`📜 AUDIT`** | `openAuditModal()` | `SECURITY_AUDITOR` (L3+) | **Cryptographic Audit Ledger.** Displays the SHA-256 chained transaction ledger of every system event, login, policy change, and alarm. Includes the integrity validation tool. |
| **`💾 NVME DISK`** | `openStorageModal()` | `SUPER_ADMIN` (L4) | **Storage Governor & Evidence Pruner.** Inspects NVMe partition utilization, snapshot allocations, video buffer sizes, and allows custom MB quotas and manual pruning. |
| **`🔑 LICENSE`** *(Developer Machine Only)* | `openLicenseModal()` | `SUPER_ADMIN` (L4) | **Developer License & AI Pipeline Manager.** Assigns AI capabilities to specific camera channels and sets node limits. **CRITICAL:** Strictly omitted and purged from all client distribution packages. |
| **`💾 USB EXPORT`** *(Developer Machine Only)* | `triggerUSBBuild()` | `SUPER_ADMIN` (L4) | **USB Client Distribution Builder.** Compiles a hardened, Cythonized, hardware-locked, and sanitized installer package directly to an attached USB drive. **CRITICAL:** Strictly omitted and purged from all client distribution packages. |

---

## 4. Left Sidebar: Channels & Disaster Radar

Located along the left panel. Handles channel focus, provisioning, simulation testing, and layout folding.

| Button Label | Action Trigger / Function | Required Clearance | Description & Operational Impact |
| :--- | :--- | :--- | :--- |
| **`◀ CHANNELS`** | `toggleLeftSidebar()` | All Users | **Left Sidebar Instant Collapse.** Instantly hides/unhides the left channel navigation bar via direct DOM inline style toggling, maximizing video viewport space. |
| **Channel Pill Buttons** (`CAM_01`, `CAM_02`, etc.) | `focusCamera(cam_id)` | All Users | **Ultra-Compact Channel Focus.** 26px sleek channel buttons with real-time green/red pulsating live status dot, channel name, and live FPS telemetry. |
| **`➕ ADD CAMERA FEED`** | `openProvisionModal()` | `SUPER_ADMIN` (L4) | **New Stream Ingestion.** Launches the camera wizard to connect a new USB V4L2 device, industrial RTSP stream, ONVIF dome, or mobile web feed. |
| **`✕ RETIRE`** | `openDeprovisionModal()` | `SUPER_ADMIN` (L4) | **Camera Deprovisioning.** Safely tears down and unbinds an active camera channel. Requires mandatory governance justification logged to the audit ledger. |
| **`🔄 RE-SYNC CAMERA SUBSYSTEM`** | `triggerSubsystemReset()` | `SUPER_ADMIN` (L4) | **Secondary Subsystem Re-sync.** Identical to the header reset button; accessible directly within the channels panel. |
| **`☣️ Acid Fuming Spill`** | `triggerDisaster('ACID_FUMING_SPILL')` | `SUPER_ADMIN` (L4) | **Emergency Drill Trigger: Acid Spill.** Simulates an exothermic corrosive liquid spill event, trips ESD interlocks, and tests hazmat dispatch pipelines. |
| **`💨 Toxic Gas Cloud Plume`** | `triggerDisaster('TOXIC_GAS_PLUME')` | `SUPER_ADMIN` (L4) | **Emergency Drill Trigger: Toxic Gas.** Tests optical gas dispersion models, downwind trajectory vectors, and safety sirens. |
| **`🌊 Main Pipe Burst Flood`** | `triggerDisaster('PIPE_BURST_FLOOD')` | `SUPER_ADMIN` (L4) | **Emergency Drill Trigger: Pipe Burst.** Simulates industrial high-pressure water deluge and electrical arc-flash ground fault warnings. |
| **`🔥 Battery Thermal Runaway`** | `triggerDisaster('THERMAL_RUNAWAY')` | `SUPER_ADMIN` (L4) | **Emergency Drill Trigger: BESS Fire.** Tests lithium-ion thermal runaway escalation, automatic sirens, and emergency suppression calls. |

---

## 5. Center Stage: Viewport Layout & Spatial Tri-Zone Editor

Located immediately above the live camera video grid.

| Button Label | Action Trigger / Function | Required Clearance | Description & Operational Impact |
| :--- | :--- | :--- | :--- |
| **`➕ ADD FEED`** | `openProvisionModal()` | `SUPER_ADMIN` (L4) | **Direct Grid Ingestion Trigger.** Quick-access feed provisioning button located directly on the main stage toolbar. |
| **`🔄 RESET CAMERAS`** | `triggerSubsystemReset()` | `SUPER_ADMIN` (L4) | **Direct Viewport Hardware Re-sync.** Re-initializes all video capture handles right above the active monitors. |
| **`1x1 FOCUS`** | `setLayout('grid-1x1')` | All Users | **Full Single-Feed View.** Expands the currently focused camera to occupy 100% of the viewport for detailed inspection. |
| **`2x2 QUAD (4)`** | `setLayout('grid-2x2')` | All Users | **Standard 4-Channel Matrix.** Divides the display into an industrial 4-quadrant monitoring grid. |
| **`3x3 (9)`** | `setLayout('grid-3x3')` | All Users | **High-Density 9-Channel Matrix.** Configures the display for multi-sector wide-area facility overview. |
| **`AUTO GRID`** | `setLayout('grid-auto')` | All Users | **Dynamic Tile Allocation.** Automatically scales grid dimensions to fit all currently provisioned cameras optimally. |
| **`📐 EDIT TRI-ZONES`** | `toggleZoneEditor()` | `OPERATOR` (L2+) | **Spatial Polygon Editor Toggle.** Enables the interactive canvas overlay allowing operators to draw and calibrate polygon coordinates on live camera frames. |
| **`🟢 GREEN`** | `setDrawType('green')` | `OPERATOR` (L2+) | **Safe Corridor Tool.** Sets active drawing mode to Green Safe Zones (normal worker walkways; no loitering alarms). |
| **`🟡 AMBER`** | `setDrawType('amber')` | `OPERATOR` (L2+) | **Cautionary Buffer Tool.** Sets active drawing mode to Amber Caution Zones (buffers surrounding heavy machinery; enforces max dwell time). |
| **`🔴 RED`** | `setDrawType('red')` | `OPERATOR` (L2+) | **Zero-Tolerance Hazard Tool.** Sets active drawing mode to Red Hazard Zones (electrical switchgear, robotic cells; zero entry tolerance). |
| **`💾 SAVE`** | `saveCurrentZone()` | `OPERATOR` (L2+) | **Polygon Persistence.** Commits the drawn polygon points to NVMe storage (`data/zones.json`) for the focused camera. |
| **`🧹 CLEAR`** | `clearAllZones()` | `OPERATOR` (L2+) | **Purge Zones.** Deletes all spatial zones drawn on the currently selected camera feed. |

### In-Feed Floating Micro-Action Bar (Inside Each Camera Feed)
Located along the top-right corner of each live video tile in an ultra-compact 20px translucent bar:

| Button Icon | Action Trigger | Required Clearance | Description & Operational Impact |
| :--- | :--- | :--- | :--- |
| **`[🔍]`** | `soloCamera(camId)` | All Users | **Solo / 1x1 Toggle.** Instantly isolates this camera into full-stage 1x1 focus mode; clicking again returns to the standard grid view. |
| **`[⚙]`** | `openCameraConfig(camId)` | `SUPER_ADMIN` (L4) | **Channel Config.** Opens settings for RTSP source, pipeline toggles, and frame rate. |
| **`[📸]`** | `takeCameraSnapshot(camId)` | All Users | **Forensic Snapshot.** Captures raw video frame, applies watermark & timestamp, writes to storage, and generates SHA-256 evidence record. |
| **`[✕]`** | `retireCamera(camId)` | `SUPER_ADMIN` (L4) | **Retire Channel.** Gracefully deprovisions the camera feed and releases hardware handles. |

---

## 6. Right Sidebar: Anomaly & Event Bus Actions

Located on the right telemetry and alert rail.

| Button Label | Action Trigger / Function | Required Clearance | Description & Operational Impact |
| :--- | :--- | :--- | :--- |
| **`EVENTS ▶`** | `toggleRightSidebar()` | All Users | **Right Sidebar Instant Collapse.** Instantly hides/unhides the incident event stream and telemetry rail to free up display space. |
| **Telemetry Pills** (`LATENCY`, `PIPELINE`, etc.) | N/A (Display) | All Users | **Ultra-Compact Telemetry.** 24px pills reporting system load, optical latency, GPU/CPU utilization, and active pipeline health. |
| **`📷 IMAGE`** | `viewAlertMedia(alert_id, 'snapshot')` | All Users | **Cryptographic Snapshot Viewer.** Opens the full-resolution high-definition photographic frame captured at the exact millisecond the violation occurred, verified with its SHA-256 seal. |
| **`🎬 VIDEO`** | `viewAlertMedia(alert_id, 'video')` | All Users | **Rolling Buffer Clip Player.** Plays the 5-second tamper-sealed MP4 video clip recorded from the rolling buffer, capturing the moments leading up to and during the incident. |
| **`ACK`** | `ackAlert(alertId)` | `OPERATOR` (L2+) | **Acknowledge Alert.** Records operator acknowledgment in the audit log, silences the individual card's pulse, and marks the event as reviewed. |

---

## 7. Modal Windows & Administrative Action Buttons

### A. Break-Glass Modal
- **`✕` / `Cancel`**: Closes the dialog without altering clearance.
- **`⚡ Authorize Elevation (15 Mins)`**: Commits emergency clearance elevation to L4, logs the justification to the ledger, and sets an auto-expire timer.

### B. IP Guard Modal
- **`+ Add Whitelist IP`**: Adds the specified IPv4/IPv6 address or subnet mask to `data/whitelist.json`.
- **`✕ Remove`** (per row): Removes the specified IP address from the whitelist.
- **`Close`**: Exits the IP guard configuration dialog.

### C. Network Sniffer Modal
- **`🔄 Rescan Subnet`**: Triggers a live ARP/ICMP broadcast scan on network interfaces to discover active IP surveillance devices.
- **`Close`**: Closes the sniffer output view.

### D. Audit Ledger Modal
- **`🛡️ Verify SHA-256 Integrity`**: Traverses the cryptographic hash chain from genesis to the latest block. Verifies that no entries have been modified or deleted.
- **`Close`**: Exits the ledger viewer.

### E. Add Camera Provisioning Modal
- **`📷 USB / V4L2 Device`**: Auto-populates camera fields with USB defaults (`/dev/videoX`).
- **`🌐 Industrial RTSP IP Dome`**: Auto-populates camera fields with RTSP defaults (`rtsp://192.168.1.X:554/live`).
- **`📱 Mobile / Web Stream`**: Auto-populates camera fields with HTTP stream defaults (`http://192.168.1.X:8080/video`).
- **`⚡ Elevate Quota (+4)`**: Temporarily expands licensed camera slots under Super Admin governance.
- **`Authorize & Provision Feed`**: Validates input, starts the OpenCV ingestion stream, and appends the tile to the live grid.
- **`Cancel` / `✕`**: Discards feed configuration.

### F. Retire (Deprovision) Modal
- **`Confirm Deprovision`**: Permanently unbinds the selected camera, releases hardware file handles, and logs justification to the audit ledger.
- **`Cancel` / `✕`**: Aborts deprovisioning.

### G. Storage Governor Modal
- **`Update Quota`**: Updates the NVMe partition storage ceiling (e.g. 100 MB or 500 MB).
- **`🧹 Prune Old Evidence Now`**: Forces immediate purging of the oldest non-critical snapshots and MP4 clips to free disk space.
- **`Close`**: Exits storage management.

### H. Safety Rules Modal
- **`💾 Save & Deploy Super Admin Parameters`**: Saves customized dwell thresholds, speed limits, curfew hours, and PPE toggles to `data/safety_rules.json`.
- **`↺ Reset Factory Defaults`**: Reverts all thresholds back to Sovereign certified industrial baselines.
- **`Cancel` / `✕`**: Discards unsaved modifications.

### I. Licensing & Workloads Modal
- **`🚀 Set Quota`**: Updates maximum camera channels allowed on the current hardware node.
- **`💾 Save Tasks for Selected Camera`**: Commits enabled AI pipelines (PPE, Tri-Zone, Collision, Acoustic) for the chosen camera.
- **`Activate`**: Validates and installs a newly purchased commercial license token.
- **`Close`**: Exits licensing.

### J. User Governance Modal
- **`👥 User Accounts`**: Displays active users, roles, clearances, and creation dates.
- **`➕ Add / Provision User`**: Opens operator registration form with clearance assignment.
- **`🔑 Password Reset Portal`**: Switches to password change and code dispatch tools.
- **`🛡️ Clearance Matrix (RBAC)`**: Displays complete table of permissions across roles (SuperAdmin, Admin, Auditor, Operator, Viewer).
- **`✓ Provision & Register User`**: Validates credentials and creates new operator account.
- **`💾 Save New Password`**: Super Admin direct password override button.
- **`📩 Get Code`**: Generates a 6-digit cryptographic verification code for secure self-service password reset.
- **`✓ Verify & Reset Password`**: Verifies code and commits new password.
- **`Close`**: Exits User Governance.

---

## 8. Anti-Piracy & Protection Rules Governing Buttons
- All UI buttons, labels, and badges are protected under **Sovereign IP Guard**:
  - Text and button labels cannot be selected or copied via `Ctrl+A` or `Ctrl+C`.
  - Right-click context menus are locked across all buttons.
  - Form fields (`input`, `textarea`) remain fully functional for typing and credential entry.
