/**
 * Express backend entry point.
 *
 * Responsibilities (Week 1 + Day 14 + Week 3):
 * - Serve a /health endpoint for connectivity checks.
 * - Connect to MongoDB.
 * - Proxy chat requests to the AI service and persist history.
 * - Handle user authentication (register/login) and protect chat routes.
 * - Serve evaluation reports to admin dashboard (Week 3).
 */
import "dotenv/config";
import express from "express";
import cors from "cors";

import { connectDB } from "./config/db.js";
import chatRoutes from "./routes/chat.js";
import authRoutes from "./routes/auth.js";
import evalRoutes from "./routes/eval.js";

const app = express();
const PORT = process.env.PORT || 5000;

// CORS configuration - allow specific origins in production
// Set CLIENT_URL env var as comma-separated list (e.g., "https://app.example.com,https://admin.example.com")
const allowedOrigins = (process.env.CLIENT_URL || "http://localhost:5173,http://localhost:3000,http://localhost").split(",");
app.use(cors({
  origin: allowedOrigins,
  credentials: true,
}));
app.use(express.json());

app.get("/api/health", (req, res) => {
  res.json({ status: "ok" });
});

// Auth routes (Day 14) - no auth middleware needed
app.use("/api/auth", authRoutes);

// Chat routes (Day 7 + Day 14) - protected by auth middleware
app.use("/api/chat", chatRoutes);

// Eval routes (Week 3) - protected by auth middleware
app.use("/api/eval", evalRoutes);

async function start() {
  await connectDB();
  app.listen(PORT, () => {
    console.log(`[server] Listening on http://localhost:${PORT}`);
  });
}

start();