"use client";

import { useEffect, useState } from "react";

export default function ClusterDashboard() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/cluster/status", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) throw new Error("Failed to fetch cluster status");
      const data = await res.json();
      setStatus(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="p-8 text-white">Loading Cluster Status...</div>;
  if (error) return <div className="p-8 text-red-400">Error: {error}</div>;

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-200 p-8 font-sans">
      <header className="mb-12">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent mb-2">
          Raft Cluster Consensus
        </h1>
        <p className="text-slate-400">Real-time distributed state and metric-based routing dashboard.</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        {/* Leader Card */}
        <div className="bg-slate-800/50 backdrop-blur-md border border-slate-700 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-slate-300">Cluster Leader</h3>
            <div className="px-3 py-1 bg-amber-500/20 text-amber-500 rounded-full text-xs font-mono">RAFT QUORUM</div>
          </div>
          <div className="text-3xl font-mono text-cyan-400 truncate">
            {status?.leader || "ELECTING..."}
          </div>
          <p className="mt-2 text-sm text-slate-500">Currently handling all STRONGLY CONSISTENT writes and reads.</p>
        </div>

        {/* Node Count Card */}
        <div className="bg-slate-800/50 backdrop-blur-md border border-slate-700 rounded-2xl p-6 shadow-xl">
          <h3 className="text-lg font-semibold text-slate-300 mb-4">Total Nodes</h3>
          <div className="text-5xl font-bold text-white">{Object.keys(status?.nodes || {}).length}</div>
          <p className="mt-2 text-sm text-slate-500">1 Leader + {Object.keys(status?.nodes || {}).length - 1} Replicas</p>
        </div>

        {/* My Status Card */}
        <div className="bg-slate-800/50 backdrop-blur-md border border-slate-700 rounded-2xl p-6 shadow-xl">
          <h3 className="text-lg font-semibold text-slate-300 mb-4">Local Node Role</h3>
          <div className={`text-3xl font-bold ${status?.is_leader ? 'text-emerald-400' : 'text-blue-400'}`}>
            {status?.is_leader ? 'LEADER' : 'REPLICA'}
          </div>
          <p className="mt-2 text-sm font-mono text-slate-500 truncate">{status?.current_node_id}</p>
        </div>
      </div>

      <h2 className="text-2xl font-semibold mb-6 text-slate-100">PostgreSQL HA Cluster (Patroni)</h2>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-12">
        {status?.db_cluster && Object.entries(status.db_cluster).map(([name, info]: [string, any]) => (
          <div key={name} className={`bg-slate-800/40 border ${info.role === 'leader' ? 'border-amber-500/50' : 'border-slate-700'} rounded-2xl p-6`}>
            <div className="flex justify-between items-center mb-4">
              <h4 className="font-mono text-white">{name}</h4>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${info.role === 'leader' ? 'bg-amber-500 text-slate-900' : 'bg-slate-700 text-slate-400'}`}>
                {info.role.toUpperCase()}
              </span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-500">STATE</span>
                <span className={info.state === 'running' ? 'text-emerald-400' : 'text-red-400'}>{info.state.toUpperCase()}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-500">LAG</span>
                <span className="text-slate-300">{info.lag} MB</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-500">ENDPOINT</span>
                <span className="text-slate-400 font-mono">{info.host}:{info.port}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <h2 className="text-2xl font-semibold mb-6 text-slate-100">Application Nodes & Metrics</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {status?.nodes && Object.entries(status.nodes).map(([id, metrics]: [string, any]) => (
          <div key={id} className={`group relative bg-slate-800/40 backdrop-blur-sm border ${id === status.leader ? 'border-cyan-500/50 shadow-cyan-500/10' : 'border-slate-700'} rounded-2xl p-6 transition-all hover:bg-slate-800/60`}>
            {id === status.leader && (
              <div className="absolute -top-3 left-6 px-3 py-0.5 bg-cyan-500 text-slate-900 text-xs font-bold rounded-full">
                ACTIVE LEADER
              </div>
            )}
            
            <div className="flex justify-between items-start mb-6">
              <div>
                <h4 className="text-xl font-mono text-white mb-1">{id}</h4>
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${metrics.status === 'healthy' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${metrics.status === 'healthy' ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`}></span>
                  {metrics.status.toUpperCase()}
                </span>
              </div>
              <div className="text-right">
                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Connections</div>
                <div className="text-2xl font-mono text-white">{metrics.connections}</div>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs text-slate-400 mb-2">
                  <span>CPU UTILIZATION</span>
                  <span>{metrics.cpu_usage}%</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-1.5 overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-500 ${metrics.cpu_usage > 80 ? 'bg-red-500' : metrics.cpu_usage > 50 ? 'bg-amber-500' : 'bg-cyan-500'}`}
                    style={{ width: `${metrics.cpu_usage}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-12 p-6 bg-blue-500/5 border border-blue-500/20 rounded-2xl">
        <h4 className="text-blue-400 font-semibold mb-2 flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            Routing Logic Information
        </h4>
        <p className="text-sm text-slate-400 leading-relaxed">
            Requests are routed via <strong>HAProxy</strong> to the currently promoted PostgreSQL leader. 
            Read traffic is balanced across replicas using Patroni's health-check integration. 
            The application additionally uses a <strong>Metric-Based Load Balancer</strong> to select the best 
            application node for processing, ensuring end-to-end high availability.
        </p>
      </div>
    </div>
  );
}
