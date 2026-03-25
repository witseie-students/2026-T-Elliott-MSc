// src/App.js

import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './styles/tailwind.css';

import HomePage          from './pages/HomePage';
import KnowledgeGraphPage from './pages/KnowledgeGraphPage';
import GraphRAGPage       from './pages/GraphRAGPage';

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/"                element={<HomePage />} />
          <Route path="/knowledge-graph" element={<KnowledgeGraphPage />} />
          <Route path="/graphrag"        element={<GraphRAGPage />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
