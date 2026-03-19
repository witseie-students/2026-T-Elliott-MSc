// src/components/Conversation.jsx

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

function Conversation({ conversationId, onNewQuestion }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const navigate = useNavigate();

  const AUTH_TOKEN = '649ad111031dae78f9fdf80fce9ad07fbeaca812';

  useEffect(() => {
    if (!conversationId) return;
    const fetchMessages = async () => {
      try {
        const res = await axios.get(`/api/conversations/${conversationId}/questions/`, {
          headers: { Authorization: `Token ${AUTH_TOKEN}` },
        });

        const fetchedMessages = res.data.map((q) => ({
          role: 'user',
          text: q.text,
        }));

        setMessages(fetchedMessages);
      } catch (err) {
        console.error('Failed to fetch messages:', err);
      }
    };

    fetchMessages();
  }, [conversationId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', text: input };
    setMessages((prev) => [...prev, userMessage]);

    try {
      const res = await axios.post(
        '/api/ask-question/',
        {
          text: input,
          conversation_id: conversationId || undefined,
        },
        {
          headers: {
            Authorization: `Token ${AUTH_TOKEN}`,
            'Content-Type': 'application/json',
          },
        }
      );

      const { conversation_id, question_id } = res.data;

      if (!conversationId) {
        navigate(`/qa/${conversation_id}`);
      }

      // 🔥 PASS BOTH question_id and input to parent
      if (onNewQuestion) {
        onNewQuestion(question_id, input);
      }

      const placeholder = {
        role: 'system',
        text: `🧠 Thinking... (question: ${question_id})`,
      };

      setMessages((prev) => [...prev, placeholder]);
      setInput('');
    } catch (err) {
      console.error('Failed to submit question:', err);
      const errorMsg = {
        role: 'system',
        text: '❌ Error submitting your question. Please try again.',
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  };

  return (
    <div className="w-full h-full border border-white rounded-md flex flex-col justify-between p-4 bg-slate-800/30 backdrop-blur-md text-white">
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg, idx) => (
          <div key={idx} className="w-full">
            {msg.role === 'user' ? (
              <div className="bg-white text-black rounded-lg px-4 py-2 max-w-[85%] ml-auto">
                {msg.text}
              </div>
            ) : (
              <p className="mt-1 ml-2">{msg.text}</p>
            )}
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="mt-4">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question..."
          className="w-full px-4 py-2 rounded-md bg-gray-200 text-black placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </form>
    </div>
  );
}

export default Conversation;
