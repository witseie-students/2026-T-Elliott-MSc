// src/components/TreeOfThought.jsx

import React, { useState } from 'react';
import useWebSocket from '../hooks/useWebSocket';

function TreeNode({ node, depth = 0 }) {
  return (
    <div className="mb-4">
      <div className="flex">
        {Array.from({ length: depth }).map((_, i) => (
          <div key={i} className="border-l border-white/30 mr-2" style={{ width: '1rem' }} />
        ))}
        <div className="flex-1">
          {node.plan && (
            <div className="text-white font-semibold mb-1">
              📋 Plan: {node.plan}
            </div>
          )}
          {node.question && (
            <div className="text-white font-semibold">
              • {node.question}
            </div>
          )}
          <div className="text-sm italic text-gray-300 mt-1 ml-4">
            {node.status === 'thinking' && '🧠 Thinking...'}
            {node.status === 'answered' && `✅ ${node.answer}`}
            {node.status === 'error' && '❌ Error generating answer'}
          </div>
        </div>
      </div>

      {node.children && node.children.map((child, index) => (
        <TreeNode key={index} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

export default function TreeOfThought({ conversationId, questionId, questionText }) {
  const [root, setRoot] = useState(null);
  const [expanded, setExpanded] = useState(true);

  const wsUrl = conversationId && questionId
    ? `ws://localhost:8001/ws/tot/${conversationId}/${questionId}/`
    : null;

  useWebSocket(
    wsUrl,
    (data) => {
      console.log('[WebSocket Message]', data);
      setRoot(prev => updateTree(prev, data, questionText));
    },
    questionText ? { question: questionText } : null
  );

  if (!root) {
    return <div className="text-gray-300 italic">Waiting for thoughts...</div>;
  }

  return (
    <div className="space-y-4 text-white">
      <div className="border border-white rounded-md">
        <button
          className="w-full text-left px-4 py-3 bg-white/10 hover:bg-white/20 transition font-semibold flex justify-between items-center"
          onClick={() => setExpanded(!expanded)}
        >
          <span>{questionText || root.question || 'Root Question'}</span>
          <span className="text-xl">{expanded ? '▲' : '▼'}</span>
        </button>

        {expanded && (
          <div className="p-4">
            <TreeNode node={root} />
          </div>
        )}
      </div>
    </div>
  );
}

function updateTree(prevRoot, data, questionText) {
  const root = prevRoot ?? {
    question: questionText || '',
    plan: '',
    status: 'thinking',
    children: [],
  };

  const { type, node, plan, q, a, ans, mode } = data;

  const path = node?.split('.').filter(x => x !== '') || [];

  const findNode = (current, path) => {
    if (path.length === 0) return current;
    const [first, ...rest] = path;
    const idx = parseInt(first, 10);
    if (!current.children[idx]) {
      current.children[idx] = {
        question: '',
        plan: '',
        status: 'thinking',
        children: [],
      };
    }
    return findNode(current.children[idx], rest);
  };

  const target = findNode(root, path);

  if (type === 'plan') {
    target.plan = plan;
  } else if (type === 'question') {
    target.question = q;
    target.status = 'thinking';
  } else if (type === 'answer') {
    target.answer = a;
    target.status = 'answered';
  } else if (type === 'final') {
    target.answer = ans;
    target.status = 'answered';
  } else if (type === 'branch' && mode === 'multi' && !target.children.length) {
    target.children = [];
  }

  return structuredClone(root); // ensures React updates
}
