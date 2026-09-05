/**
 * ChatMessage model — persists each user/assistant turn.
 *
 * Fields:
 * - role: "user" | "assistant"
 * - content: the message text
 * - sources: array of { filename, chunkIndex, text } for citations
 *   (only populated on assistant messages)
 * - confidence: "high" | "medium" | "low" - confidence level of the answer
 * - userId: reference to the User who owns this message
 * - createdAt: timestamp (Mongoose adds this automatically via timestamps)
 */
import mongoose from "mongoose";

const sourceSchema = new mongoose.Schema(
  {
    filename: { type: String, required: true },
    chunkIndex: { type: Number, required: true },
    text: { type: String, required: false, default: "" }, // Optional - AI service may not return chunk text
  },
  { _id: false }
);

const chatMessageSchema = new mongoose.Schema(
  {
    role: { type: String, enum: ["user", "assistant"], required: true },
    content: { type: String, required: true },
    sources: { type: [sourceSchema], default: [] },
    confidence: { 
      type: String, 
      enum: ["high", "medium", "low"], 
      default: "medium" 
    },
    userId: { 
      type: mongoose.Schema.Types.ObjectId, 
      ref: "User", 
      required: true 
    },
  },
  { timestamps: true } // adds createdAt + updatedAt automatically
);

export default mongoose.model("ChatMessage", chatMessageSchema);