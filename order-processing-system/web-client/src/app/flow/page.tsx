"use client";

import React, { useEffect, useState } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  Edge, 
  Node,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, Database, Zap } from "lucide-react";

export default function FlowPage() {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFlow = async () => {
      try {
        const resp = await fetch('/api/analytics/flow');
        const data = await resp.json();
        
        // Map markers for edges
        const mappedEdges = data.edges.map((e: any) => ({
          ...e,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: '#3b82f6',
          },
          style: { stroke: '#3b82f6', strokeWidth: 2 },
        }));

        setNodes(data.nodes);
        setEdges(mappedEdges);
      } catch (err) {
        console.error("Failed to fetch flow metadata", err);
      } finally {
        setLoading(false);
      }
    };

    fetchFlow();
  }, []);

  return (
    <div className="container mx-auto p-6 space-y-8 h-[calc(100vh-100px)]">
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Streaming Pipeline Flow</h1>
        <p className="text-muted-foreground">
          Real-time structural visualization of the Kafka-Flink-Elasticsearch pipeline
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 h-full">
        <Card className="md:col-span-3 h-full border-2 overflow-hidden bg-slate-50 dark:bg-slate-900">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            className="w-full h-full"
          >
            <Background color="#cbd5e1" gap={20} />
            <Controls />
          </ReactFlow>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Activity className="h-4 w-4 text-blue-500" />
                Pipeline Stats
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground">Status</span>
                <Badge variant="default" className="bg-green-500">Active</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground">Processing Latency</span>
                <span className="text-sm font-mono">~150ms</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground">Checkpointing</span>
                <Badge variant="outline">Enabled (S3)</Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Zap className="h-4 w-4 text-yellow-500" />
                Connectivity
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
               <div className="flex items-center gap-2 text-xs">
                 <div className="h-2 w-2 rounded-full bg-green-500" />
                 Kafka Broker (kafka:29092)
               </div>
               <div className="flex items-center gap-2 text-xs">
                 <div className="h-2 w-2 rounded-full bg-green-500" />
                 Flink JobManager (flink:8081)
               </div>
               <div className="flex items-center gap-2 text-xs">
                 <div className="h-2 w-2 rounded-full bg-green-500" />
                 Elasticsearch (es:9200)
               </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
