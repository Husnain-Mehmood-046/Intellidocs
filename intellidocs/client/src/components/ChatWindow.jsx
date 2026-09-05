/**
 * Chat window component (Redesigned - Pass 2).
 *
 * Features:
 * - Scrolling message list with user/assistant bubbles
 * - Input box + send button
 * - Citations as inline markers tied to expandable source panel
 * - Confidence as unified status bar (HIGH/MEDIUM/LOW)
 * - Clarification mode visually distinct from grounded answers
 * - Document upload zone with drag/drop, progress, success/error states
 * - Empty state with orientation prompts
 * - Multi-stage loading indicator (Retrieving → Reasoning → Finalizing)
 * - Chat history persistence across page reloads
 * - Week 3: Handles clarifications, shows route (RAG/tool), tool info
 * - Fixed: Hooks rules compliance (no useState in nested functions)
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { sendMessage, uploadDocument, fetchHistory } from "../api/chatApi";
import { useAuth } from "../context/AuthContext";

const LOADING_STAGES = [
  { key: "retrieving", label: "Retrieving relevant passages…" },
  { key: "reasoning", label: "Reasoning over sources…" },
  { key: "finalizing", label: "Finalizing answer…" },
];

export default function ChatWindow() {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null); // null | 'uploading' | 'success' | 'error'
  const [uploadResult, setUploadResult] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [openCitationPanels, setOpenCitationPanels] = useState({}); // Track open citation panels by message ID
  const [showAllCitations, setShowAllCitations] = useState({}); // Track "show all citations" per message ID
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const stageTimerRef = useRef(null);
  const messageListRef = useRef(null);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Scroll listener for "Scroll to bottom" button
  useEffect(() => {
    const messageList = messageListRef.current;
    if (!messageList) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = messageList;
      // Show button when scrolled up more than 200px from bottom
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 200;
      setShowScrollToBottom(!isNearBottom);
    };

    messageList.addEventListener("scroll", handleScroll, { passive: true });
    return () => messageList.removeEventListener("scroll", handleScroll);
  }, []);

  const handleScrollToBottom = useCallback(() => {
    const messageList = messageListRef.current;
    if (messageList) {
      messageList.scrollTo({ top: messageList.scrollHeight, behavior: "smooth" });
    }
    setShowScrollToBottom(false);
  }, []);

  const toggleCitationPanel = useCallback((messageId) => {
    setOpenCitationPanels(prev => ({ ...prev, [messageId]: !prev[messageId] }));
  }, []);

  const toggleShowAllCitations = useCallback((messageId) => {
    setShowAllCitations(prev => ({ ...prev, [messageId]: !prev[messageId] }));
  }, []);

  // Load chat history on mount
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const { messages: history } = await fetchHistory();
        if (history && history.length > 0) {
          const formattedMessages = history.map((msg) => {
            const base = {
              role: msg.role,
              content: msg.content,
              citations: msg.sources?.map((s) => ({
                source: s.filename,
                chunk_index: s.chunkIndex,
                excerpt: s.text,
              })) || [],
              confidence: msg.confidence,
            };
            
            if (msg.metadata?.type === "clarification") {
              return { ...base, isClarification: true };
            }
            
            if (msg.metadata?.route) {
              return { ...base, route: msg.metadata.route, tool_used: msg.metadata.tool_used, tool_args: msg.metadata.tool_args };
            }
            
            return base;
          });
          setMessages(formattedMessages);
        }
      } catch (err) {
        console.error("Failed to load chat history:", err);
      }
    };
    loadHistory();
  }, []);

  // Loading stage animation
  useEffect(() => {
    if (!loading) {
      setLoadingStage(0);
      if (stageTimerRef.current) {
        clearInterval(stageTimerRef.current);
        stageTimerRef.current = null;
      }
      return;
    }

    // Cycle through stages every ~1.5s
    stageTimerRef.current = setInterval(() => {
      setLoadingStage((prev) => (prev + 1) % LOADING_STAGES.length);
    }, 1500);

    return () => {
      if (stageTimerRef.current) {
        clearInterval(stageTimerRef.current);
        stageTimerRef.current = null;
      }
    };
  }, [loading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setLoading(true);
    setLoadingStage(0);

    // Add user message optimistically
    setMessages((prev) => [...prev, { role: "user", content: userMessage, citations: [] }]);

    try {
      const response = await sendMessage(userMessage);
      
      if (response.route === "clarify") {
        setMessages((prev) => [...prev, { 
          role: "assistant", 
          content: response.clarification, 
          citations: [], 
          confidence: "low",
          isClarification: true,
          route: "clarify",
        }]);
      } else {
        setMessages((prev) => [...prev, { 
          role: "assistant", 
          content: response.answer, 
          citations: response.citations || [], 
          confidence: response.confidence,
          route: response.route,
          tool_used: response.tool_used,
          tool_args: response.tool_args,
        }]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.message}`, citations: [], confidence: "low" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;

    setUploading(true);
    setUploadProgress("uploading");
    setUploadResult(null);

    try {
      const result = await uploadDocument(file);
      setUploadProgress("success");
      setUploadResult({ chunks: result.chunks, filename: file.name });
      // Reset after showing success
      setTimeout(() => {
        setUploadProgress(null);
        setUploadResult(null);
      }, 4000);
    } catch (err) {
      setUploadProgress("error");
      setUploadResult({ error: err.message });
      setTimeout(() => {
        setUploadProgress(null);
        setUploadResult(null);
      }, 6000);
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) handleFileUpload(file);
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  // Helper to render message content based on type
  const renderMessageContent = (msg) => {
    const isUser = msg.role === "user";
    const isClarification = msg.isClarification === true;
    const confidence = msg.confidence;
    const citations = msg.citations || [];
    const route = msg.route;
    const toolUsed = msg.tool_used;

    // Confidence badge config
    const confidenceConfig = {
      high: { label: "HIGH", bg: "var(--trust-high-bg)", color: "var(--trust-high)", dot: "var(--trust-high)" },
      medium: { label: "MEDIUM", bg: "var(--trust-medium-bg)", color: "var(--trust-medium)", dot: "var(--trust-medium)" },
      low: { label: "LOW", bg: "var(--trust-low-bg)", color: "var(--trust-low)", dot: "var(--trust-low)" },
    };

    const conf = confidenceConfig[confidence] || confidenceConfig.low;

    // Route badge
    const routeBadge = route && route !== "rag" ? (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "var(--space-1)",
          marginLeft: "var(--space-2)",
          padding: "var(--space-1) var(--space-2)",
          borderRadius: "var(--radius-sm)",
          fontSize: "var(--text-xs)",
          fontWeight: "var(--font-semibold)",
          fontFamily: "var(--font-sans)",
          textTransform: "uppercase",
          letterSpacing: "0.02em",
          background: route === "tool" ? "var(--accent-subtle)" : "var(--border)",
          color: route === "tool" ? "var(--accent)" : "var(--ink-muted)",
        }}
      >
        {route.toUpperCase()}
        {toolUsed && <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}> · {toolUsed}</span>}
      </span>
    ) : null;

    // Clarification message - distinct visual mode
    if (isClarification) {
      return (
        <div
          style={{
            width: "100%",
            maxWidth: "100%",
            padding: "var(--space-5) var(--space-6)",
            borderRadius: "var(--radius-lg)",
            background: "var(--trust-medium-bg)",
            border: "1px solid var(--trust-medium)",
            borderLeft: "4px solid var(--trust-medium)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-3)" }}>
            <div
              style={{
                flexShrink: 0,
                width: "var(--space-7)",
                height: "var(--space-7)",
                borderRadius: "var(--radius-full)",
                background: "var(--trust-medium)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "white",
                fontSize: "var(--text-base)",
              }}
              aria-hidden="true"
            >
              ?
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                <strong style={{ fontSize: "var(--text-base)", color: "var(--ink)" }}>Clarification Needed</strong>
                <span
                  style={{
                    padding: "var(--space-1) var(--space-2)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "var(--text-xs)",
                    fontWeight: "var(--font-semibold)",
                    fontFamily: "var(--font-sans)",
                    textTransform: "uppercase",
                    letterSpacing: "0.02em",
                    background: "var(--trust-medium)",
                    color: "white",
                  }}
                >
                  CLARIFY
                </span>
              </div>
              <div style={{ fontSize: "var(--text-md)", lineHeight: "var(--leading-relaxed)", color: "var(--ink)", maxWidth: "700px" }}>
                {msg.content}
              </div>
              <p style={{ marginTop: "var(--space-3)", fontSize: "var(--text-sm)", color: "var(--ink-muted)", fontStyle: "italic" }}>
                The system needs more context to give you a precise, grounded answer. Please provide additional details.
              </p>
            </div>
          </div>
        </div>
      );
    }

    // Normal message (user or assistant)
    return (
      <>
        <div
          style={{
            width: "100%",
            maxWidth: "100%",
            padding: "var(--space-4) var(--space-5)",
            borderRadius: "var(--radius-lg)",
            background: isUser ? "var(--accent)" : "var(--paper-elevated)",
            color: isUser ? "white" : "var(--ink)",
            border: isUser ? "none" : "1px solid var(--border)",
            boxShadow: isUser ? "var(--shadow-sm)" : "var(--shadow-sm)",
            borderBottomLeftRadius: isUser ? "var(--radius-lg)" : "var(--radius-sm)",
            borderBottomRightRadius: isUser ? "var(--radius-sm)" : "var(--radius-lg)",
          }}
        >
          <div style={{ fontSize: "var(--text-md)", lineHeight: "var(--leading-relaxed)", maxWidth: "700px" }}>
            {msg.content}
            {routeBadge}
          </div>
          
          {/* Confidence + Citations unified bar for assistant messages */}
          {!isUser && (confidence || citations.length > 0) && (
            <div
              style={{
                marginTop: "var(--space-3)",
                paddingTop: "var(--space-3)",
                borderTop: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "var(--space-4)",
                flexWrap: "wrap",
              }}
            >
              {/* Confidence indicator */}
              {confidence && (
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "var(--space-2)",
                    padding: "var(--space-1) var(--space-3)",
                    borderRadius: "var(--radius-full)",
                    fontSize: "var(--text-xs)",
                    fontWeight: "var(--font-semibold)",
                    fontFamily: "var(--font-sans)",
                    textTransform: "uppercase",
                    letterSpacing: "0.02em",
                    background: conf.bg,
                    color: conf.color,
                  }}
                >
                  <span
                    style={{
                      width: "var(--space-1-5)",
                      height: "var(--space-1-5)",
                      borderRadius: "var(--radius-full)",
                      background: conf.dot,
                    }}
                    aria-hidden="true"
                  />
                  {conf.label}
                </div>
              )}

              {/* Citations trigger */}
              {citations.length > 0 && (
                <button
                  type="button"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "var(--space-1)",
                    padding: "var(--space-1) var(--space-3)",
                    borderRadius: "var(--radius-full)",
                    fontSize: "var(--text-xs)",
                    fontWeight: "var(--font-medium)",
                    fontFamily: "var(--font-sans)",
                    color: "var(--accent)",
                    background: "var(--accent-subtle)",
                    border: "none",
                    cursor: "pointer",
                    transition: "background var(--transition-fast)",
                  }}
                  aria-expanded={String(openCitationPanels[msg.id] || false)}
                  aria-controls={`citations-${msg.id}`}
                  onClick={() => toggleCitationPanel(msg.id)}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                  </svg>
                  Sources ({citations.length})
                </button>
              )}
            </div>
          )}

          {/* Expandable citations panel */}
          {!isUser && citations.length > 0 && (() => {
            const MAX_VISIBLE_CITATIONS = 5;
            const isShowAll = showAllCitations[msg.id] || false;
            const visibleCitations = isShowAll || citations.length <= MAX_VISIBLE_CITATIONS
              ? citations
              : citations.slice(0, MAX_VISIBLE_CITATIONS);
            const hasMore = citations.length > MAX_VISIBLE_CITATIONS && !isShowAll;

            return (
              <details
                id={`citations-${msg.id}`}
                open={openCitationPanels[msg.id] || false}
                onToggle={() => toggleCitationPanel(msg.id)}
                style={{ marginTop: "var(--space-3)", animation: `expand var(--transition-normal) ease` }}
              >
                <summary style={{ display: "none" }} aria-hidden="true">Sources</summary>
                <div
                  style={{
                    padding: "var(--space-4)",
                    background: "var(--paper)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-md)",
                    fontSize: "var(--text-sm)",
                    lineHeight: "var(--leading-relaxed)",
                  }}
                >
                  <ul style={{ margin: 0, paddingLeft: "var(--space-6)" }}>
                    {visibleCitations.map((citation, i) => (
                      <li key={i} style={{ marginBottom: "var(--space-3)", paddingLeft: "var(--space-3)", borderLeft: "2px solid var(--border)", position: "relative" }}>
                        <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-2)", marginBottom: "var(--space-1)", flexWrap: "wrap" }}>
                          <span style={{ fontWeight: "var(--font-semibold)", color: "var(--ink)" }}>{citation.source}</span>
                          <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--ink-muted)", background: "var(--border)", padding: "0 var(--space-1)", borderRadius: "var(--radius-sm)" }}>
                            chunk {citation.chunk_index}
                          </span>
                          <span style={{ position: "absolute", left: "calc(var(--space-2) * -1.25)", top: "0", width: "var(--space-1-5)", height: "var(--space-1-5)", borderRadius: "var(--radius-full)", background: "var(--accent)" }} aria-hidden="true" />
                        </div>
                        <div style={{ fontStyle: "italic", color: "var(--ink-muted)", fontSize: "var(--text-sm)", lineHeight: "var(--leading-relaxed)" }}>
                          {citation.excerpt?.slice(0, 300)}{citation.excerpt && citation.excerpt.length > 300 ? "…" : ""}
                        </div>
                      </li>
                    ))}
                  </ul>
                  {hasMore && (
                    <button
                      type="button"
                      className="citation-show-more"
                      onClick={() => toggleShowAllCitations(msg.id)}
                      style={{
                        marginTop: "var(--space-3)",
                        padding: "var(--space-2) var(--space-3)",
                        fontSize: "var(--text-sm)",
                        fontWeight: "var(--font-medium)",
                        fontFamily: "var(--font-sans)",
                        color: "var(--accent)",
                        background: "transparent",
                        border: "1px solid var(--accent)",
                        borderRadius: "var(--radius-md)",
                        cursor: "pointer",
                        transition: "background var(--transition-fast), color var(--transition-fast)",
                      }}
                    >
                      Show {citations.length - MAX_VISIBLE_CITATIONS} more source{citations.length - MAX_VISIBLE_CITATIONS !== 1 ? "s" : ""}
                    </button>
                  )}
                </div>
              </details>
            );
          })()}
        </div>
      </>
    );
  };

  // Assign stable IDs to messages for citation panel targeting
  const messagesWithIds = messages.map((msg, idx) => ({ ...msg, id: `msg-${idx}` }));

  // Compute upload zone styles as explicit strings to avoid React boolean attribute warning
  const uploadBackground = String(dragActive ? "var(--accent-subtle)" : "var(--paper-elevated)");
  const uploadBorder = String(dragActive ? "2px dashed var(--accent)" : "1px solid var(--border)");
  const uploadZoneStyle = {
    padding: "var(--space-4) var(--space-5)",
    background: uploadBackground,
    border: uploadBorder,
    borderRadius: "var(--radius-lg)",
    marginBottom: "var(--space-4)",
    transition: "border var(--transition-fast), background var(--transition-fast)",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: "calc(100vh - var(--header-height) - var(--space-6) - var(--space-8))" }}>
      {/* Upload Zone */}
      <section
        className="upload-zone"
        style={uploadZoneStyle}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        role="region"
        aria-label="Document upload"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt"
          onChange={handleFileSelect}
          disabled={uploading}
          style={{ display: "none" }}
          id="file-upload"
          aria-label="Choose a PDF or TXT file to upload"
        />
        
        {uploadProgress === "uploading" && (
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
            <div
              style={{
                width: "var(--space-5)",
                height: "var(--space-5)",
                border: "2px solid var(--border)",
                borderTopColor: "var(--accent)",
                borderRadius: "var(--radius-full)",
                animation: `spin var(--spin-duration) linear infinite`,
              }}
              aria-hidden="true"
            />
            <div style={{ fontSize: "var(--text-sm)", color: "var(--ink)", minWidth: 0 }}>
              <strong>Uploading…</strong>{" "}
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "inline-block", maxWidth: "280px", verticalAlign: "middle" }}>
                {uploadResult?.filename || "document"}
              </span>
            </div>
          </div>
        )}

        {uploadProgress === "success" && uploadResult && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              padding: "var(--space-3)",
              background: "var(--trust-high-bg)",
              border: "1px solid var(--trust-high)",
              borderRadius: "var(--radius-md)",
              marginBottom: "var(--space-3)",
            }}
            role="status"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--trust-high)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <div style={{ minWidth: 0 }}>
              <strong style={{ color: "var(--trust-high)" }}>Uploaded successfully</strong>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--ink-muted)", display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "280px", display: "inline-block" }}>
                  {uploadResult.filename}
                </span>
                <span>•</span>
                <span>{uploadResult.chunks} chunks ingested</span>
              </div>
            </div>
          </div>
        )}

        {uploadProgress === "error" && uploadResult && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              padding: "var(--space-3)",
              background: "var(--trust-low-bg)",
              border: "1px solid var(--trust-low)",
              borderRadius: "var(--radius-md)",
              marginBottom: "var(--space-3)",
            }}
            role="alert"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--trust-low)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <div style={{ minWidth: 0 }}>
              <strong style={{ color: "var(--trust-low)" }}>Upload failed</strong>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--ink-muted)" }}>
                {uploadResult.error || "Unknown error. Try a PDF or TXT file under 20MB."}
              </div>
            </div>
          </div>
        )}

        {!uploadProgress && (
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
            <div
              style={{
                flexShrink: 0,
                width: "var(--space-10)",
                height: "var(--space-10)",
                borderRadius: "var(--radius-md)",
                background: "var(--accent-subtle)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--accent)",
              }}
              aria-hidden="true"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <button
                type="button"
                onClick={triggerFileInput}
                disabled={uploading}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "var(--space-2)",
                  padding: "var(--space-2) var(--space-4)",
                  fontSize: "var(--text-sm)",
                  fontWeight: "var(--font-medium)",
                  fontFamily: "var(--font-sans)",
                  color: "white",
                  background: "var(--accent)",
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  cursor: uploading ? "not-allowed" : "pointer",
                  transition: "background var(--transition-fast)",
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                Upload Document
              </button>
              <p style={{ margin: "var(--space-1) 0 0", fontSize: "var(--text-xs)", color: "var(--ink-muted)" }}>
                PDF or TXT • Drag and drop or click to browse
              </p>
            </div>
            {messages.length > 0 && messages.some(m => m.citations?.length) && (
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--ink-muted)", padding: "var(--space-1) var(--space-2)", background: "var(--paper)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
                {messages.filter(m => m.citations?.length).reduce((sum, m) => sum + m.citations.length, 0)} sources in conversation
              </span>
            )}
          </div>
        )}
      </section>

      {/* Message List */}
      <main
        ref={messageListRef}
        style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "var(--space-4)", position: "relative" }}
      >
        {messagesWithIds.length === 0 && (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              padding: "var(--space-12) var(--space-6)",
              color: "var(--ink-muted)",
            }}
          >
            <div
              style={{
                width: "var(--space-16)",
                height: "var(--space-16)",
                borderRadius: "var(--radius-full)",
                background: "var(--accent-subtle)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--accent)",
                marginBottom: "var(--space-5)",
              }}
              aria-hidden="true"
            >
              <svg width="var(--space-7)" height="var(--space-7)" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </div>
            <h2 style={{ margin: "0 0 var(--space-2)", fontSize: "var(--text-xl)", fontWeight: "var(--font-semibold)", color: "var(--ink)" }}>
              Start a research session
            </h2>
            <p style={{ margin: "0 0 var(--space-6)", fontSize: "var(--text-md)", maxWidth: "400px", lineHeight: "var(--leading-relaxed)" }}>
              Upload a document (PDF or TXT) using the control above, then ask questions about its contents. Every answer includes citations you can verify.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", maxWidth: "360px" }}>
              <div style={{ padding: "var(--space-3) var(--space-4)", background: "var(--paper-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", textAlign: "left", fontSize: "var(--text-sm)" }}>
                <strong style={{ color: "var(--ink)" }}>Try asking:</strong>
                <ul style={{ margin: "var(--space-2) 0 0", paddingLeft: "var(--space-4)", color: "var(--ink-muted)" }}>
                  <li>"Summarize the methodology section"</li>
                  <li>"What are the key findings?"</li>
                  <li>"Compare the results across experiments"</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {messagesWithIds.map((msg, idx) => (
          <div
            key={msg.id || idx}
            className="message-wrapper"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: msg.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "100%",
              width: "100%",
              alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            {renderMessageContent(msg)}
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div
            style={{
              alignSelf: "flex-start",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              padding: "var(--space-3) var(--space-5)",
              background: "var(--paper-elevated)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              borderBottomLeftRadius: "var(--radius-sm)",
              boxShadow: "var(--shadow-sm)",
            }}
            role="status"
            aria-live="polite"
          >
            <div
              style={{
                width: "var(--space-6)",
                height: "var(--space-6)",
                border: "2px solid var(--border)",
                borderTopColor: "var(--accent)",
                borderRadius: "var(--radius-full)",
                animation: `spin var(--spin-duration) linear infinite`,
              }}
              aria-hidden="true"
            />
            <div style={{ fontSize: "var(--text-sm)", color: "var(--ink-muted)" }}>
              <strong style={{ color: "var(--ink)" }}>{LOADING_STAGES[loadingStage].label}</strong>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
        {showScrollToBottom && (
          <button
            type="button"
            onClick={handleScrollToBottom}
            style={{
              position: "absolute",
              bottom: "var(--space-4)",
              right: "var(--space-4)",
              zIndex: 10,
              padding: "var(--space-2) var(--space-3)",
              fontSize: "var(--text-sm)",
              fontWeight: "var(--font-medium)",
              fontFamily: "var(--font-sans)",
              color: "white",
              background: "var(--accent)",
              border: "none",
              borderRadius: "var(--radius-full)",
              cursor: "pointer",
              boxShadow: "var(--shadow-md)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-1)",
              transition: "background var(--transition-fast), transform var(--transition-fast)",
              animation: `fadeIn var(--transition-normal) ease`,
            }}
            className="scroll-to-bottom-btn"
            aria-label="Scroll to bottom"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="18 15 12 21 6 15" />
            </svg>
            <span>New messages</span>
          </button>
        )}
      </main>

      {/* Input Area */}
      <form className="chat-input-form" onSubmit={handleSend} style={{ paddingTop: "var(--space-4)", borderTop: "1px solid var(--border)" }}>
        <div className="chat-input-container" style={{ display: "flex", gap: "var(--space-3)" }}>
          <label htmlFor="chat-input" className="visually-hidden">Your question</label>
          <input
            id="chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your documents…"
            disabled={loading}
            style={{
              flex: 1,
              padding: "var(--space-3) var(--space-5)",
              fontSize: "var(--text-md)",
              fontFamily: "var(--font-sans)",
              color: "var(--ink)",
              background: "var(--paper-elevated)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              transition: "border-color var(--transition-fast), box-shadow var(--transition-fast)",
            }}
            aria-describedby="chat-input-hint"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            style={{
              padding: "var(--space-3) var(--space-6)",
              fontSize: "var(--text-md)",
              fontWeight: "var(--font-semibold)",
              fontFamily: "var(--font-sans)",
              color: "white",
              background: loading || !input.trim() ? "var(--border-strong)" : "var(--accent)",
              border: "none",
              borderRadius: "var(--radius-lg)",
              cursor: loading || !input.trim() ? "not-allowed" : "pointer",
              transition: "background var(--transition-fast)",
              minWidth: "100px",
            }}
          >
            {loading ? "Thinking…" : "Send"}
          </button>
        </div>
        <p id="chat-input-hint" style={{ margin: "var(--space-2) 0 0", fontSize: "var(--text-xs)", color: "var(--ink-muted)" }}>
          Press Enter to send • Shift+Enter for new line
        </p>
      </form>

      <style jsx global>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes expand {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}