"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ShieldCheck, Database, Zap, AlertTriangle } from "lucide-react";

interface FilterMetrics {
  bf_tier1_hits: number;
  bf_tier1_rejects: number;
  cf_tier2_hits: number;
  cf_tier2_rejects: number;
  db_hits_prevented: number;
}

export function FilterDashboard({ token }: { token: string | null }) {
  const [metrics, setMetrics] = useState<FilterMetrics | null>(null);

  const fetchMetrics = async () => {
    if (!token) return;
    try {
      const response = await fetch("/api/metrics/filters", {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await response.json();
      setMetrics(data);
    } catch (error) {
      console.error("Failed to fetch filter metrics:", error);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, [token]);

  if (!metrics) return null;

  const totalTier1 = metrics.bf_tier1_hits + metrics.bf_tier1_rejects;
  const tier1Efficiency = totalTier1 > 0 ? (metrics.bf_tier1_rejects / totalTier1 * 100).toFixed(1) : "0";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-primary" />
          Filter Performance
        </h2>
        <div className="text-xs text-zinc-500 uppercase tracking-widest bg-zinc-900 px-2 py-1 rounded border border-zinc-800">
          Real-time Protection
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400 uppercase tracking-wider">Tier-1 (Catalog)</CardTitle>
            <CardDescription className="text-2xl font-bold text-zinc-100">{metrics.bf_tier1_rejects}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <Zap className="h-3 w-3 text-yellow-500" />
              <span>{tier1Efficiency}% requests pre-filtered</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400 uppercase tracking-wider">Database Shield</CardTitle>
            <CardDescription className="text-2xl font-bold text-green-500">+{metrics.db_hits_prevented}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <Database className="h-3 w-3 text-primary" />
              <span>Calls prevented by Bloom/Cuckoo</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="rounded-2xl bg-zinc-900/50 border border-zinc-800 p-6 space-y-4">
        <h3 className="text-sm font-bold text-zinc-500 uppercase tracking-tight">Traffic Breakdown</h3>
        <div className="space-y-3">
          <div className="space-y-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-zinc-400">Tier-2 Stock Rejections (Cuckoo)</span>
              <span className="font-mono text-primary">{metrics.cf_tier2_rejects}</span>
            </div>
            <div className="h-2 w-full bg-zinc-800 rounded-full overflow-hidden">
               <div 
                 className="h-full bg-primary transition-all duration-500" 
                 style={{ width: `${Math.min(100, (metrics.cf_tier2_rejects / (metrics.cf_tier2_hits + metrics.cf_tier2_rejects || 1)) * 100)}%` }} 
               />
            </div>
          </div>
          
          <div className="space-y-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-zinc-400">Total Valid Requests</span>
              <span className="font-mono text-green-500">{metrics.bf_tier1_hits}</span>
            </div>
            <div className="h-2 w-full bg-zinc-800 rounded-full overflow-hidden">
               <div 
                 className="h-full bg-green-500 transition-all duration-500" 
                 style={{ width: `${Math.min(100, (metrics.bf_tier1_hits / totalTier1 || 1)) * 100}%` }} 
               />
            </div>
          </div>
        </div>
        
        <div className="mt-4 pt-4 border-t border-zinc-800">
          <div className="flex items-start gap-3 text-[11px] text-zinc-500 leading-tight">
            <AlertTriangle className="h-4 w-4 text-primary shrink-0" />
            <p>The multi-tier filtering system is currently operating at peak efficiency, preventing unnecessary database load for non-existent products and out-of-stock items.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
