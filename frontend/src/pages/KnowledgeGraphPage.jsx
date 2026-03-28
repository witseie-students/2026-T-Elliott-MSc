// src/pages/KnowledgeGraphPage.jsx
//
// Knowledge Graph Generation pipeline demo page.
//
// The page walks the examiner through the full KG generation pipeline
// in three discrete, step-through stages:
//
//   INPUT
//     ↓  Stage 1  ← single API call fires here, full pipeline runs
//   PREPROCESSING         (proposition chunking + coreference resolution)
//     ↓  Stage 2  ← data already loaded, just reveals the next section
//   INFORMATION EXTRACTION (triple extraction + intermediate KG with floating islands)
//     ↓  Stage 3  ← data already loaded, just reveals the next section
//   POST-PROCESSING       (inferred relationships → connected abstract KG;
//                           ontological entity identification for global KG)
//
// API endpoint (Django backend):
//   POST http://localhost:8000/api/process_paragraph_parallel/
//   Body: { "paragraph": "<text>" }
//
// Response fields used per stage:
//   Stage 1 → results[].proposition_sentence
//             results[].coreferenced_sentence
//   Stage 2 → results[].quadruples[].quadruple  (subject, predicate, object)
//   Stage 3 → new_inferred_quadruples[].quadruple
//             ontological_entities[]

