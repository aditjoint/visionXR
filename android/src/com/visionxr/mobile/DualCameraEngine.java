package com.visionxr.mobile;

import android.content.Context;
import android.hardware.camera2.*;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.Log;
import android.view.Surface;
import java.util.Collections;

public class DualCameraEngine {
    private static final String TAG = "VXR.DualCamera";
    private final Context context;
    private final CameraManager cameraManager;
    private CameraDevice backCameraDevice;
    private CameraDevice frontCameraDevice;
    private HandlerThread cameraThread;
    private Handler cameraHandler;

    public DualCameraEngine(Context ctx) {
        this.context = ctx;
        this.cameraManager = (CameraManager) ctx.getSystemService(Context.CAMERA_SERVICE);
    }

    public void startDualCameras(final Surface backSurface, final Surface frontSurface) {
        cameraThread = new HandlerThread("DualCameraWorker");
        cameraThread.start();
        cameraHandler = new Handler(cameraThread.getLooper());

        try {
            for (String cameraId : cameraManager.getCameraIdList()) {
                CameraCharacteristics characteristics = cameraManager.getCameraCharacteristics(cameraId);
                Integer facing = characteristics.get(CameraCharacteristics.LENS_FACING);

                // Open Rear Camera (Facing Back)
                if (facing != null && facing == CameraCharacteristics.LENS_FACING_BACK && backSurface != null) {
                    cameraManager.openCamera(cameraId, new CameraDevice.StateCallback() {
                        @Override
                        public void onOpened(CameraDevice camera) {
                            backCameraDevice = camera;
                            startCaptureSession(camera, backSurface);
                        }
                        @Override
                        public void onDisconnected(CameraDevice camera) { camera.close(); }
                        @Override
                        public void onError(CameraDevice camera, int error) { camera.close(); }
                    }, cameraHandler);
                }

                // Open Front Camera (Facing Front)
                if (facing != null && facing == CameraCharacteristics.LENS_FACING_FRONT && frontSurface != null) {
                    cameraManager.openCamera(cameraId, new CameraDevice.StateCallback() {
                        @Override
                        public void onOpened(CameraDevice camera) {
                            frontCameraDevice = camera;
                            startCaptureSession(camera, frontSurface);
                        }
                        @Override
                        public void onDisconnected(CameraDevice camera) { camera.close(); }
                        @Override
                        public void onError(CameraDevice camera, int error) { camera.close(); }
                    }, cameraHandler);
                }
            }
        } catch (SecurityException | CameraAccessException e) {
            Log.e(TAG, "Dual Camera initialization note: " + e.getMessage());
        }
    }

    private void startCaptureSession(final CameraDevice camera, final Surface surface) {
        try {
            camera.createCaptureSession(Collections.singletonList(surface),
                new CameraCaptureSession.StateCallback() {
                    @Override
                    public void onConfigured(CameraCaptureSession session) {
                        try {
                            CaptureRequest.Builder builder = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
                            builder.addTarget(surface);
                            session.setRepeatingRequest(builder.build(), null, cameraHandler);
                        } catch (CameraAccessException e) {
                            Log.e(TAG, "Capture error: " + e.getMessage());
                        }
                    }
                    @Override
                    public void onConfigureFailed(CameraCaptureSession session) {}
                }, cameraHandler);
        } catch (CameraAccessException e) {
            Log.e(TAG, "Session creation failed: " + e.getMessage());
        }
    }

    public void stopDualCameras() {
        if (backCameraDevice != null) {
            backCameraDevice.close();
            backCameraDevice = null;
        }
        if (frontCameraDevice != null) {
            frontCameraDevice.close();
            frontCameraDevice = null;
        }
        if (cameraThread != null) {
            cameraThread.quitSafely();
            cameraThread = null;
        }
    }
}
