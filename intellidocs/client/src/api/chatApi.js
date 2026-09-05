/**
 * API client for the chat backend (Day 7 + Day 8-9 + Day 14 + Week 3 updates).
 *
 * Why a dedicated module?
 * - Centralizes all HTTP calls so components don't scatter fetch() calls
 *   and base URLs around the codebase.
 * - Automatically includes JWT token from localStorage for authenticated requests.
 */

const BASE_URL = "/api/chat";

function getAuthHeaders() {
  const token = localStorage.getItem("intellidocs_token");
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function getAuthHeadersNoContentType() {
  const token = localStorage.getItem("intellidocs_token");
  const headers = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function sendMessage(message, threadId = null) {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ message, thread_id: threadId }),
  });
  if (!res.ok) {
    if (res.status === 401) {
      // Token expired - clear auth and reload
      localStorage.removeItem("intellidocs_token");
      localStorage.removeItem("intellidocs_user");
      window.location.href = "/login";
      return;
    }
    throw new Error(`Chat request failed: ${res.status}`);
  }
  // Backend now returns either:
  // - { answer, citations, confidence, route, tool_used, tool_args } for RAG/tool
  // - { clarification, route: "clarify", messageId } for clarification
  return res.json();
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE_URL}/ingest`, {
    method: "POST",
    headers: getAuthHeadersNoContentType(), // Don't set Content-Type for FormData
    body: formData,
  });
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem("intellidocs_token");
      localStorage.removeItem("intellidocs_user");
      window.location.href = "/login";
      return;
    }
    throw new Error(`Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchHistory() {
  const res = await fetch(`${BASE_URL}/history`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem("intellidocs_token");
      localStorage.removeItem("intellidocs_user");
      window.location.href = "/login";
      return;
    }
    throw new Error(`History fetch failed: ${res.status}`);
  }
  return res.json();
}

// Eval API functions (Week 3 - Day 21)
const EVAL_BASE_URL = "/api/eval";

export async function fetchLatestEval() {
  const res = await fetch(`${EVAL_BASE_URL}/latest`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem("intellidocs_token");
      localStorage.removeItem("intellidocs_user");
      window.location.href = "/login";
      return;
    }
    throw new Error(`Eval fetch failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchEvalList() {
  const res = await fetch(`${EVAL_BASE_URL}/list`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem("intellidocs_token");
      localStorage.removeItem("intellidocs_user");
      window.location.href = "/login";
      return;
    }
    throw new Error(`Eval list fetch failed: ${res.status}`);
  }
  return res.json();
}