"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, User, Bot, MessageSquare, Trash2, Plus } from "lucide-react";
import { fetchOwnerChatThreads, deleteOwnerChatThread, sendOwnerChatMessage } from "@/lib/api-client";
import type { OwnerChatThread } from "@/lib/types";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: Date;
}

export default function ChatClient() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [threads, setThreads] = useState<OwnerChatThread[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [isLoadingThreads, setIsLoadingThreads] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    loadThreads();
  }, []);

  const loadThreads = async () => {
    setIsLoadingThreads(true);
    try {
      const response = await fetchOwnerChatThreads();
      setThreads(response.threads || []);
      
      if (response.threads && response.threads.length > 0 && !selectedThreadId) {
        setSelectedThreadId(response.threads[0].thread_id);
      } else if (!response.threads || response.threads.length === 0) {
        const newThreadId = `owner-thread-${Date.now()}`;
        setSelectedThreadId(newThreadId);
      }
    } catch (error) {
      console.error("Failed to load threads:", error);
      const newThreadId = `owner-thread-${Date.now()}`;
      setSelectedThreadId(newThreadId);
    } finally {
      setIsLoadingThreads(false);
    }
  };

  const handleCreateNewThread = () => {
    const newThreadId = `owner-thread-${Date.now()}`;
    setSelectedThreadId(newThreadId);
    setMessages([]);
  };

  const handleSwitchThread = (threadId: string) => {
    setSelectedThreadId(threadId);
    setMessages([]);
  };

  const handleDeleteThread = async (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (!confirm("Are you sure you want to delete this thread?")) {
      return;
    }

    try {
      await deleteOwnerChatThread(threadId);
      
      setThreads(prev => prev.filter(t => t.thread_id !== threadId));
      
      if (selectedThreadId === threadId) {
        const remainingThreads = threads.filter(t => t.thread_id !== threadId);
        if (remainingThreads.length > 0) {
          setSelectedThreadId(remainingThreads[0].thread_id);
        } else {
          handleCreateNewThread();
        }
      }
    } catch (error: any) {
      alert(`Failed to delete thread: ${error.message}`);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const threadId = selectedThreadId || `owner-thread-${Date.now()}`;

      if (!selectedThreadId) {
        setSelectedThreadId(threadId);
      }

      const data = await sendOwnerChatMessage({
        raw_message: userMessage.content,
        thread_id: threadId,
      });
      
      const agentMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "agent",
        content: data.reply_text || "No reply generated.",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, agentMessage]);
      
      loadThreads();
    } catch (error: any) {
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "agent",
        content: `Error: ${error.message || "Failed to communicate with agent."}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      <div className="w-72 flex flex-col rounded-xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-zinc-200 px-4 py-3 bg-zinc-50/50 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-900">Conversations</h3>
          <button
            onClick={handleCreateNewThread}
            className="p-1.5 rounded-lg hover:bg-zinc-100 transition"
            title="New conversation"
          >
            <Plus className="h-4 w-4 text-zinc-600" />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto">
          {isLoadingThreads ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
            </div>
          ) : threads.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <MessageSquare className="h-8 w-8 text-zinc-300 mx-auto mb-2" />
              <p className="text-sm text-zinc-500">No conversations yet</p>
              <p className="text-xs text-zinc-400 mt-1">Start a new chat</p>
            </div>
          ) : (
            <div className="py-2">
              {threads.map((thread) => (
                <button
                  key={thread.thread_id}
                  onClick={() => handleSwitchThread(thread.thread_id)}
                  className={`w-full px-4 py-3 text-left hover:bg-zinc-50 transition border-l-2 flex items-start justify-between gap-2 group ${
                    selectedThreadId === thread.thread_id
                      ? "bg-sky-50 border-sky-500"
                      : "border-transparent"
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-zinc-900 truncate">
                      {thread.title || "New conversation"}
                    </div>
                    <div className="text-xs text-zinc-500 mt-0.5">
                      {thread.message_count} message{thread.message_count !== 1 ? "s" : ""}
                      {thread.last_message_at && (
                        <> · {new Date(thread.last_message_at).toLocaleDateString()}</>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDeleteThread(thread.thread_id, e)}
                    className="shrink-0 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 transition-opacity"
                    title="Delete thread"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-red-600" />
                  </button>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col rounded-xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-zinc-200 px-6 py-4 bg-zinc-50/50">
          <h2 className="text-lg font-semibold text-zinc-900">Chat to Agent</h2>
          <p className="text-sm text-zinc-500">Unrestricted access to your business orchestration agent.</p>
        </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-zinc-50/30">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center">
            <div className="max-w-md">
              <Bot className="mx-auto h-12 w-12 text-zinc-300" />
              <h3 className="mt-4 text-base font-medium text-zinc-900">Welcome to Owner Chat</h3>
              <p className="mt-2 text-sm text-zinc-500">
                You have unrestricted access to your business data. Ask about margins, costs, inventory, or request operational insights.
              </p>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border ${msg.role === "user" ? "bg-sky-100 border-sky-200" : "bg-indigo-100 border-indigo-200"}`}>
                {msg.role === "user" ? <User className="h-5 w-5 text-sky-700" /> : <Bot className="h-5 w-5 text-indigo-700" />}
              </div>
              <div className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"} max-w-[75%]`}>
                <div className={`rounded-2xl px-5 py-3 text-sm ${msg.role === "user" ? "bg-sky-600 text-white" : "bg-white border border-zinc-200 text-zinc-800 shadow-sm"}`}>
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                </div>
                <span className="mt-1 text-xs text-zinc-400">
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))
        )}
        
        {isLoading && (
          <div className="flex gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border bg-indigo-100 border-indigo-200">
              <Bot className="h-5 w-5 text-indigo-700" />
            </div>
            <div className="flex items-center rounded-2xl border border-zinc-200 bg-white px-5 py-3 shadow-sm">
              <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
              <span className="ml-2 text-sm text-zinc-500">Agent is thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-zinc-200 p-4 bg-white">
        <form onSubmit={handleSubmit} className="flex gap-4">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask your agent anything..."
            disabled={isLoading}
            className="flex-1 rounded-xl border border-zinc-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-sky-500 focus:ring-1 focus:ring-sky-500 disabled:bg-zinc-50 disabled:text-zinc-500"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="flex items-center justify-center rounded-xl bg-zinc-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
      </div>
    </div>
  );
}
