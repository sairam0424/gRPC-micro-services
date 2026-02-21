"use client";

import React from "react";
import { CardSpotlight } from "@/components/ui/card-spotlight";
import { ProductImage } from "@/components/product-image";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ProductCardProps {
  product: {
    product_id: string;
    name: string;
    quantity: number;
    media_id?: string;
  };
  className?: string;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  className,
}) => {
  const isOutOfStock = product.quantity <= 0;

  return (
    <CardSpotlight className={cn("flex flex-col h-full", className)}>
      <div className="relative group cursor-pointer overflow-hidden rounded-lg mb-4">
        <ProductImage 
          mediaId={product.media_id || ""} 
          alt={product.name}
          className="w-full aspect-square transition-transform duration-500 group-hover:scale-110" 
        />
        {isOutOfStock && (
          <div className="absolute inset-0 bg-black/60 backdrop-blur-[2px] flex items-center justify-center">
            <Badge variant="destructive" className="uppercase font-bold tracking-wider">Out of Stock</Badge>
          </div>
        )}
      </div>

      <div className="flex flex-col flex-1 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-zinc-100 group-hover:text-primary transition-colors line-clamp-1">
            {product.name || `Product ${product.product_id}`}
          </h3>
          <Badge 
            variant={isOutOfStock ? "outline" : "secondary"} 
            className={cn(
              "text-[10px] font-bold uppercase",
              !isOutOfStock && "bg-primary/10 text-primary border-primary/20"
            )}
          >
            {product.product_id}
          </Badge>
        </div>

        <div className="mt-auto flex items-center justify-between pt-4 border-t border-zinc-800">
          <div className="space-y-0.5">
            <p className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">Inventory</p>
            <p className={cn(
              "text-lg font-bold tabular-nums",
              isOutOfStock ? "text-zinc-600" : "text-zinc-100"
            )}>
              {product.quantity}
            </p>
          </div>
          <div className="text-right space-y-0.5">
             <p className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">Status</p>
             <p className={cn(
               "text-sm font-medium",
               isOutOfStock ? "text-red-500" : "text-green-500"
             )}>
               {isOutOfStock ? "Alert" : "Healthy"}
             </p>
          </div>
        </div>
      </div>
    </CardSpotlight>
  );
};
