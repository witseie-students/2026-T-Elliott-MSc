// src/pages/HomePage.jsx
//
// Landing page for the dissertation demo.
// Layout: full-screen background image with a frosted-glass overlay
// divided into retro-style info blocks:
//   ┌──────────────────────────────┐
//   │  HEADER (fixed, from Header) │
//   ├──────────────┬───────────────┤
//   │  TITLE BLOCK │  ABSTRACT     │
//   ├──────┬───────┴───────────────┤
//   │ STUD │  SUPERVISOR  │  CO-SV │
//   └──────┴──────────────┴────────┘
//
// Each named block uses the shared .glass-block + .block-accent
// utility classes defined in tailwind.css.

import React, { useRef, useState, useEffect } from 'react';
import backgroundImage from '../assets/background1.jpg';
import Header from '../components/Header';
import '../styles/tailwind.css';

/* ── Dissertation metadata ────────────────────────────────────────
   Update these constants to change displayed content without
   touching the layout JSX.
─────────────────────────────────────────────────────────────────── */
const META = {
  title:      'Addressing Biomedical Literature Overload through Knowledge Graph Generation and Agentic Reasoning',
  subtitle:   'A Knowledge Graph Generation and Reasoning System',
  type:       "Master's Dissertation",
  abstract:
    'Biomedical literature is growing at an unprecedented rate. As a result, researchers are likely to struggle ' +
    'keeping up with the growing volume. Current biomedical literature search tools retrieve large volumes of ' +
    'results, but lack the ability to deliver precise, context-aware answers. This work extends and contributes ' +
    'to research in information extraction for knowledge graph generation and knowledge graph retrieval augmented ' +
    'generation (graphRAG), with the goal of connecting all biomedical literature through units of knowledge. ' +
    'The work documents how a knowledge graph of propositions is built using 350 biomedical abstracts from the ' +
    'PubMedQA dataset. During construction, a back-translation methodology for validation was pioneered. Once ' +
    'constructed, questions derived from the dataset were answered using the knowledge graph with both ' +
    'single-iteration and recursive retrieval approaches. The system\'s performance was compared to a baseline ' +
    '(where the latter had access to the full context prior to graph generation). Through back-translation, the ' +
    'average cosine similarity between the reconstructed abstracts of propositions and the original abstracts ' +
    'was 0.913. The cosine similarity distribution was calibrated against the Semantic Textual Similarity ' +
    'Benchmark (STS-B), showing that reconstructed abstracts were completely equivalent to the original texts. ' +
    'Answers derived from the knowledge graph achieved 93.03% of the baseline F1 score with single-iteration ' +
    'retrieval, and 86.07% with recursive retrieval. This performance implies that knowledge graphs are capable ' +
    'of storing biomedical knowledge faithfully, and that they enable precise retrieval for effective reasoning. ' +
    'Ultimately, this dissertation demonstrates that biomedical literature can be captured in knowledge graph ' +
    'form, can effectively be reasoned with, signalling how researchers might better navigate vast quantities ' +
    'of biomedical knowledge.',
  student: {
    label:  'Student',
    name:   'Taine J. Elliott',
    degree: 'MSc Engineering - Artificial Intelligence',
    year:   '2026',
  },
  supervisor: {
    label: 'Main Supervisor',
    name:  'Dr. Martin Bekker',
  },
  coSupervisors: [
    { name: 'Dr. Ken Nixon'    },
    { name: 'Dr. Steven Levitt' },
  ],
};

/* ── Reusable block wrapper ───────────────────────────────────────
   Applies the glass + retro accent styling to any block section.
   `className` allows callers to control sizing/layout via Tailwind.
   `style` is forwarded for dynamic values (e.g. measured heights).
─────────────────────────────────────────────────────────────────── */
function InfoBlock({ className = '', style, forwardRef, children }) {
  return (
    <div
      ref={forwardRef}
      style={style}
      className={`glass-block block-accent rounded-sm p-5 ${className}`}
    >
      {children}
    </div>
  );
}

/* ── Small mono label ─────────────────────────────────────────────
   Uppercase monospace tag used above each block's content.
─────────────────────────────────────────────────────────────────── */
function BlockLabel({ text }) {
  return (
    <p className="font-mono text-xs tracking-[0.2em] uppercase text-white/50 mb-2">
      {text}
    </p>
  );
}

