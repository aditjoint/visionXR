package com.visionxr.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import java.io.File;

public class MainActivity extends Activity {
    private SurfaceView surfaceBack;
    private SurfaceView surfaceFront;
    private TextView tvHwid;
    private TextView tvAlertLog;
    private TextView tvTamperStatus;
    private Button btnCapture;
    private Button btnViewGallery;

    private DualCameraEngine cameraEngine;
    private SovereignStorageGuard storageGuard;
    private SurfaceHolder holderBack;
    private SurfaceHolder holderFront;
    private boolean backReady = false;
    private boolean frontReady = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        surfaceBack = (SurfaceView) findViewById(R.id.surface_back_camera);
        surfaceFront = (SurfaceView) findViewById(R.id.surface_front_camera);
        tvHwid = (TextView) findViewById(R.id.tv_hwid);
        tvAlertLog = (TextView) findViewById(R.id.tv_alert_log);
        tvTamperStatus = (TextView) findViewById(R.id.tv_tamper_status);
        btnCapture = (Button) findViewById(R.id.btn_trigger_evidence);
        btnViewGallery = (Button) findViewById(R.id.btn_view_evidence);

        storageGuard = new SovereignStorageGuard(this);
        cameraEngine = new DualCameraEngine(this);

        // Hardware Binding & Node Lock
        String hwid = MobileHardwareLock.getHardwareId(this);
        tvHwid.setText("HARDWARE NODE: " + hwid + " • AIR-GAPPED MOBILE CONTROLLER");

        // Media Self-Deletion from USB OTG Drive
        checkAndWipeUsbInstaller();

        setupSurfaces();

        // Capture Discrepancy Evidence Button
        btnCapture.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                // Save simulated evidence frames to sandboxed local storage
                byte[] mockBackFrame = new byte[1024 * 32];
                byte[] mockFrontFrame = new byte[1024 * 32];
                String p1 = storageGuard.saveDiscrepancyFrame("REAR", mockBackFrame);
                String p2 = storageGuard.saveDiscrepancyFrame("FRONT", mockFrontFrame);

                int count = storageGuard.getEvidenceCount();
                tvAlertLog.setText("✓ Dual-lens evidence sealed in sandboxed storage (" + count + " incidents recorded).");
                Toast.makeText(MainActivity.this, "📸 Dual Evidence Saved Locally (Isolated Storage)", Toast.LENGTH_SHORT).show();
            }
        });

        // Local Sandbox Gallery Viewer (Directly within app - No sharing)
        btnViewGallery.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showLocalSandboxEvidenceDialog();
            }
        });
    }

    private void setupSurfaces() {
        surfaceBack.getHolder().addCallback(new SurfaceHolder.Callback() {
            @Override
            public void surfaceCreated(SurfaceHolder holder) {
                holderBack = holder;
                backReady = true;
                checkAndStartDualCameras();
            }
            @Override
            public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {}
            @Override
            public void surfaceDestroyed(SurfaceHolder holder) {
                backReady = false;
            }
        });

        surfaceFront.getHolder().addCallback(new SurfaceHolder.Callback() {
            @Override
            public void surfaceCreated(SurfaceHolder holder) {
                holderFront = holder;
                frontReady = true;
                checkAndStartDualCameras();
            }
            @Override
            public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {}
            @Override
            public void surfaceDestroyed(SurfaceHolder holder) {
                frontReady = false;
            }
        });
    }

    private void checkAndStartDualCameras() {
        if (backReady && frontReady && cameraEngine != null) {
            cameraEngine.startDualCameras(holderBack.getSurface(), holderFront.getSurface());
            tvAlertLog.setText("✓ Active dual camera surveillance: Rear Lens + Front Lens streaming.");
        }
    }

    private void showLocalSandboxEvidenceDialog() {
        File[] files = storageGuard.listEvidenceFiles();
        StringBuilder sb = new StringBuilder();
        if (files == null || files.length == 0) {
            sb.append("No local discrepancy recordings in sandboxed storage.\n\n");
            sb.append("All captures will reside strictly in private storage with ZERO external transmission capability.");
        } else {
            sb.append("Total Sandboxed Recordings: ").append(files.length).append("\n\n");
            for (int i = 0; i < Math.min(files.length, 8); i++) {
                sb.append("• ").append(files[i].getName())
                  .append(" (").append(files[i].length() / 1024).append(" KB)\n");
            }
            sb.append("\n🔒 Storage Status: Sandboxed to app container. Inaccessible to all other phone apps.");
        }

        new AlertDialog.Builder(this)
            .setTitle("Sovereign Local Evidence Gallery")
            .setMessage(sb.toString())
            .setPositiveButton("Close", null)
            .show();
    }

    private void checkAndWipeUsbInstaller() {
        try {
            File storageDir = new File("/storage");
            if (storageDir.exists() && storageDir.isDirectory()) {
                File[] volumes = storageDir.listFiles();
                if (volumes != null) {
                    for (File vol : volumes) {
                        if (vol.isDirectory() && !vol.getName().equals("emulated") && !vol.getName().equals("self")) {
                            File usbApk = new File(vol, "VisionXR-Sovereign-Mobile.apk");
                            if (usbApk.exists()) {
                                usbApk.delete();
                            }
                            File usbLic = new File(vol, "developer.license");
                            if (usbLic.exists()) {
                                usbLic.delete();
                            }
                        }
                    }
                }
            }
        } catch (Exception ignored) {}
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (cameraEngine != null) {
            cameraEngine.stopDualCameras();
        }
    }
}
