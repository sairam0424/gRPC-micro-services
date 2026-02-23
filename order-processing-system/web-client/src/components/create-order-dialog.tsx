"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { useAuth } from "@/context/auth-context";

export function CreateOrderDialog({ onOrderCreated }: { onOrderCreated: (order: any) => void }) {
  const [customerId, setCustomerId] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { token } = useAuth();

  const handleSubmit = async (e: any) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          customer_id: customerId,
          items: [
            {
              product_id: productId,
              quantity: quantity,
              price_cents: 1000
            }
          ]
        })
      });

      if (response.ok) {
        const data = await response.json();
        onOrderCreated(data);
        setIsOpen(false);
        // Reset form
        setCustomerId("");
        setProductId("");
        setQuantity(1);
      } else {
        const data = await response.json();
        if (data.detail && typeof data.detail === "object") {
          // Flatten Pydantic/FastAPI validation errors
          const errorMsg = Array.isArray(data.detail) 
            ? data.detail.map((err: any) => `${err.loc.join('.')}: ${err.msg}`).join(", ")
            : JSON.stringify(data.detail);
          setError(errorMsg);
        } else {
          setError(data.detail || "Failed to create order");
        }
      }
    } catch (error) {
      console.error("Error creating order:", error);
      setError("Network error. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>Create Order</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Create New Order</DialogTitle>
          <DialogDescription>
            Enter the details for the new order.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="customer" className="text-right">
                Customer
              </Label>
              <Input
                id="customer"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                className="col-span-3"
                placeholder="CUST-123"
                required
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="product" className="text-right">
                Product
              </Label>
              <Input
                id="product"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                className="col-span-3"
                placeholder="PROD-456"
                required
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="quantity" className="text-right">
                Quantity
              </Label>
              <Input
                id="quantity"
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
                className="col-span-3"
                min="1"
                required
              />
            </div>
            {error && (
              <div className="col-span-4 rounded-md bg-destructive/15 p-3 text-sm text-destructive font-medium">
                {error}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "Creating..." : "Create Order"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
