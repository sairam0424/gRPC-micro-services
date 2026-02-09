"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/context/auth-context";
import { UserNav } from "./user-nav";
import { Package2 } from "lucide-react";
import { CreateOrderDialog } from "@/components/create-order-dialog";

export interface Order {
  order_id: string;
  customer_id: string;
  status: string;
}

export default function Dashboard() {
  const [orders, setOrders] = useState<any[]>([]);
  const [inventory, setInventory] = useState<any[]>([]);
  const { token, user } = useAuth();
  
  const fetchOrders = async () => {
    try {
      const response = await fetch("/api/orders", {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      const data = await response.json();
      setOrders(data.orders || []);
    } catch (error) {
      console.error("Failed to fetch orders:", error);
    }
  };

  const fetchInventory = async () => {
    try {
      const response = await fetch("/api/inventory", {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      const data = await response.json();
      setInventory(data.inventory || []);
    } catch (error) {
      console.error("Failed to fetch inventory:", error);
    }
  };

  useEffect(() => {
    if (!token) return;

    fetchOrders();
    fetchInventory();

    const eventSource = new EventSource(`/api/orders/events?token=${token}`);
    
    eventSource.onmessage = (event) => {
      try {
        const updatedOrder = JSON.parse(event.data);
        setOrders((prev) => {
          const index = prev.findIndex((o) => o.order_id === updatedOrder.order_id);
          if (index !== -1) {
            const newOrders = [...prev];
            newOrders[index] = updatedOrder;
            return newOrders;
          }
          return [updatedOrder, ...prev];
        });
      } catch (error) {
        console.error("Failed to parse SSE message:", error);
      }
    };

    return () => eventSource.close();
  }, [token]);

  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-white shadow-lg shadow-primary/20">
              <Package2 className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">OrderCore</h1>
              <p className="text-[10px] uppercase tracking-widest text-zinc-500">Enterprise Logistics</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <CreateOrderDialog onOrderCreated={(newOrder) => setOrders(prev => [newOrder, ...prev])} />
            <div className="h-8 w-px bg-zinc-800" />
            <UserNav />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-3">
          {/* Order List */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-semibold">Orders</h2>
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <span className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                Live Updates Enabled
              </div>
            </div>
            <div className="grid gap-4">
              {orders.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/30 py-20 text-center">
                  <div className="rounded-full bg-zinc-800/50 p-4 mb-4 text-zinc-600">
                    <Package2 className="h-10 w-10" />
                  </div>
                  <h3 className="text-lg font-medium text-zinc-400">No orders yet</h3>
                  <p className="text-sm text-zinc-500 max-w-xs mt-1">Create your first order to see it appear here in real-time.</p>
                </div>
              ) : (
                orders.map((order) => (
                  <div 
                    key={order.order_id} 
                    className="group relative overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6 transition-all hover:border-zinc-700 hover:bg-zinc-900 shadow-sm"
                  >
                    <div className="flex items-center justify-between mb-4">
                      <div className="space-y-1">
                        <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">Order ID</p>
                        <p className="font-mono text-sm font-semibold">{order.order_id}</p>
                      </div>
                      <div className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider ${
                        order.status === 'COMPLETED' ? 'bg-green-500/10 text-green-500' :
                        order.status === 'FAILED' ? 'bg-red-500/10 text-red-500' :
                        order.status === 'PENDING' ? 'bg-yellow-500/10 text-yellow-500' :
                        'bg-blue-500/10 text-blue-500'
                      }`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${
                          order.status === 'COMPLETED' ? 'bg-green-500' :
                          order.status === 'FAILED' ? 'bg-red-500' :
                          'bg-current animate-pulse'
                        }`} />
                        {order.status}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">Customer</p>
                        <p className="text-sm">{order.customer_id}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">Total Items</p>
                        <p className="text-sm font-semibold text-primary">{order.items?.length || 0}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Inventory Summary */}
          <div className="space-y-6">
            <h2 className="text-2xl font-semibold">Inventory</h2>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6">
              <div className="space-y-4">
                {['SKU-1001', 'SKU-1002', 'SKU-1003'].map((sku) => (
                  <div key={sku} className="flex items-center justify-between border-b border-zinc-800 pb-4 last:border-0 last:pb-0">
                    <div className="space-y-1">
                      <p className="text-sm font-medium">{sku}</p>
                      <p className="text-xs text-zinc-500">Reserved: 12 units</p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold">120</p>
                      <p className="text-[10px] uppercase font-bold text-zinc-500">Available</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* System Status Card */}
            <div className="rounded-2xl bg-gradient-to-br from-primary/10 to-transparent border border-primary/20 p-6">
              <h3 className="text-sm font-bold uppercase tracking-wider text-primary mb-2">System Status</h3>
              <p className="text-xs text-zinc-400 mb-4 leading-relaxed">The Saga orchestrator is actively managing inventory reservations across all active shards.</p>
              <div className="flex gap-2">
                <div className="h-1 flex-1 rounded-full bg-primary/20 overflow-hidden">
                  <div className="h-full w-full bg-primary animate-pulse" />
                </div>
                <div className="h-1 flex-1 rounded-full bg-primary/20 overflow-hidden">
                   <div className="h-full w-2/3 bg-primary" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
