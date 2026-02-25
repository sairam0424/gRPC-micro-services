"use client";

import { useState } from "react";
import { Search, Package, User, Clock, AlertCircle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;

    setLoading(true);
    setError("");
    try {
      const resp = await fetch(`/api/orders/search?q=${encodeURIComponent(query)}`);
      if (!resp.ok) throw new Error("Search failed");
      const data = await resp.json();
      setResults(data.orders || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-8">
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Search Orders</h1>
        <p className="text-muted-foreground">
          Query the order analytics index via Elasticsearch
        </p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-4 max-w-2xl">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by Order ID, Customer ID, or Status..."
            className="pl-10"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={loading}>
          {loading ? "Searching..." : "Search"}
        </Button>
      </form>

      {error && (
        <Card className="border-destructive bg-destructive/10">
          <CardContent className="flex items-center gap-2 pt-6">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <p className="text-destructive font-medium">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4">
        {results.length > 0 ? (
          results.map((order, idx) => (
            <Card key={idx} className="hover:bg-accent/50 transition-colors">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                   Order {order.order_id}
                </CardTitle>
                <Badge variant={order.status === "COMPLETED" ? "default" : "secondary"}>
                  {order.status}
                </Badge>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 text-sm mt-2">
                  <div className="flex items-center gap-2">
                    <User className="h-4 w-4 text-muted-foreground" />
                    <span>Customer: {order.customer_id}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span>Type: {order.event_type || "N/A"}</span>
                  </div>
                </div>
                {order.message && (
                  <p className="mt-4 text-sm text-muted-foreground border-l-2 pl-4 py-1 italic">
                    "{order.message}"
                  </p>
                )}
              </CardContent>
            </Card>
          ))
        ) : !loading && query && (
          <div className="text-center py-12 text-muted-foreground">
            No results found for "{query}"
          </div>
        )}
      </div>
    </div>
  );
}
