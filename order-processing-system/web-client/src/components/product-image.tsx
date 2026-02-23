"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/context/auth-context";
import { Loader2, ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProductImageProps {
  mediaId: string;
  alt?: string;
  className?: string;
  aspectRatio?: "square" | "video" | "auto";
}

export const ProductImage: React.FC<ProductImageProps> = ({
  mediaId,
  alt = "Product image",
  className,
  aspectRatio = "square",
}) => {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const { token } = useAuth();

  useEffect(() => {
    const fetchUrl = async () => {
      if (
        !mediaId ||
        !token ||
        mediaId === "550e8400-e29b-41d4-a716-446655440000"
      ) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const response = await fetch(`/api/media/${mediaId}/view-url`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.error(
            `Failed to fetch image URL for ${mediaId}. Status: ${response.status}`,
            errorText,
          );
          throw new Error("Failed to fetch image URL");
        }

        const data = await response.json();
        if (!data.view_url) {
          console.warn(`No view_url returned for media ${mediaId}`);
          setError(true);
        } else {
          setImageUrl(data.view_url);
          setError(false);
        }
      } catch (err) {
        console.error("Error fetching image URL:", err);
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchUrl();
  }, [mediaId, token]);

  const aspectClass = {
    square: "aspect-square",
    video: "aspect-video",
    auto: "aspect-auto",
  }[aspectRatio];

  return (
    <div
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-xl bg-zinc-900",
        aspectClass,
        className,
      )}
    >
      {loading ? (
        <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
      ) : error || !imageUrl ? (
        <div className="flex flex-col items-center gap-2 text-zinc-600">
          <ImageIcon className="h-8 w-8" />
          <span className="text-xs">Image unavailable</span>
        </div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imageUrl}
          alt={alt}
          className="h-full w-full object-cover transition-transform duration-500 hover:scale-105"
          onLoad={() => setLoading(false)}
        />
      )}
    </div>
  );
};
