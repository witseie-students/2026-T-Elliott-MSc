// src/hooks/useWebSocket.js
import { useEffect, useRef } from 'react';

export default function useWebSocket(url, onMessage, initialMessage = null) {
  const socketRef = useRef(null);

  useEffect(() => {
    if (!url) return;

    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log('[WebSocket Open]', url);
      // 🔥 If an initialMessage is provided, send it immediately when connected
      if (initialMessage) {
        socket.send(JSON.stringify(initialMessage));
      }
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (err) {
        console.error('Error parsing message:', err);
      }
    };

    socket.onclose = () => {
      console.log('[WebSocket Closed]', url);
    };

    socket.onerror = (error) => {
      console.error('[WebSocket Error]', error);
    };

    return () => {
      socket.close();
    };
  }, [url, initialMessage]); // 🔥 Also re-run effect if initialMessage changes

  return socketRef.current;
}
