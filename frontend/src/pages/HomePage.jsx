// src/pages/HomePage.jsx

import React from 'react';
import { Link } from 'react-router-dom';
import backgroundImage from '../assets/background.jpg';
import '../styles/tailwind.css';

export default function HomePage() {
  return (
    <div
      className="relative flex items-center justify-center h-screen"
      style={{
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div
        className="absolute inset-0 bg-white bg-opacity-20 backdrop-blur-lg
                   flex flex-col items-center justify-center space-y-6
                   p-8 rounded-lg shadow-lg text-white text-center"
      >
        <h1 className="text-5xl font-bold">THE‑EVERYTHING‑ENGINE</h1>
        <p className="text-2xl italic">
          A Knowledge Graph Generation and Reasoning System
        </p>
        <p className="text-xl">Master&apos;s Dissertation</p>

        <div className="space-y-2 text-lg">
          <p>Author: Taine J. Elliott</p>
          <p>Supervisor: Dr. Martin Bekker</p>
          <p>Co‑Supervisors: Dr. Ken Nixon, Dr. Steven Levitt</p>
        </div>

        {/* ——— Redirects to conversations list instead of hardcoded QA page ——— */}
        <Link
          to="/conversations"
          className="
            inline-block px-6 py-2
            bg-white text-blue-600 font-medium
            rounded-md
            shadow-md hover:shadow-xl
            transition-shadow duration-200
            focus:outline-none focus:ring-2 focus:ring-blue-200 focus:ring-opacity-50
          "
        >
          View Conversations
        </Link>
      </div>
    </div>
  );
}
