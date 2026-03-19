// src/pages/ConversationsPage.jsx

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import backgroundImage from '../assets/background.jpg';
import Header from '../components/Header';

export default function ConversationsPage() {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const AUTH_TOKEN = '649ad111031dae78f9fdf80fce9ad07fbeaca812';

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const res = await axios.get('/api/conversations/', {
          headers: {
            Authorization: `Token ${AUTH_TOKEN}`,
          },
        });
        setConversations(res.data);
      } catch (error) {
        console.error('Failed to fetch conversations:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchConversations();
  }, []);

  const handleNewConversation = () => {
    navigate(`/qa/`);
  };
  

  return (
    <div
      className="relative h-screen flex flex-col"
      style={{
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* Background overlay */}
      <div className="absolute inset-0 bg-white bg-opacity-20 backdrop-blur-lg" />

      {/* Foreground */}
      <div className="relative z-10 flex flex-col flex-1">
        <div className="h-24">
          <Header />
        </div>

        <div className="flex-1 px-8 py-4 text-white overflow-auto">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-3xl font-bold">Conversations</h2>
            <button
              onClick={handleNewConversation}
              className="bg-white text-blue-600 px-4 py-2 rounded shadow hover:shadow-lg transition"
            >
              + New Conversation
            </button>
          </div>

          {loading ? (
            <p className="italic">Loading conversations...</p>
          ) : (
            <table className="w-full table-auto border border-white/30 rounded-md overflow-hidden bg-white/10 backdrop-blur text-white">
              <thead className="bg-white/20">
                <tr>
                  <th className="p-3 text-left">Conversation ID</th>
                  <th className="p-3 text-left">Questions</th>
                  <th className="p-3 text-left">Last Active</th>
                  <th className="p-3 text-left">Action</th>
                </tr>
              </thead>
              <tbody>
                {conversations.map((conv) => (
                  <tr key={conv.id} className="border-t border-white/20">
                    <td className="p-3">{conv.id}</td>
                    <td className="p-3">{conv.question_count}</td>
                    <td className="p-3">
                      {new Date(conv.updated_at).toLocaleString()}
                    </td>
                    <td className="p-3">
                      <button
                        onClick={() => navigate(`/qa/${conv.id}`)}
                        className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded transition"
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
