/**
 * MongoDB connection via Mongoose.
 *
 * Why a separate config module?
 * - Centralizes the connection string and connection logic so routes/models
 *   don't need to know about connection details.
 * - Makes it easy to swap local MongoDB for Atlas by changing one env var.
 */
import mongoose from "mongoose";

const MONGODB_URI =
  process.env.MONGODB_URI || "mongodb://localhost:27017/intellidocs";

export async function connectDB() {
  try {
    await mongoose.connect(MONGODB_URI);
    console.log(`[db] Connected to MongoDB at ${MONGODB_URI}`);
  } catch (err) {
    console.error("[db] MongoDB connection failed:", err.message);
    // Exit so the server doesn't run in a half-broken state.
    process.exit(1);
  }
}