package com.visionxr.mobile;

import android.content.Context;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class SovereignStorageGuard {
    private final File privateStorageDir;

    public SovereignStorageGuard(Context context) {
        // Strictly internal private app directory: /data/user/0/com.visionxr.mobile/files/sovereign_evidence/
        this.privateStorageDir = new File(context.getFilesDir(), "sovereign_evidence");
        if (!privateStorageDir.exists()) {
            privateStorageDir.mkdirs();
        }
    }

    public synchronized String saveDiscrepancyFrame(String lens, byte[] frameData) {
        try {
            String timeStamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
            String fileName = "DISCREPANCY_" + lens.toUpperCase() + "_" + timeStamp + ".dat";
            File targetFile = new File(privateStorageDir, fileName);

            // Simple XOR scramble + private file storage
            byte[] scrambled = new byte[frameData.length];
            byte key = (byte) 0xA5;
            for (int i = 0; i < frameData.length; i++) {
                scrambled[i] = (byte) (frameData[i] ^ key);
            }

            FileOutputStream fos = new FileOutputStream(targetFile);
            fos.write(scrambled);
            fos.flush();
            fos.close();
            return targetFile.getAbsolutePath();
        } catch (Exception e) {
            e.printStackTrace();
            return null;
        }
    }

    public File[] listEvidenceFiles() {
        return privateStorageDir.listFiles();
    }

    public int getEvidenceCount() {
        File[] files = listEvidenceFiles();
        return files != null ? files.length : 0;
    }
}
