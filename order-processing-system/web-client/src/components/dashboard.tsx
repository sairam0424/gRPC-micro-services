"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { CreateOrderDialog } from "@/components/create-order-dialog";

export interface Order {
  order_id: string;
  customer_id: string;
  status: string;
}

export default function Dashboard() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [inventory, setInventory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchOrders = async () => {
    try {
      const response = await fetch("/api/orders");
      if (response.ok) {
        const data = await response.json();
        setOrders(data.orders || []);
      }
    } catch (error) {
      console.error("Failed to fetch orders:", error);
    }
  };

  const fetchInventory = async () => {
    try {
      // In a real app, we'd have a proxy endpoint in the gateway
      // Since we don't have a direct gRPC ListInventory yet, 
      // let's assume the gateway provides a basic health/status or we call inventory-service if possible.
      // For this demo, we'll fetch from the gateway's new /inventory endpoint
      const response = await fetch("/api/inventory");
      if (response.ok) {
        // This is just a status for now as per my gateway change
        // In a real system, it would return the actual list.
      }
    } catch (error) {
      console.error("Failed to fetch inventory:", error);
    }
  };

  const refreshData = async () => {
    setLoading(true);
    await Promise.all([fetchOrders(), fetchInventory()]);
    setLoading(false);
  };

  useEffect(() => {
    refreshData();
  }, []);

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
        <div className="flex items-center space-x-2">
          <CreateOrderDialog onOrderCreated={refreshData} />
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Orders</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{orders.length}</div>
          </CardContent>
        </Card>
        {/* Add more summary cards here */}
      </div>
      <Card className="col-span-4">
        <CardHeader>
          <CardTitle>Recent Orders</CardTitle>
          <CardDescription>
            You have {orders.length} orders in the system.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order ID</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((order) => (
                <TableRow key={order.order_id}>
                  <TableCell className="font-medium">{order.order_id}</TableCell>
                  <TableCell>{order.customer_id}</TableCell>
                  <TableCell>
                    <Badge variant={order.status === "COMPLETED" ? "default" : "secondary"}>
                      {order.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm">View</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
