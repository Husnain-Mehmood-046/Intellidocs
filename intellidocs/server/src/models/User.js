/**
 * User model — stores registered users with hashed passwords.
 *
 * Fields:
 * - email: unique email address (used for login)
 * - passwordHash: bcrypt-hashed password (never store plain text!)
 * - createdAt: timestamp (Mongoose adds this automatically via timestamps)
 */
import mongoose from "mongoose";
import bcrypt from "bcrypt";

const userSchema = new mongoose.Schema(
  {
    email: {
      type: String,
      required: true,
      unique: true,
      lowercase: true,
      trim: true,
    },
    passwordHash: {
      type: String,
      required: true,
    },
  },
  { timestamps: true } // adds createdAt + updatedAt automatically
);

// Instance method to verify a password
userSchema.methods.verifyPassword = async function (password) {
  return bcrypt.compare(password, this.passwordHash);
};

// Static method to hash a password before saving
userSchema.statics.hashPassword = async function (password) {
  const saltRounds = 12;
  return bcrypt.hash(password, saltRounds);
};

export default mongoose.model("User", userSchema);