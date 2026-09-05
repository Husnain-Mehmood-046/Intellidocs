# IntelliDocs AI Service - Modal Deployment
#
# Why Modal?
# - Native Python support, no Docker needed (but can use Dockerfile)
# - GPU support (A10G, T4, H100) with per-second billing
# - Automatic scaling to zero (no cold start for web endpoints)
# - Built-in secrets management, observability, custom domains
# - Free tier: $30/month GPU credits
#
# Usage:
#   modal deploy modal_app.py
#   modal serve modal_app.py  # For development with live reload
#
# Required secrets in Modal dashboard:
# - GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
# - MONGODB_URI (Atlas connection string)
# - JWT_SECRET (shared with server)

import modal
from pathlib import Path

# =============================================================================
# Modal App Configuration
# =============================================================================

app = modal.App("intellidocs-ai-service")

# Define the container image using our Dockerfile
# This ensures exact parity between local docker-compose and Modal deployment
image = modal.Image.from_dockerfile(
    Path(__file__).parent / "Dockerfile"
).env({
    "PYTHONUNBUFFERED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
})

# =============================================================================
# Secrets (configured in Modal dashboard)
# =============================================================================

# Create a secret object that references Modal secrets
# In Modal dashboard: Secrets → Create secret → Add key-value pairs
secrets = modal.Secret.from_name("intellidocs-ai-secrets", required_keys=[
    "GROQ_API_KEY",
    "OPENAI_API_KEY", 
    "ANTHROPIC_API_KEY",
    "MONGODB_URI",
    "JWT_SECRET",
])

# =============================================================================
# Volumes (persistent storage for vector store and data)
# =============================================================================

# Volume for FAISS vector store
vector_store_volume = modal.Volume.from_name("intellidocs-vector-store", create_if_missing=True)

# Volume for uploaded documents
data_volume = modal.Volume.from_name("intellidocs-data", create_if_missing=True)

# Volume for fine-tuning artifacts
finetune_volume = modal.Volume.from_name("intellidocs-finetune", create_if_missing=True)

# =============================================================================
# GPU Configuration
# =============================================================================

# GPU options (choose based on model size and budget):
# - "T4": 16GB VRAM, ~$0.73/hr - Good for llama3.1:8b inference
# - "A10G": 24GB VRAM, ~$1.14/hr - Better for larger models
# - "H100": 80GB VRAM, ~$4.50/hr - For training/large models
# 
# For fine-tuned model serving: T4 is sufficient for 8B model
# For training: Use A10G or H100 (see train_lora.py modal.run)

GPU_CONFIG = "T4"  # Change to "A10G" if needed

# =============================================================================
# FastAPI App (mounted as ASGI)
# =============================================================================

@app.function(
    image=image,
    secrets=[secrets],
    volumes={
        "/app/chroma_db": vector_store_volume,
        "/app/data": data_volume,
        "/app/finetune": finetune_volume,
    },
    gpu=GPU_CONFIG,
    scaledown_window=300,  # Scale to zero after 5 minutes of inactivity
    timeout=600,  # 10 minute timeout for long requests
    memory=8192,  # 8GB RAM
    cpu=4,
    min_containers=0,  # Scale to zero
    max_containers=10,  # Max 10 concurrent containers
)
@modal.asgi_app()
def fastapi_app():
    import sys
    sys.path.insert(0, "/app")
    
    from app.main import app as fastapi_app
    return fastapi_app

# =============================================================================
# Scheduled Jobs (optional)
# =============================================================================

# Example: Daily vector store optimization
@app.function(
    image=image,
    secrets=[secrets],
    volumes={"/app/chroma_db": vector_store_volume},
    schedule=modal.Cron("0 3 * * *"),  # Daily at 3 AM UTC
)
def daily_maintenance():
    """Daily maintenance: optimize vector store, clean old data."""
    import sys
    sys.path.insert(0, "/app")
    
    from app.ingestion import optimize_vector_store
    optimize_vector_store()
    print("Daily maintenance completed")

# =============================================================================
# Fine-tuning Job (run manually with `modal run modal_app.py::train_finetuned`)
# =============================================================================

@app.function(
    image=image,
    secrets=[secrets],
    volumes={
        "/app/chroma_db": vector_store_volume,
        "/app/data": data_volume,
        "/app/finetune": finetune_volume,
    },
    gpu="A10G",  # Need more VRAM for training
    timeout=3600 * 4,  # 4 hours max
    memory=32768,  # 32GB RAM
    cpu=8,
)
def train_finetuned():
    """Run LoRA fine-tuning on Modal GPU."""
    import sys
    sys.path.insert(0, "/app")
    
    # Import and run training
    from finetune.train_lora import main
    import sys
    
    # Override sys.argv for the training script
    sys.argv = [
        "train_lora.py",
        "--epochs", "3",
        "--batch-size", "2",
        "--output-dir", "/app/finetune/lora_adapter",
    ]
    
    main()
    
    # After training, commit the volume so adapter is persisted
    finetune_volume.commit()
    print("Fine-tuning completed and adapter saved")

# =============================================================================
# Export to GGUF Job (run after training)
# =============================================================================

@app.function(
    image=image,
    secrets=[secrets],
    volumes={"/app/finetune": finetune_volume},
    timeout=3600,  # 1 hour
    memory=16384,  # 16GB RAM
)
def export_gguf():
    """Merge LoRA and export to GGUF for Ollama."""
    import sys
    sys.path.insert(0, "/app")
    
    from finetune.quantize_export import main
    import sys
    
    sys.argv = [
        "quantize_export.py",
        "--adapter-path", "/app/finetune/lora_adapter",
        "--output-dir", "/app/finetune/gguf_model",
        "--method", "modelfile",
    ]
    
    main()
    
    finetune_volume.commit()
    print("GGUF export completed")

# =============================================================================
# Local Development Helper
# =============================================================================

@app.local_entrypoint()
def main():
    """Entry point for `modal serve modal_app.py` - runs locally with live reload."""
    print("Starting IntelliDocs AI Service on Modal...")
    print("Access at: https://<your-workspace>.modal.run")
    print("Health check: https://<your-workspace>.modal.run/health")