/**
 * Auth routes (Day 14).
 *
 * POST /api/auth/register — Create a new user account
 * POST /api/auth/login    — Authenticate user and return JWT
 */
import { Router } from "express";
import jwt from "jsonwebtoken";
import User from "../models/User.js";

const router = Router();
const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
  throw new Error("JWT_SECRET environment variable must be set");
}
const JWT_EXPIRES_IN = "7d";

/**
 * POST /api/auth/register
 * Body: { email, password }
 * Returns: { token, user: { id, email, createdAt } }
 */
router.post("/register", async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: "Email and password are required" });
    }

    if (password.length < 8) {
      return res.status(400).json({ error: "Password must be at least 8 characters" });
    }

    // Check if user already exists
    const existing = await User.findOne({ email: email.toLowerCase() });
    if (existing) {
      return res.status(409).json({ error: "Email already registered" });
    }

    // Hash password and create user
    const passwordHash = await User.hashPassword(password);
    const user = await User.create({ email: email.toLowerCase(), passwordHash });

    // Generate JWT
    const token = jwt.sign({ userId: user._id }, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });

    res.status(201).json({
      token,
      user: { id: user._id, email: user.email, createdAt: user.createdAt },
    });
  } catch (err) {
    console.error("[auth/register] Error:", err.message);
    res.status(500).json({ error: "Registration failed" });
  }
});

/**
 * POST /api/auth/login
 * Body: { email, password }
 * Returns: { token, user: { id, email, createdAt } }
 */
router.post("/login", async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: "Email and password are required" });
    }

    // Find user
    const user = await User.findOne({ email: email.toLowerCase() });
    if (!user) {
      return res.status(401).json({ error: "Invalid credentials" });
    }

    // Verify password
    const valid = await user.verifyPassword(password);
    if (!valid) {
      return res.status(401).json({ error: "Invalid credentials" });
    }

    // Generate JWT
    const token = jwt.sign({ userId: user._id }, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });

    res.json({
      token,
      user: { id: user._id, email: user.email, createdAt: user.createdAt },
    });
  } catch (err) {
    console.error("[auth/login] Error:", err.message);
    res.status(500).json({ error: "Login failed" });
  }
});

export default router;