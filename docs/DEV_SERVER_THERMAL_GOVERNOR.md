# VisionXR • Host Development Server Thermal & CPU Governance Guide
> **IMPORTANT NOTE**: This document and host thermal optimizations are strictly for the **Host Development Node (dcim-2)** and are **EXCLUDED FROM CUSTOMER DISTRIBUTION PACKAGES**. Client production builds run standard enterprise frame rates and do not package this file.

---

## 1. Problem Statement
On development laptops or single-host edge nodes with limited active cooling, running dense optical flow (`cv2.calcOpticalFlowFarneback`) and background subtraction across 4 simultaneous camera channels at 10–30Hz drives CPU usage to ~170% and temperatures to ~83°C.

---

## 2. Solutions & Immediate Fixes for Dev Server

### Option A: Optimize VisionXR's AI Loop (Recommended)
* **Mechanism**: Throttle the heavy Farneback optical flow and background subtraction rate to run every 1–2 seconds (or on motion trigger) rather than 10–30 times every second.
* **Impact**:
  * VisionXR remains fully online on port `8022`.
  * Live CCTV RTSP/USB video feeds continue streaming smoothly at full FPS via MJPEG/WebSockets.
  * CPU utilization drops from ~170% to **~10–15%**.
  * Server temperature cools down from 83°C to **~50–55°C**.

### Option B: Temporarily Pause / Stop VisionXR
* **Mechanism**: Use the header `⏹️ STOP` button (`toggleEngineState()`) or stop the process:
  ```bash
  fuser -k 8022/tcp
  ```
* **Impact**: Instantly halts inference and video capture until actively testing.

---

## 3. Distribution Isolation Guarantee
* **Exclusion from Packaging**: The production packaging pipeline in `scripts/build_distribution_package.py`:
  1. Only copies `app`, `static`, and production `scripts`.
  2. Does **not** copy `docs/`.
  3. Recursively unlinks 100% of `.md` files in stage.
  4. Keeps client production packages running at standard enterprise surveillance specifications.
