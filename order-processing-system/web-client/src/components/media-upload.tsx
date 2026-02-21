"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/auth-context";
import { Upload, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface MediaUploadProps {
  entityType: "inventory" | "order";
  entityId: string;
  onSuccess?: (mediaId: string) => void;
  className?: string;
}

export const MediaUpload: React.FC<MediaUploadProps> = ({
  entityType,
  entityId,
  onSuccess,
  className,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [progress, setProgress] = useState(0);
  const { token } = useAuth();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setStatus("idle");
    }
  };

  const uploadFile = async () => {
    if (!file || !token) return;

    try {
      setStatus("uploading");
      setProgress(10);

      // 1. Get Pre-signed URL
      const urlResponse = await fetch("/api/media/upload-url", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          entity_type: entityType,
          entity_id: entityId,
          file_name: file.name,
          content_type: file.type,
        }),
      });

      if (!urlResponse.ok) throw new Error("Failed to get upload URL");
      const { media_id, upload_url } = await urlResponse.json();
      setProgress(30);

      // 2. Upload to MinIO (direct PUT)
      const uploadResponse = await fetch(upload_url, {
        method: "PUT",
        body: file,
        headers: {
          "Content-Type": file.type,
        },
      });

      if (!uploadResponse.ok) throw new Error("Failed to upload to storage");
      setProgress(70);

      // 3. Confirm Upload
      const confirmResponse = await fetch(`/api/media/${media_id}/confirm-upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!confirmResponse.ok) throw new Error("Failed to confirm upload");
      
      setProgress(100);
      setStatus("success");
      if (onSuccess) onSuccess(media_id);
    } catch (error) {
      console.error("Upload error:", error);
      setStatus("error");
    }
  };

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-zinc-800 bg-zinc-900/30 p-8 transition-colors hover:border-zinc-700">
        <input
          type="file"
          id="file-upload"
          className="hidden"
          onChange={handleFileChange}
          accept="image/*"
        />
        <label
          htmlFor="file-upload"
          className="flex cursor-pointer flex-col items-center gap-2"
        >
          {status === "uploading" ? (
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
          ) : status === "success" ? (
            <CheckCircle2 className="h-10 w-10 text-green-500" />
          ) : status === "error" ? (
            <XCircle className="h-10 w-10 text-red-500" />
          ) : (
            <Upload className="h-10 w-10 text-zinc-500 group-hover:text-zinc-400" />
          )}
          <span className="text-sm font-medium text-zinc-400">
            {file ? file.name : "Click to select image"}
          </span>
        </label>
      </div>

      {file && status === "idle" && (
        <Button onClick={uploadFile} className="w-full">
          Start Upload
        </Button>
      )}

      {status === "uploading" && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
};
