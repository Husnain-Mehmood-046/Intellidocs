/**
 * Evaluation routes (Week 3 - Day 21).
 * 
 * Serves evaluation reports to the admin dashboard.
 */

import { Router } from "express";
import fs from "fs";
import path from "path";
import authMiddleware from "../middleware/auth.js";

const router = Router();

// Apply auth middleware (admin only in production)
router.use(authMiddleware);

/**
 * GET /api/eval/latest
 * Returns the latest evaluation report.
 * 
 * In production, this would read from a database.
 * For now, reads from the latest JSON file in ai-service/eval/.
 */
router.get("/latest", async (req, res) => {
  try {
    // Path to ai-service/eval directory
    const evalDir = path.join(process.cwd(), "..", "ai-service", "eval");
    
    // Find the latest eval report file
    const files = fs.readdirSync(evalDir)
      .filter(f => f.startsWith("eval_report_") && f.endsWith(".json"))
      .sort()
      .reverse();
    
    if (files.length === 0) {
      return res.status(404).json({ error: "No evaluation reports found" });
    }
    
    const latestFile = files[0];
    const filePath = path.join(evalDir, latestFile);
    const report = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    
    res.json({
      report,
      filename: latestFile,
      timestamp: report.metadata?.timestamp,
    });
  } catch (err) {
    console.error("[eval/latest] Error:", err.message);
    res.status(500).json({ error: "Failed to load evaluation report" });
  }
});

/**
 * GET /api/eval/list
 * Lists all available evaluation reports.
 */
router.get("/list", async (req, res) => {
  try {
    const evalDir = path.join(process.cwd(), "..", "ai-service", "eval");
    
    const files = fs.readdirSync(evalDir)
      .filter(f => f.startsWith("eval_report_") && f.endsWith(".json"))
      .map(f => {
        const filePath = path.join(evalDir, f);
        const stats = fs.statSync(filePath);
        const report = JSON.parse(fs.readFileSync(filePath, "utf-8"));
        return {
          filename: f,
          timestamp: report.metadata?.timestamp,
          provider: report.metadata?.llm_provider,
          total_questions: report.metadata?.total_questions,
          path_accuracy: report.summary?.path_accuracy,
          avg_latency_ms: report.summary?.avg_latency_ms,
          total_cost_usd: report.summary?.total_cost_usd,
          size: stats.size,
        };
      })
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    res.json({ reports: files });
  } catch (err) {
    console.error("[eval/list] Error:", err.message);
    res.status(500).json({ error: "Failed to list evaluation reports" });
  }
});

/**
 * GET /api/eval/:filename
 * Returns a specific evaluation report by filename.
 */
router.get("/:filename", async (req, res) => {
  try {
    const { filename } = req.params;
    
    // Security: only allow eval_report_*.json files
    if (!filename.startsWith("eval_report_") || !filename.endsWith(".json")) {
      return res.status(400).json({ error: "Invalid filename" });
    }
    
    const evalDir = path.join(process.cwd(), "..", "ai-service", "eval");
    const filePath = path.join(evalDir, filename);
    
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: "Report not found" });
    }
    
    const report = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    res.json({ report, filename });
  } catch (err) {
    console.error("[eval/:filename] Error:", err.message);
    res.status(500).json({ error: "Failed to load evaluation report" });
  }
});

export default router;