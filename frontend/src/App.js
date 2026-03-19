// src/App.js

import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './styles/tailwind.css';

import HomePage from './pages/HomePage';
import QAPage from './pages/QAPage';
import ConversationsPage from './pages/ConversationsPage'; // ✅ NEW

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/qa" element={<QAPage />} /> {/* 🔥 no conversationId */}
          <Route path="/qa/:conversationId" element={<QAPage />} />
          <Route path="/conversations" element={<ConversationsPage />} /> {/* ✅ NEW route */}
        </Routes>
      </div>
    </Router>
  );
}

export default App;
