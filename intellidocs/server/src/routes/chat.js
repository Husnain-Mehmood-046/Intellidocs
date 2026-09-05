/**
 * Chat routes (Day 7 + Day 14 auth).
 *
 * Why a separate routes file?
 * - Keeps index.js focused on app setup (middleware, DB, listen) and lets
 *   route handlers live in their own module as the API grows.
 */

import { Router } from "express";
import multer from "multer";
import ChatMessage from "../models/ChatMessage.js";
import authMiddleware from "../middleware/auth.js";

const router = Router();
const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8000";

// Configure multer for memory storage (we'll forward the file to AI service)
const upload = multer({ storage: multer.memoryStorage() });

// Apply auth middleware to all chat routes
router.use(authMiddleware);

router.post("/chat", async (req, res) => {
  try {
    const { message, thread_id } = req.body;
    if (!message || !message.trim()) {
      return res.status(400).json({ error: "Message is required" });
    }

    // 1. Save user message with userId
    const userMsg = await ChatMessage.create({
      role: "user",
      content: message.trim(),
      sources: [],
      userId: req.userId,
    });

    // 2. Forward to AI service /agent/query (new agent endpoint)
    const aiRes = await fetch(`${AI_SERVICE_URL}/agent/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        question: message.trim(),
        thread_id: thread_id || req.userId, // Use userId as default thread_id
      }),
    });

    if (!aiRes.ok) {
      const err = await aiRes.json().catch(() => ({}));
      throw new Error(err.message || `AI service error: ${aiRes.status}`);
    }

    const aiResponse = await aiRes.json();

    // Handle different response types from agent
    if (aiResponse.route === "clarify") {
      // Clarification response - save as special assistant message
      const clarification = aiResponse.clarification;
      
      const assistantMsg = await ChatMessage.create({
        role: "assistant",
        content: clarification,
        sources: [],
        confidence: "low",
        userId: req.userId,
        metadata: { type: "clarification", route: "clarify" },
      });

      // Return clarification to frontend (different format)
      return res.json({ 
        clarification, 
        route: "clarify",
        messageId: assistantMsg._id,
      });
    }

    // Normal answer response (RAG or tool)
    const { answer, citations, confidence, route, tool_used, tool_args } = aiResponse;

    // Transform citations from AI service format to MongoDB model format
    const transformedSources = (citations || []).map((citation, idx) => ({
      filename: citation.source?.split("\\").pop()?.split("/").pop() || citation.source || `source-${idx}`,
      chunkIndex: citation.chunk_index !== undefined ? citation.chunk_index : idx,
      text: citation.excerpt || "",
    }));

    // 3. Save assistant message with sources, confidence, and userId
    const assistantMsg = await ChatMessage.create({
      role: "assistant",
      content: answer,
      sources: transformedSources,
      confidence: confidence || "medium",
      userId: req.userId,
      metadata: { 
        type: "answer", 
        route: route || "rag",
        tool_used,
        tool_args,
      },
    });

    // 4. Return answer + citations + confidence + route to frontend
    res.json({ answer, citations, confidence, route, tool_used, tool_args });
  } catch (err) {
    console.error("[chat] Error:", err.message);
    res.status(500).json({ error: err.message || "Internal server error" });
  }
});

/**
 * GET /api/chat/history
 * Returns the authenticated user's chat history
 */
router.get("/history", async (req, res) => {
  try {
    const messages = await ChatMessage.find({ userId: req.userId })
      .sort({ createdAt: 1 })
      .lean();

    res.json({ messages });
  } catch (err) {
    console.error("[chat/history] Error:", err.message);
    res.status(500).json({ error: "Failed to fetch chat history" });
  }
});

/**
 * Proxy file upload to AI service /ingest endpoint.
 *
 * Why proxy through Express instead of calling AI service directly?
 * - Avoids CORS issues (browser blocks cross-origin requests to localhost:8000)
 * - Keeps the frontend simple (single API base URL)
 * - Allows adding auth/validation later without changing the frontend
 */
router.post("/ingest", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No file uploaded" });
    }

    // Forward the file to the AI service
    const formData = new FormData();
    const blob = new Blob([req.file.buffer], { type: req.file.mimetype });
    formData.append("file", blob, req.file.originalname);

    const aiRes = await fetch(`${AI_SERVICE_URL}/ingest`, {
      method: "POST",
      body: formData,
    });

    if (!aiRes.ok) {
      const err = await aiRes.json().catch(() => ({}));
      throw new Error(err.message || `AI service error: ${aiRes.status}`);
    }

    const result = await aiRes.json();
    res.json(result);
  } catch (err) {
    console.error("[ingest] Error:", err.message);
    res.status(500).json({ error: err.message || "Upload failed" });
  }
});

export default router;