/* ── Page component ───────────────────────────────────────────────*/
export default function HomePage() {
  // Measure the project block's rendered height so the abstract block
  // can be capped to exactly the same height, making it scroll cleanly.
  const titleRef = useRef(null);
  const [titleHeight, setTitleHeight] = useState(null);

  useEffect(() => {
    const el = titleRef.current;
    if (!el) return;

    // ResizeObserver keeps the height in sync if the window is resized.
    // offsetHeight is used (not contentRect.height) so that padding and
    // border are included — giving the abstract block the full outer height.
    const ro = new ResizeObserver(() => {
      setTitleHeight(el.offsetHeight);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    /* Full-screen background */
    <div
      className="min-h-screen relative"
      style={{
        backgroundImage:    `url(${backgroundImage})`,
        backgroundSize:     'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* Fixed navigation header */}
      <Header />

      {/* Dark overlay — dims the photo so blocks read clearly */}
      <div className="absolute inset-0 bg-black/40" />

      {/* ── Main content — sits above the overlay ───────────────── */}
      <main className="relative z-10 flex items-center justify-center min-h-screen px-6 py-24">

        {/* Outer container — constrains max width for readability */}
        <div className="w-full max-w-5xl flex flex-col gap-4">

          {/* ── Row 1: Title + Abstract ──────────────────────────── */}
          {/* Both blocks sit side-by-side; abstract height is driven
              by the measured height of the title block via JS. */}
          <div className="flex flex-col md:flex-row md:items-start gap-4">

            {/* TITLE BLOCK — ref'd so its height can be measured */}
            <InfoBlock
              forwardRef={titleRef}
              className="md:w-2/5 flex flex-col justify-between"
            >
              <div>
                <BlockLabel text="Project" />
                <h1 className="font-grotesk font-bold text-3xl text-white leading-tight tracking-wide uppercase">
                  {META.title}
                </h1>
              </div>
              <div className="mt-4">
                <p className="font-mono text-sm italic text-white/80 leading-snug">
                  {META.subtitle}
                </p>
                <span className="
                  inline-block mt-3
                  font-mono text-xs tracking-widest uppercase
                  border border-white/40 text-white/60
                  px-2 py-0.5 rounded-sm
                ">
                  {META.type}
                </span>
              </div>
            </InfoBlock>

            {/* ABSTRACT BLOCK — height locked to title block height via
                inline style; scroll area fills remaining space inside. */}
            <InfoBlock
              className="md:w-3/5 flex flex-col"
              style={titleHeight ? { height: titleHeight } : undefined}
            >
              <BlockLabel text="Abstract" />
              {/* flex-1 fills height between label and block bottom;
                  overflow-y-scroll enables scrolling within that space. */}
              <div className="flex-1 overflow-y-scroll pr-2 scrollbar-visible">
                <p className="font-mono text-sm text-white/85 leading-relaxed">
                  {META.abstract}
                </p>
              </div>
            </InfoBlock>

          </div>

          {/* ── Row 2: Student + Supervisor + Co-Supervisors ─────── */}
          <div className="flex flex-col md:flex-row gap-4">

            {/* STUDENT BLOCK */}
            <InfoBlock className="md:w-1/3">
              <BlockLabel text={META.student.label} />
              <p className="font-grotesk font-semibold text-lg text-white">
                {META.student.name}
              </p>
              <p className="font-mono text-xs text-white/60 mt-1">
                {META.student.degree}
              </p>
              <p className="font-mono text-xs text-white/60">
                {META.student.year}
              </p>
            </InfoBlock>

            {/* MAIN SUPERVISOR BLOCK */}
            <InfoBlock className="md:w-1/3">
              <BlockLabel text={META.supervisor.label} />
              <p className="font-grotesk font-semibold text-lg text-white">
                {META.supervisor.name}
              </p>
            </InfoBlock>

            {/* CO-SUPERVISORS BLOCK */}
            <InfoBlock className="md:w-1/3">
              <BlockLabel text="Co‑Supervisors" />
              {META.coSupervisors.map((sv) => (
                <p
                  key={sv.name}
                  className="font-grotesk font-semibold text-lg text-white leading-snug"
                >
                  {sv.name}
                </p>
              ))}
            </InfoBlock>

          </div>

        </div>
      </main>
    </div>
  );
}
