// src/components/Header.jsx

import React from 'react';
import { Link } from 'react-router-dom';

function Header() {
  return (
    <header className="text-white py-2 px-8 h-full flex flex-col justify-center">
      <div className="flex justify-between items-center">
        <Link to="/" className="text-white no-underline hover:text-gray-300 transition duration-300">
          <h1
            className="text-4xl font-extrabold tracking-wider"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}
          >
            THE-EVERYTHING-ENGINE
          </h1>
        </Link>
        <nav className="space-x-4">
          <Link to="/" className="text-lg font-medium hover:text-gray-300 transition duration-300">
            Home
          </Link>
          <Link to="/conversations" className="text-lg font-medium hover:text-gray-300 transition duration-300">
            Conversations
          </Link>
        </nav>
      </div>
      <hr className="border-t border-white mt-2" />
    </header>
  );
}

export default Header;