import React, { useState, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';
import ForceGraph2D from 'react-force-graph-2d';
import Header from '../components/Header';
import backgroundImage from '../assets/background1.jpg';
import '../styles/tailwind.css';

/* ══════════════════════════════════════════════════════════════════
   CONFIG
   ══════════════════════════════════════════════════════════════════ */

// Base URL for the Django backend.
const API_BASE = 'http://localhost:8000';

// Full pipeline endpoint — parallel (production) variant.
const PIPELINE_URL = `${API_BASE}/api/process_paragraph_parallel/`;

// Auth token required by the Django REST framework token authentication.
const API_HEADERS = { Authorization: 'Token 649ad111031dae78f9fdf80fce9ad07fbeaca812' };

// First three abstracts from data/PUBMEDQA/pubmedqa_labelled_full.csv.
// Section labels (BACKGROUND:, OBJECTIVE:, METHODS:, RESULTS:) are stripped
// so the text reads as a clean paragraph. Conclusions are excluded as per
// PubMedQA convention — the labelled_contexts field already omits them.
const DEMO_ABSTRACTS = [
  {
    label: 'Abstract 1 — Chronic Rhinosinusitis & ILC2s',
    pubid: '25429730',
    text:
      'Chronic rhinosinusitis (CRS) is a heterogeneous disease with an uncertain pathogenesis. ' +
      'Group 2 innate lymphoid cells (ILC2s) represent a recently discovered cell population which has been ' +
      'implicated in driving Th2 inflammation in CRS; however, their relationship with clinical disease ' +
      'characteristics has yet to be investigated. ' +
      'The aim of this study was to identify ILC2s in sinus mucosa in patients with CRS and controls and ' +
      'compare ILC2s across characteristics of disease. ' +
      'A cross-sectional study of patients with CRS undergoing endoscopic sinus surgery was conducted. ' +
      'Sinus mucosal biopsies were obtained during surgery and control tissue from patients undergoing ' +
      'pituitary tumour resection through transphenoidal approach. ILC2s were identified as CD45(+) Lin(-) ' +
      'CD127(+) CD4(-) CD8(-) CRTH2(CD294)(+) CD161(+) cells in single cell suspensions through flow ' +
      'cytometry. ILC2 frequencies, measured as a percentage of CD45(+) cells, were compared across CRS ' +
      'phenotype, endotype, inflammatory CRS subtype and other disease characteristics including blood ' +
      'eosinophils, serum IgE, asthma status and nasal symptom score. ' +
      '35 patients (40% female, age 48 ± 17 years) including 13 with eosinophilic CRS (eCRS), 13 with ' +
      'non-eCRS and 9 controls were recruited. ILC2 frequencies were associated with the presence of nasal ' +
      'polyps (P = 0.002) as well as high tissue eosinophilia (P = 0.004) and eosinophil-dominant CRS ' +
      '(P = 0.001) (Mann-Whitney U). They were also associated with increased blood eosinophilia (P = 0.005). ' +
      'There were no significant associations found between ILC2s and serum total IgE and allergic disease. ' +
      'In the CRS with nasal polyps (CRSwNP) population, ILC2s were increased in patients with co-existing ' +
      'asthma (P = 0.03). ILC2s were also correlated with worsening nasal symptom score in CRS (P = 0.04).',
  },
  {
    label: 'Abstract 2 — PEMT, Vagus Nerve & Obesity',
    pubid: '25433161',
    text:
      'Phosphatidylethanolamine N-methyltransferase (PEMT), a liver enriched enzyme, is responsible for ' +
      'approximately one third of hepatic phosphatidylcholine biosynthesis. When fed a high-fat diet (HFD), ' +
      'Pemt(-/-) mice are protected from HF-induced obesity; however, they develop steatohepatitis. ' +
      'The vagus nerve relays signals between liver and brain that regulate peripheral adiposity and pancreas ' +
      'function. Here we explore a possible role of the hepatic branch of the vagus nerve in the development ' +
      'of diet induced obesity and steatohepatitis in Pemt(-/-) mice. ' +
      '8-week old Pemt(-/-) and Pemt(+/+) mice were subjected to hepatic vagotomy (HV) or capsaicin ' +
      'treatment, which selectively disrupts afferent nerves, and were compared to sham-operated or ' +
      'vehicle-treatment, respectively. After surgery, mice were fed a HFD for 10 weeks. ' +
      'HV abolished the protection against the HFD-induced obesity and glucose intolerance in Pemt(-/-) mice. ' +
      'HV normalized phospholipid content and prevented steatohepatitis in Pemt(-/-) mice. Moreover, HV ' +
      'increased the hepatic anti-inflammatory cytokine interleukin-10, reduced chemokine monocyte ' +
      'chemotactic protein-1 and the ER stress marker C/EBP homologous protein. Furthermore, HV normalized ' +
      'the expression of mitochondrial electron transport chain proteins and of proteins involved in fatty ' +
      'acid synthesis, acetyl-CoA carboxylase and fatty acid synthase in Pemt(-/-) mice. However, disruption ' +
      'of the hepatic afferent vagus nerve by capsaicin failed to reverse either the protection against the ' +
      'HFD-induced obesity or the development of HF-induced steatohepatitis in Pemt(-/-) mice.',
  },
  {
    label: 'Abstract 3 — Psammaplin A & Breast Cancer',
    pubid: '25445714',
    text:
      'Psammaplin A (PsA) is a natural product isolated from marine sponges, which has been demonstrated to ' +
      'have anticancer activity against several human cancer cell lines via the induction of cell cycle arrest ' +
      'and apoptosis. New drugs that are less toxic and more effective against multidrug-resistant cancers are ' +
      'urgently needed. ' +
      'We tested cell proliferation, cell cycle progression and autophagic cell death pathway in ' +
      'doxorubicin-resistant MCF-7 (MCF-7/adr) human breast cancer cells. The potency of PsA was further ' +
      'determined using an in vivo xenograft model.',
  },
];

/* ══════════════════════════════════════════════════════════════════
   DATA HELPERS
   Functions that transform the raw API response into the shape each
   stage section needs for rendering.
   ══════════════════════════════════════════════════════════════════ */

// Flatten all quadruples from the per-sentence results array,
// attaching the source sentences so links can display them later.
function extractAllQuads(results) {
  return results.flatMap(r =>
    (r.quadruples ?? []).map(q => ({
      ...q,
      proposition_sentence:  r.proposition_sentence,
      coreferenced_sentence: r.coreferenced_sentence,
    }))
  );
}

// Build ForceGraph2D-compatible { nodes, links } from a list of quad
// objects and, optionally, a list of inferred quad objects.
// Inferred edges are flagged so the graph can colour them differently.
function buildGraphData(extractedItems, inferredItems = []) {
  const nodeMap = new Map();
  const links   = [];

  const addNode = (name, group) => {
    if (!nodeMap.has(name)) nodeMap.set(name, { id: name, group });
  };

  extractedItems.forEach(item => {
    const sub  = item.quadruple.subject.name;
    const obj  = item.quadruple.object.name;
    const pred = item.quadruple.predicate;
    addNode(sub, 0);
    addNode(obj, 1);
    links.push({
      source: sub,
      target: obj,
      label:  pred,
      inferred: false,
      proposition_sentence:  item.proposition_sentence  ?? null,
      coreferenced_sentence: item.coreferenced_sentence ?? null,
    });
  });

  inferredItems.forEach(item => {
    const sub  = item.quadruple.subject.name;
    const obj  = item.quadruple.object.name;
    const pred = item.quadruple.predicate;
    addNode(sub, 0);
    addNode(obj, 3); // group 3 = newly bridged node
    links.push({ source: sub, target: obj, label: pred, inferred: true });
  });

  return { nodes: [...nodeMap.values()], links };
}

/* ══════════════════════════════════════════════════════════════════
   SHARED UI PRIMITIVES
   ══════════════════════════════════════════════════════════════════ */

function InfoBlock({ className = '', children }) {
  return (
    <div className={`glass-block block-accent rounded-sm p-5 ${className}`}>
      {children}
    </div>
  );
}

function BlockLabel({ text }) {
  return (
    <p className="font-mono text-xs tracking-[0.2em] uppercase text-white/50 mb-3">
      {text}
    </p>
  );
}

function PanelLabel({ text }) {
  return (
    <p className="font-mono text-[10px] tracking-[0.15em] uppercase text-white/35 mb-2">
      {text}
    </p>
  );
}

function ActionButton({ label, onClick, disabled = false }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        font-mono text-xs tracking-wider uppercase
        px-4 py-2 rounded-sm border
        transition-all duration-200
        ${disabled
          ? 'opacity-30 cursor-not-allowed border-white/20 text-white/30'
          : 'border-white/50 text-white hover:bg-white/10 cursor-pointer'
        }
      `}
    >
      {label}
    </button>
  );
}

/* ── Pipeline connector ───────────────────────────────────────────*/
function PipelineConnector({ stageNumber }) {
  return (
    <div className="flex flex-col items-center py-0.5">
      <div className="w-px h-5 bg-white/20" />
      <span className="font-mono text-[10px] tracking-widest uppercase border border-white/20 text-white/35 px-2 py-0.5 rounded-sm">
        Stage {stageNumber}
      </span>
      <div className="w-px h-5 bg-white/20" />
      <svg className="w-3 h-3 text-white/30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    </div>
  );
}

/* ── Force graph visualiser ───────────────────────────────────────
   Neo4j Bloom-style rendering:
   • Everything is drawn in graph-coordinate space so nodes scale
     naturally with zoom — small overview when zoomed out, large and
     readable when zoomed in.
   • All nodes are the same size (NODE_R graph units).
   • Label is centred inside the circle; ellipsed if it won't fit.
   • Relationship labels sit above the edge, rotate with it.
   • White canvas, light-blue nodes, directed arrows.
   • Graph auto-fits the container once the layout settles.

   Node colour by group:
     0 = extracted entity        (#60A5FA — light blue)
     1 = peripheral entity       (#93C5FD — lighter blue)
     3 = bridged / inferred node (#6EE7B7 — mint green)
─────────────────────────────────────────────────────────────────── */

// All sizes are in graph units — they scale proportionally with zoom.
const NODE_R    = 8;  // node radius (graph units)
const NODE_FONT = 5;  // label font size (graph units)
const LINK_FONT = 4;  // relationship label font size (graph units)

const NODE_COLOURS = { 0: '#60A5FA', 1: '#93C5FD', 3: '#6EE7B7' };
const nodeColour   = (node) => NODE_COLOURS[node.group] ?? '#C4B5FD';
const linkColour   = (link) => link.inferred ? '#10B981' : '#94A3B8';

// Truncate text to fit within maxWidth graph units, appending ellipsis.
function ellipsis(ctx, text, maxWidth) {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let t = text;
  while (t.length > 0 && ctx.measureText(t + '…').width > maxWidth) t = t.slice(0, -1);
  return t + '…';
}

// ── Shared canvas painters (used in both inline and modal graphs) ─

// Node: uniform circle + white label centred inside, all in graph units.
function makeNodePainter() {
  return (node, ctx, globalScale) => {
    const color = nodeColour(node);

    // Circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, NODE_R, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    // Keep the border 1.5 screen px regardless of zoom
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth   = 1.5 / globalScale;
    ctx.stroke();

    // Label — only render when large enough to read (globalScale ≥ 0.5)
    if (globalScale >= 0.5) {
      ctx.font         = `600 ${NODE_FONT}px IBM Plex Mono, monospace`;
      ctx.textAlign    = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle    = '#ffffff';
      ctx.fillText(ellipsis(ctx, node.id, NODE_R * 1.7), node.x, node.y);
    }
  };
}

// Hit area matches the visual circle exactly.
function makeNodeAreaPainter() {
  return (node, color, ctx) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, NODE_R, 0, 2 * Math.PI);
    ctx.fill();
  };
}

// Relationship label: sits above the edge midpoint, rotates with it.
// The label is ellipsed so it never exceeds the available space between
// the two node circles — preventing overlap with the node bodies.
function makeLinkPainter() {
  return (link, ctx, globalScale) => {
    if (!link.label) return;
    const src = link.source;
    const tgt = link.target;
    if (typeof src !== 'object' || typeof tgt !== 'object') return;

    if (globalScale < 0.4) return;

    const dx         = tgt.x - src.x;
    const dy         = tgt.y - src.y;
    const edgeLength = Math.sqrt(dx * dx + dy * dy);

    // Leave NODE_R clearance on each end plus a small gap
    const availableWidth = edgeLength - NODE_R * 2 - 4;
    if (availableWidth <= 0) return;

    const midX         = (src.x + tgt.x) / 2;
    const midY         = (src.y + tgt.y) / 2;
    const angle        = Math.atan2(dy, dx);
    const displayAngle = Math.abs(angle) > Math.PI / 2 ? angle + Math.PI : angle;

    ctx.save();
    ctx.translate(midX, midY);
    ctx.rotate(displayAngle);

    ctx.font         = `${LINK_FONT}px IBM Plex Mono, monospace`;
    ctx.fillStyle    = link.inferred ? '#059669' : '#475569';
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(ellipsis(ctx, link.label, availableWidth), 0, -NODE_R * 0.6);

    ctx.restore();
  };
}

// ── Shared ForceGraph2D canvas ─────────────────────────────────────
function GraphCanvas({ width, height, graphData, fgRef, onNodeHover, onLinkHover, onNodeClick, onLinkClick }) {
  const paintNode     = useCallback(makeNodePainter(),     []);
  const paintNodeArea = useCallback(makeNodeAreaPainter(), []);
  const paintLink     = useCallback(makeLinkPainter(),     []);

  // Configure D3 forces for a compact, evenly-spaced layout.
  // distanceMax on the charge force is the key setting: it limits repulsion
  // to nodes within 80 graph units of each other, so disconnected clusters
  // are not pushed apart — only adjacent nodes repel.
  useEffect(() => {
    const fg = fgRef?.current;
    if (!fg) return;
    const charge = fg.d3Force('charge');
    if (charge) { charge.strength(-80); charge.distanceMax(80); }
    const link = fg.d3Force('link');
    if (link) link.distance(35);
    // Pull everything toward the centre so disconnected clusters stay close.
    const center = fg.d3Force('center');
    if (center) center.strength(0.8);
  }, [fgRef, graphData]);

  return (
    <ForceGraph2D
      ref={fgRef}
      width={width}
      height={height}
      graphData={graphData}
      linkColor={linkColour}
      linkWidth={0.8}
      linkDirectionalArrowLength={4}
      linkDirectionalArrowRelPos={1}
      linkDirectionalArrowColor={linkColour}
      nodeCanvasObject={paintNode}
      nodeCanvasObjectMode={() => 'replace'}
      nodePointerAreaPaint={paintNodeArea}
      linkCanvasObject={paintLink}
      linkCanvasObjectMode={() => 'after'}
      backgroundColor="#ffffff"
      cooldownTicks={150}
      d3AlphaDecay={0.025}
      d3VelocityDecay={0.35}
      onEngineStop={() => fgRef?.current?.zoomToFit(0, 20)}
      onNodeHover={onNodeHover}
      onLinkHover={onLinkHover}
      onNodeClick={onNodeClick}
      onLinkClick={onLinkClick}
    />
  );
}

// Group label shown in the node tooltip
const GROUP_LABELS = { 0: 'Extracted Entity', 1: 'Peripheral Entity', 3: 'Inferred Entity' };

// ── GraphVisualiser — inline card + expand modal ──────────────────
function GraphVisualiser({ graphData, title }) {
  const containerRef  = useRef(null);
  const modalRef      = useRef(null);
  const inlineFgRef   = useRef(null);
  const modalFgRef    = useRef(null);
  const [dims,        setDims]      = useState({ width: 400, height: 300 });
  const [modalDims,   setModalDims] = useState({ width: 800, height: 600 });
  const [expanded,      setExpanded]      = useState(false);
  const [selectedNode,  setSelectedNode]  = useState(null);
  const [selectedLink,  setSelectedLink]  = useState(null);

  // Measure inline container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setDims({ width: el.offsetWidth, height: el.offsetHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Measure modal container when open
  useEffect(() => {
    if (!expanded) return;
    const el = modalRef.current;
    if (!el) return;
    // Small delay so the DOM has painted before measuring
    const id = setTimeout(() => {
      setModalDims({ width: el.offsetWidth, height: el.offsetHeight });
    }, 50);
    const ro = new ResizeObserver(() => setModalDims({ width: el.offsetWidth, height: el.offsetHeight }));
    ro.observe(el);
    return () => { clearTimeout(id); ro.disconnect(); };
  }, [expanded]);

  // Close modal on Escape key
  useEffect(() => {
    if (!expanded) return;
    const handler = (e) => { if (e.key === 'Escape') setExpanded(false); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [expanded]);

  // Clear selection when modal closes
  useEffect(() => {
    if (!expanded) { setSelectedNode(null); setSelectedLink(null); }
  }, [expanded]);

  return (
    <>
      {/* ── Inline card ───────────────────────────────────────── */}
      <div className="relative" ref={containerRef}
        style={{ width: '100%', height: '300px', background: '#ffffff', borderRadius: '2px', overflow: 'hidden', border: '1px solid #E2E8F0' }}
      >
        <GraphCanvas width={dims.width} height={dims.height} graphData={graphData} fgRef={inlineFgRef} />

        {/* Expand button — top right corner */}
        <button
          onClick={() => setExpanded(true)}
          title="Expand graph"
          className="
            absolute top-2 right-2
            rounded-sm px-2 py-1
            font-mono text-[10px] uppercase tracking-wider
            bg-slate-800 text-white/70 border border-slate-600
            hover:bg-slate-900 hover:text-white transition-colors duration-150
            flex items-center gap-1
          "
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M4 8V4m0 0h4M4 4l5 5m11-5h-4m4 0v4m0-4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
          Expand
        </button>
      </div>

      {/* ── Full-screen modal ─────────────────────────────────── */}
      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)' }}
          onClick={(e) => { if (e.target === e.currentTarget) setExpanded(false); }}
        >
          <div
            className="glass-block rounded-sm flex flex-col"
            style={{ width: '92vw', height: '88vh' }}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/10 shrink-0">
              <div>
                <p className="font-mono text-[10px] text-white/40 uppercase tracking-widest">Knowledge Graph</p>
                <p className="font-grotesk font-semibold text-white text-sm">{title}</p>
              </div>
              <div className="flex items-center gap-3">
                {/* Legend */}
                <div className="flex gap-4">
                  <span className="flex items-center gap-1.5 font-mono text-[10px] text-white/50">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#60A5FA' }} /> Entity
                  </span>
                  <span className="flex items-center gap-1.5 font-mono text-[10px] text-white/50">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#93C5FD' }} /> Peripheral
                  </span>
                  <span className="flex items-center gap-1.5 font-mono text-[10px] text-white/50">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#6EE7B7' }} /> Inferred
                  </span>
                  <span className="flex items-center gap-1.5 font-mono text-[10px] text-[#10B981]/80">
                    — Inferred edge
                  </span>
                </div>
                {/* Close button */}
                <button
                  onClick={() => setExpanded(false)}
                  className="font-mono text-[10px] text-white/50 uppercase tracking-widest border border-white/20 px-3 py-1.5 rounded-sm hover:text-white hover:border-white/50 transition-colors duration-150"
                >
                  ✕ Close
                </button>
              </div>
            </div>

            {/* Modal graph canvas + overlaid panels — wrapper is relative so
                panels can be positioned absolutely over the canvas */}
            <div className="flex-1 relative" style={{ minHeight: 0 }}>
              {/* Canvas fill — no overflow-hidden so panels aren't clipped */}
              <div ref={modalRef} className="absolute inset-0" style={{ background: '#ffffff' }}>
                <GraphCanvas
                  width={modalDims.width}
                  height={modalDims.height}
                  graphData={graphData}
                  fgRef={modalFgRef}
                  onNodeClick={(node) => { setSelectedNode(node); setSelectedLink(null); }}
                  onLinkClick={(link) => { setSelectedLink(link); setSelectedNode(null); }}
                />
              </div>

              {/* ── Entity name — top-left on node click ─────── */}
              {selectedNode && (
                <div className="absolute top-3 left-3 w-72 rounded-sm border border-slate-200 bg-white shadow-xl z-20 overflow-hidden pointer-events-auto">
                  <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-slate-400">
                      {GROUP_LABELS[selectedNode.group] ?? 'Entity'}
                    </p>
                    <button
                      onClick={() => setSelectedNode(null)}
                      className="font-mono text-[10px] text-slate-400 hover:text-slate-700 transition-colors leading-none"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="px-3 py-3">
                    <p className="font-mono text-sm font-semibold text-slate-800 leading-snug break-words">
                      {selectedNode.id}
                    </p>
                  </div>
                </div>
              )}

              {/* ── Relationship triple — top-left on edge click ── */}
              {selectedLink && (() => {
                const src = typeof selectedLink.source === 'object' ? selectedLink.source.id : selectedLink.source;
                const tgt = typeof selectedLink.target === 'object' ? selectedLink.target.id : selectedLink.target;
                return (
                  <div className="absolute top-3 left-3 w-80 rounded-sm border border-slate-200 bg-white shadow-xl z-20 overflow-hidden pointer-events-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200">
                      <p className="font-mono text-[9px] uppercase tracking-widest text-slate-400">
                        {selectedLink.inferred ? 'Inferred Relationship' : 'Relationship'}
                      </p>
                      <button
                        onClick={() => setSelectedLink(null)}
                        className="font-mono text-[10px] text-slate-400 hover:text-slate-700 transition-colors leading-none"
                      >
                        ✕
                      </button>
                    </div>

                    <div className="px-3 py-3 flex flex-col gap-2.5 max-h-80 overflow-y-auto">
                      {/* Triple */}
                      <div>
                        <p className="font-mono text-[9px] uppercase tracking-widest text-slate-400 mb-0.5">Subject</p>
                        <p className="font-mono text-xs font-semibold text-slate-800 break-words leading-snug">{src}</p>
                      </div>
                      <div>
                        <p className="font-mono text-[9px] uppercase tracking-widest text-slate-400 mb-0.5">Predicate</p>
                        <p className="font-mono text-xs font-semibold text-blue-600 break-words leading-snug">{selectedLink.label}</p>
                      </div>
                      <div>
                        <p className="font-mono text-[9px] uppercase tracking-widest text-slate-400 mb-0.5">Object</p>
                        <p className="font-mono text-xs font-semibold text-slate-800 break-words leading-snug">{tgt}</p>
                      </div>

                      {/* Source sentences — only present on extracted (non-inferred) edges */}
                      {selectedLink.proposition_sentence && (
                        <div className="border-t border-slate-100 pt-2.5">
                          <p className="font-mono text-[9px] uppercase tracking-widest text-slate-400 mb-0.5">Proposition Sentence</p>
                          <p className="font-mono text-xs text-slate-700 leading-relaxed break-words">{selectedLink.proposition_sentence}</p>
                        </div>
                      )}
                      {selectedLink.coreferenced_sentence && (
                        <div>
                          <p className="font-mono text-[9px] uppercase tracking-widest text-slate-400 mb-0.5">Coreferenced Sentence</p>
                          <p className="font-mono text-xs text-slate-700 leading-relaxed break-words">{selectedLink.coreferenced_sentence}</p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Modal footer hint */}
            <div className="px-5 py-2 border-t border-white/10 shrink-0">
              <p className="font-mono text-[10px] text-white/25">
                Scroll to zoom · Drag to pan · Click node or edge for details · Press Esc to close
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/* ══════════════════════════════════════════════════════════════════
   MAIN PAGE COMPONENT
   ══════════════════════════════════════════════════════════════════ */

export default function KnowledgeGraphPage() {
  const [abstract,      setAbstract]      = useState('');
  const [stage,         setStage]         = useState(0);
  const [pipelineData,  setPipelineData]  = useState(null); // raw API response
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState(null);
  const [demoDropOpen,  setDemoDropOpen]  = useState(false);
  const demoDropRef = useRef(null);

  // Close demo dropdown when clicking outside.
  useEffect(() => {
    function handleClickOutside(e) {
      if (demoDropRef.current && !demoDropRef.current.contains(e.target)) {
        setDemoDropOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ── Handlers ────────────────────────────────────────────────────

  const handleLoadDemo = (text) => {
    setAbstract(text);
    setDemoDropOpen(false);
  };

  const handleReset = () => {
    setAbstract('');
    setStage(0);
    setPipelineData(null);
    setError(null);
  };

  // Fires the full pipeline. Stages 2 and 3 just reveal already-loaded data.
  const handleRunPipeline = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await axios.post(PIPELINE_URL, { paragraph: abstract }, { headers: API_HEADERS });
      setPipelineData(data);
      setStage(1);
    } catch (err) {
      setError(
        err.response?.data?.error
          ?? 'Could not reach the backend. Make sure the Django server is running on port 8000.'
      );
    } finally {
      setLoading(false);
    }
  };

  // ── Derived data (computed only when pipelineData is available) ─

  const propositions    = pipelineData?.results?.map(r => r.proposition_sentence)    ?? [];
  const coreferences    = pipelineData?.results?.map(r => r.coreferenced_sentence)   ?? [];
  const allQuadItems    = pipelineData ? extractAllQuads(pipelineData.results)        : [];
  const inferredItems   = pipelineData?.new_inferred_quadruples                      ?? [];
  const ontoEntities    = pipelineData?.ontological_entities                         ?? [];

  // Triples table rows for Stage 2.
  const triples = allQuadItems.map(item => ({
    subject:   item.quadruple.subject.name,
    predicate: item.quadruple.predicate,
    object:    item.quadruple.object.name,
  }));

  // Inferred relationship rows for Stage 3.
  const inferredTriples = inferredItems.map(item => ({
    subject:   item.quadruple.subject.name,
    predicate: item.quadruple.predicate,
    object:    item.quadruple.object.name,
  }));

  // Graph data for Stage 2 (extracted only — floating islands visible).
  const intermediateGraph = buildGraphData(allQuadItems);

  // Graph data for Stage 3 (extracted + inferred — all islands connected).
  const connectedGraph = buildGraphData(allQuadItems, inferredItems);

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div
      className="min-h-screen relative"
      style={{
        backgroundImage:    `url(${backgroundImage})`,
        backgroundSize:     'cover',
        backgroundPosition: 'center',
      }}
    >
      <Header />
      <div className="absolute inset-0 bg-black/40" />

      <main className="relative z-10 px-6 py-24 flex justify-center">
        <div className="w-full max-w-5xl flex flex-col gap-1">

          {/* ── Page heading ─────────────────────────────────────── */}
          <div className="mb-3">
            <p className="font-mono text-xs tracking-[0.2em] uppercase text-white/40">Demo Pipeline</p>
            <h1 className="font-grotesk font-bold text-2xl text-white tracking-wide uppercase">
              Knowledge Graph Generation
            </h1>
          </div>

          {/* ══════════════════════════════════════════════════════
              INPUT BLOCK
              ══════════════════════════════════════════════════════ */}
          <InfoBlock>
            <BlockLabel text="Input — Biomedical Abstract" />
            <textarea
              value={abstract}
              onChange={e => setAbstract(e.target.value)}
              placeholder="Paste a biomedical abstract here, or load the demo abstract below…"
              rows={5}
              className="
                w-full bg-transparent resize-none
                font-mono text-sm text-white/85
                border border-white/20 rounded-sm p-3
                placeholder-white/25
                focus:outline-none focus:border-white/50
                transition-colors duration-150
              "
            />

            {/* Error message */}
            {error && (
              <p className="font-mono text-xs text-red-400/80 mt-2 border border-red-400/20 rounded-sm px-3 py-2">
                {error}
              </p>
            )}

            <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
              <div className="flex gap-2 items-center">

                {/* Demo abstract dropdown */}
                <div className="relative" ref={demoDropRef}>
                  <button
                    onClick={() => setDemoDropOpen(prev => !prev)}
                    disabled={loading}
                    className={`
                      flex items-center gap-1.5
                      font-mono text-xs tracking-wider uppercase
                      px-4 py-2 rounded-sm border
                      transition-all duration-200
                      ${loading
                        ? 'opacity-30 cursor-not-allowed border-white/20 text-white/30'
                        : 'border-white/50 text-white hover:bg-white/10 cursor-pointer'
                      }
                    `}
                  >
                    Load Demo Abstract
                    <svg
                      className={`w-3 h-3 transition-transform duration-200 ${demoDropOpen ? 'rotate-180' : ''}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {demoDropOpen && (
                    <div className="absolute left-0 mt-2 z-20 glass-block rounded-sm py-1 min-w-[280px] flex flex-col">
                      {DEMO_ABSTRACTS.map((demo) => (
                        <button
                          key={demo.pubid}
                          onClick={() => handleLoadDemo(demo.text)}
                          className="text-left px-4 py-2 font-mono text-xs text-white/70 hover:text-white hover:bg-white/10 transition-colors duration-150"
                        >
                          {demo.label}
                          <span className="block text-[10px] text-white/30 mt-0.5">PubMed ID: {demo.pubid}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {stage > 0 && (
                  <ActionButton label="Reset Pipeline" onClick={handleReset} disabled={loading} />
                )}
              </div>
              <ActionButton
                label={loading ? 'Running pipeline…' : 'Run Preprocessing →'}
                onClick={handleRunPipeline}
                disabled={!abstract.trim() || stage >= 1 || loading}
              />
            </div>

            {/* Loading indicator */}
            {loading && (
              <div className="mt-4 flex items-center gap-3">
                {/* Animated pulse bar */}
                <div className="flex gap-1">
                  {[0, 1, 2, 3].map(i => (
                    <div
                      key={i}
                      className="w-1 h-4 bg-white/40 rounded-full animate-pulse"
                      style={{ animationDelay: `${i * 150}ms` }}
                    />
                  ))}
                </div>
                <p className="font-mono text-xs text-white/50">
                  Running full pipeline — this may take a few minutes while the LLM processes each sentence…
                </p>
              </div>
            )}
          </InfoBlock>

          <PipelineConnector stageNumber={1} />

          {/* ══════════════════════════════════════════════════════
              STAGE 1 — PREPROCESSING
              ══════════════════════════════════════════════════════ */}
          <InfoBlock className={stage < 1 ? 'opacity-40 pointer-events-none select-none' : ''}>
            <div className="flex items-center justify-between">
              <BlockLabel text="Stage 1 — Preprocessing" />
              {stage < 1 && (
                <span className="font-mono text-[10px] text-white/30 uppercase tracking-widest mb-3">Locked</span>
              )}
            </div>

            {stage >= 1 ? (
              <>
                <div className="flex flex-col md:flex-row gap-4">

                  {/* Proposition chunks */}
                  <div className="md:w-1/2 flex flex-col">
                    <PanelLabel text={`Proposition Chunks — ${propositions.length} propositions`} />
                    <div className="overflow-y-scroll flex-1 max-h-52 pr-2 scrollbar-visible space-y-1">
                      {propositions.map((prop, i) => (
                        <div key={i} className="flex gap-2 items-start border-b border-white/5 pb-1">
                          <span className="font-mono text-[10px] text-white/30 mt-0.5 w-4 shrink-0">{i + 1}.</span>
                          <p className="font-mono text-xs text-white/80 leading-relaxed">{prop}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Coreference resolution */}
                  <div className="md:w-1/2 flex flex-col">
                    <PanelLabel text="Coreference Resolution" />
                    <div className="overflow-y-scroll flex-1 max-h-52 pr-2 scrollbar-visible space-y-1">
                      {coreferences.map((sentence, i) => (
                        <div key={i} className="flex gap-2 items-start border-b border-white/5 pb-1">
                          <span className="font-mono text-[10px] text-white/30 mt-0.5 w-4 shrink-0">{i + 1}.</span>
                          <p className="font-mono text-xs text-white/80 leading-relaxed">{sentence}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
                <div className="flex justify-end mt-4">
                  <ActionButton
                    label="Run Information Extraction →"
                    onClick={() => setStage(2)}
                    disabled={stage >= 2}
                  />
                </div>
              </>
            ) : (
              <p className="font-mono text-xs text-white/25 text-center py-8">
                Complete the input step to unlock this stage.
              </p>
            )}
          </InfoBlock>

          <PipelineConnector stageNumber={2} />

          {/* ══════════════════════════════════════════════════════
              STAGE 2 — INFORMATION EXTRACTION
              Triples are sentence-local, so entities that never share
              a sentence produce floating islands in the intermediate KG.
              ══════════════════════════════════════════════════════ */}
          <InfoBlock className={stage < 2 ? 'opacity-40 pointer-events-none select-none' : ''}>
            <div className="flex items-center justify-between">
              <BlockLabel text="Stage 2 — Information Extraction" />
              {stage < 2 && (
                <span className="font-mono text-[10px] text-white/30 uppercase tracking-widest mb-3">Locked</span>
              )}
            </div>

            {stage >= 2 ? (
              <>
                <div className="flex flex-col md:flex-row gap-4">

                  {/* Triples table */}
                  <div className="md:w-1/2 flex flex-col">
                    <PanelLabel text={`Extracted Triples — ${triples.length} triples`} />
                    <div className="overflow-y-scroll max-h-64 scrollbar-visible">
                      <table className="w-full font-mono text-xs">
                        <thead>
                          <tr className="text-white/35 border-b border-white/15">
                            <th className="text-left py-1.5 pr-3 font-normal">Subject</th>
                            <th className="text-left py-1.5 pr-3 font-normal">Predicate</th>
                            <th className="text-left py-1.5 font-normal">Object</th>
                          </tr>
                        </thead>
                        <tbody>
                          {triples.map((t, i) => (
                            <tr key={i} className="border-b border-white/5 text-white/75">
                              <td className="py-1.5 pr-3">{t.subject}</td>
                              <td className="py-1.5 pr-3 text-white/45 italic">{t.predicate}</td>
                              <td className="py-1.5">{t.object}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Intermediate KG — floating islands visible */}
                  <div className="md:w-1/2 flex flex-col">
                    <PanelLabel text="Intermediate Knowledge Graph — floating islands" />
                    <GraphVisualiser graphData={intermediateGraph} title="Intermediate Knowledge Graph" />
                  </div>

                </div>
                <div className="flex justify-end mt-4">
                  <ActionButton
                    label="Run Post-processing →"
                    onClick={() => setStage(3)}
                    disabled={stage >= 3}
                  />
                </div>
              </>
            ) : (
              <p className="font-mono text-xs text-white/25 text-center py-8">
                Complete preprocessing to unlock this stage.
              </p>
            )}
          </InfoBlock>

          <PipelineConnector stageNumber={3} />

          {/* ══════════════════════════════════════════════════════
              STAGE 3 — POST-PROCESSING
              Step A: Relationship inference bridges floating islands
                      into a single connected abstract KG.
              Step B: Ontological entity identification selects the
                      canonical entities ready for global KG integration.
              ══════════════════════════════════════════════════════ */}
          <InfoBlock className={stage < 3 ? 'opacity-40 pointer-events-none select-none' : ''}>
            <div className="flex items-center justify-between">
              <BlockLabel text="Stage 3 — Post-processing" />
              {stage < 3 && (
                <span className="font-mono text-[10px] text-white/30 uppercase tracking-widest mb-3">Locked</span>
              )}
            </div>

            {stage >= 3 ? (
              <div className="flex flex-col gap-5">

                {/* ── Step A: Relationship Inference ────────────── */}
                <div className="flex flex-col md:flex-row gap-4">

                  {/* Inferred triples */}
                  <div className="md:w-1/2 flex flex-col">
                    <PanelLabel text={`Step A — Inferred Relationships (${inferredTriples.length} inferred)`} />
                    <div className="overflow-y-scroll max-h-52 pr-2 scrollbar-visible space-y-2">
                      {inferredTriples.length > 0 ? inferredTriples.map((r, i) => (
                        <div key={i} className="flex items-center gap-2 font-mono text-xs flex-wrap border-b border-white/10 pb-2">
                          <span className="text-white/80">{r.subject}</span>
                          <span className="text-white/35 italic">{r.predicate}</span>
                          <span className="text-white/80">{r.object}</span>
                          <span className="ml-auto font-mono text-[10px] text-[#34d399]/70 border border-[#34d399]/30 px-1.5 py-0.5 rounded-sm shrink-0">
                            inferred
                          </span>
                        </div>
                      )) : (
                        <p className="font-mono text-xs text-white/30 py-4">No inferred relationships generated.</p>
                      )}
                    </div>
                  </div>

                  {/* Connected KG */}
                  <div className="md:w-1/2 flex flex-col">
                    <PanelLabel text="Connected Abstract Knowledge Graph" />
                    <GraphVisualiser graphData={connectedGraph} title="Connected Abstract Knowledge Graph" />
                  </div>

                </div>

                {/* Divider */}
                <div className="border-t border-white/10" />

                {/* ── Step B: Ontological Entity Identification ──── */}
                <div className="flex flex-col">
                  <PanelLabel text={`Step B — Ontological Entities for Global KG (${ontoEntities.length} identified)`} />
                  {ontoEntities.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {ontoEntities.map((entity, i) => (
                        <span
                          key={i}
                          className="font-mono text-xs text-white/80 border border-white/20 px-2 py-1 rounded-sm"
                        >
                          {entity}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="font-mono text-xs text-white/30">No ontological entities identified.</p>
                  )}
                  <div className="mt-4 flex justify-end">
                    <span className="font-mono text-xs tracking-widest uppercase border border-white/30 text-white/50 px-3 py-1 rounded-sm">
                      ✓ Abstract KG ready for global knowledge graph integration
                    </span>
                  </div>
                </div>

              </div>
            ) : (
              <p className="font-mono text-xs text-white/25 text-center py-8">
                Complete information extraction to unlock this stage.
              </p>
            )}
          </InfoBlock>

        </div>
      </main>
    </div>
  );
}
