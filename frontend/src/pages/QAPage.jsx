// src/pages/QAPage.jsx

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import backgroundImage from '../assets/background.jpg';
import '../styles/tailwind.css';

import Header from '../components/Header';
import Conversation from '../components/Conversation';
import TreeOfThought from '../components/TreeOfThought';
import Memory from '../components/Memory';

export default function QAPage() {
  const { conversationId } = useParams();
  const [isTreeOpen, setIsTreeOpen] = useState(true);
  const [currentQuestionId, setCurrentQuestionId] = useState(null);
  const [currentQuestionText, setCurrentQuestionText] = useState(''); // 🔥 New
  const memoryRef = useRef(null);

  useEffect(() => {
    const timeout = setTimeout(() => {
      memoryRef.current?.resize();
    }, 300);
    return () => clearTimeout(timeout);
  }, [isTreeOpen]);

  return (
    <div
      className="relative h-screen flex flex-col"
      style={{
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div className="absolute inset-0 bg-white bg-opacity-20 backdrop-blur-lg" />

      <div className="relative z-10 flex flex-col flex-1">
        <div className="h-24">
          <Header />
        </div>

        <div className="flex flex-1 pt-0 px-6 pb-6 gap-4">
          {/* Left column: Chat */}
          <div className="w-1/3 h-full">
            <Conversation
              conversationId={conversationId}
              onNewQuestion={(qid, qtext) => {
                setCurrentQuestionId(qid);
                setCurrentQuestionText(qtext); // 🔥 Save the input text too
              }}
            />
          </div>

          {/* Right side: Memory + collapsible TreeOfThought */}
          <div className="w-2/3 h-full border border-white rounded-md p-4 flex relative">
            <div className="flex-1 h-full overflow-y-auto">
              <Memory ref={memoryRef} />
            </div>

            <div
              className={`flex flex-col h-full transition-all duration-300 ${
                isTreeOpen ? 'w-64 ml-4' : 'w-16 ml-4'
              } bg-slate-800/30 rounded-md`}
            >
              <div className="flex items-center justify-between px-2 py-2 border-b border-white">
                {isTreeOpen ? (
                  <span className="text-sm font-semibold text-white ml-2">Tree of Thought</span>
                ) : (
                  <span
                    title="Tree of Thought"
                    className="text-white text-2xl flex justify-center items-center w-full"
                  >
                    🌲
                  </span>
                )}

                <button
                  onClick={() => setIsTreeOpen(!isTreeOpen)}
                  className="bg-white/20 hover:bg-white/30 text-white backdrop-blur-sm p-1 rounded transition focus:outline-none"
                  title={isTreeOpen ? 'Collapse Tree of Thought' : 'Expand Tree of Thought'}
                >
                  <span className="text-sm">{isTreeOpen ? '⮜' : '⮞'}</span>
                </button>
              </div>

              {/* Tree content */}
              {isTreeOpen && (
                <div className="p-3 overflow-y-auto flex-1 text-white">
                  <TreeOfThought
                    conversationId={conversationId}
                    questionId={currentQuestionId}
                    questionText={currentQuestionText} // 🔥 PASS IT IN
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
