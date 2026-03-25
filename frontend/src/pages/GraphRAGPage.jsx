// src/pages/GraphRAGPage.jsx
//
// Page for the GraphRAG (Graph Retrieval Augmented Generation) section of the demo.
// Blank canvas — add components here as the demo is built out.

import React from 'react';
import Header from '../components/Header';
import backgroundImage from '../assets/background1.jpg';
import '../styles/tailwind.css';

export default function GraphRAGPage() {
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

      <main className="relative z-10 flex items-center justify-center min-h-screen px-6 py-24">
        {/* Content goes here */}
      </main>
    </div>
  );
}
