// src/components/Memory.jsx

import React, {
    useRef,
    useLayoutEffect,
    useImperativeHandle,
    forwardRef,
    useState,
  } from 'react';
  import { Network } from 'vis-network/standalone/esm/vis-network';
  import useWebSocket from '../hooks/useWebSocket'; // Custom WebSocket hook
  
  /**
   * Memory.jsx
   * This component displays a dynamic knowledge graph.
   * It connects to a WebSocket and visualizes incoming nodes and edges
   * using vis-network in real time.
   */
  const Memory = forwardRef((props, ref) => {
    const containerRef = useRef(null);
    const networkRef = useRef(null);
  
    const [graphData, setGraphData] = useState({
      nodes: [],
      edges: [],
    });
  
    // --- WebSocket Setup ---
    // Replace with actual dynamic IDs from your conversation flow later
    const conversationId = 'conv123';
    const questionId = 'q001';
    const wsUrl = `ws://localhost:8766/ws/memory/${conversationId}/${questionId}/`;
  
    // Listen to streamed updates from the backend
    useWebSocket(wsUrl, (data) => {
      setGraphData((prev) => ({
        nodes: [...prev.nodes, ...(data.nodes || [])],
        edges: [...prev.edges, ...(data.edges || [])],
      }));
    });
  
    // --- Expose resize method to parent via ref (used in QAPage) ---
    useImperativeHandle(ref, () => ({
      resize: () => {
        if (containerRef.current && networkRef.current) {
          const { clientWidth, clientHeight } = containerRef.current;
          networkRef.current.setSize(clientWidth + 'px', clientHeight + 'px');
          networkRef.current.redraw();
        }
      },
    }));
  
    // --- Initialize & update network when data changes ---
    useLayoutEffect(() => {
      if (!containerRef.current) return;
  
      const options = {
        layout: { improvedLayout: true },
        nodes: {
          shape: 'circle',
          scaling: { min: 20, max: 20 },
          widthConstraint: { minimum: 80, maximum: 80 },
          font: {
            color: '#000000',
            face: 'monospace',
            size: 14,
          },
          color: {
            background: '#ffffff', // ✅ White node background
            border: '#111827',     // ✅ Dark gray border
            highlight: {
              background: '#fef3c7',
              border: '#111827',
            },
          },
        },
        edges: {
          smooth: { type: 'dynamic' },
          arrows: { to: { enabled: true, scaleFactor: 0.7 } },
          font: {
            color: '#1f2937',
            face: 'monospace',
            align: 'top',
          },
          color: {
            color: '#6b7280',
            highlight: '#374151',
          },
        },
        physics: {
          enabled: true,
          solver: 'forceAtlas2Based',
          forceAtlas2Based: {
            gravitationalConstant: -50,
            centralGravity: 0.01,
            springLength: 150,
            springConstant: 0.08,
          },
          minVelocity: 0.75,
        },
        interaction: {
          hover: true,
          zoomView: true,
          dragNodes: true,
        },
      };
  
      const network = new Network(containerRef.current, graphData, options);
      networkRef.current = network;
  
      const { clientWidth, clientHeight } = containerRef.current;
      network.setSize(clientWidth + 'px', clientHeight + 'px');
      network.redraw();
    }, [graphData]);
  
    return (
      <div className="w-full h-full relative">
        <div className="absolute top-2 left-3 z-10 text-white text-sm font-semibold">
          Knowledge Graph Memory
        </div>
        <div
          ref={containerRef}
          className="w-full h-full"
          style={{ backgroundColor: 'transparent' }}
        />
      </div>
    );
  });
  
  export default Memory;
  