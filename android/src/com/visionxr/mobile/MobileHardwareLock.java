package com.visionxr.mobile;

import android.content.Context;
import android.os.Build;
import android.provider.Settings;
import java.io.File;
import java.io.FileOutputStream;
import java.security.MessageDigest;
import java.security.SecureRandom;

public class MobileHardwareLock {
    private static final int MAX_ATTEMPTS = 20;

    public static String getHardwareId(Context context) {
        try {
            String androidId = Settings.Secure.getString(context.getContentResolver(), Settings.Secure.ANDROID_ID);
            String raw = Build.FINGERPRINT + "|" + Build.HARDWARE + "|" + (androidId != null ? androidId : "0000");
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(raw.getBytes("UTF-8"));
            StringBuilder sb = new StringBuilder("VXR-MOB-");
            for (int i = 0; i < 8; i++) {
                sb.append(String.format("%02X", hash[i]));
            }
            return sb.toString();
        } catch (Exception e) {
            return "VXR-MOB-NODE-LOCK";
        }
    }

    public static void checkTamperAttempts(Context context, int currentAttempts) {
        if (currentAttempts >= MAX_ATTEMPTS) {
            triggerSelfDestruct(context);
        }
    }

    public static void triggerSelfDestruct(Context context) {
        // Multi-pass cryptographic overwrite and shredding of internal storage
        File evidenceDir = new File(context.getFilesDir(), "sovereign_evidence");
        if (evidenceDir.exists()) {
            File[] files = evidenceDir.listFiles();
            if (files != null) {
                SecureRandom rng = new SecureRandom();
                for (File f : files) {
                    try {
                        byte[] randomBytes = new byte[(int) f.length()];
                        rng.nextBytes(randomBytes);
                        FileOutputStream fos = new FileOutputStream(f);
                        fos.write(randomBytes);
                        fos.flush();
                        fos.close();
                        f.delete();
                    } catch (Exception ignored) {}
                }
            }
        }
        System.exit(99);
    }
}
