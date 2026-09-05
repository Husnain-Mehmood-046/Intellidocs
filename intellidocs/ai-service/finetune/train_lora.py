#!/usr/bin/env python
"""
LoRA/QLoRA fine-tuning script for IntelliDocs.

Why this script?
- Fine-tunes a base model on our domain-specific Q&A dataset.
- Uses QLoRA (4-bit quantization + LoRA adapters) for memory-efficient training.
- Designed to run on cloud GPUs (Modal, Colab) or local GPUs with 8GB+ VRAM.
- Saves LoRA adapter weights that can be merged and exported to GGUF.

Usage:
    # Local GPU (8GB+ VRAM)
    python -m finetune.train_lora
    
    # Modal cloud GPU (recommended for AMD/integrated graphics)
    modal run finetune/train_lora.py
    
    # Google Colab: upload and run in notebook

Requirements:
- Dataset must exist at finetune/dataset.jsonl (run build_dataset.py first)
- Base model: llama-3.1-8b (Hugging Face equivalent of ollama's llama3.1:8b)
- GPU with 8GB+ VRAM for 4-bit QLoRA, 16GB+ for 8-bit/16-bit
"""

import os
import sys
import json
import torch
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check for required packages
try:
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainingArguments,
        Trainer,
        DataCollatorForLanguageModeling,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel
    from datasets import load_dataset
    import bitsandbytes as bnb
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install transformers peft datasets bitsandbytes accelerate")
    sys.exit(1)


@dataclass
class FinetuneConfig:
    """Configuration for fine-tuning run."""
    # Model
    base_model_name: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    # Alternative smaller models if VRAM limited:
    # "meta-llama/Meta-Llama-3.1-8B" (base, not instruct)
    # "mistralai/Mistral-7B-Instruct-v0.3"
    
    # LoRA config
    lora_r: int = 16           # Rank (8, 16, 32, 64) - higher = more capacity
    lora_alpha: int = 32       # Scaling factor (typically 2*r)
    lora_dropout: float = 0.05
    target_modules: list = None  # Auto-detect if None
    
    # Quantization
    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "bfloat16"  # or "float16"
    bnb_4bit_quant_type: str = "nf4"
    use_double_quant: bool = True
    
    # Training
    output_dir: str = "./lora_adapter"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 4  # Effective batch = 1 * 4 = 4
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    logging_steps: int = 10
    save_steps: int = 50
    eval_steps: int = 50
    max_steps: int = -1  # -1 = use epochs
    fp16: bool = False
    bf16: bool = True  # Use bfloat16 if supported (Ampere+ GPUs)
    gradient_checkpointing: bool = True
    optim: str = "paged_adamw_32bit"
    
    # Data
    dataset_path: str = "./finetune/dataset.jsonl"
    max_seq_length: int = 2048
    train_split: float = 0.95
    
    # Hardware
    device_map: str = "auto"
    
    def __post_init__(self):
        if self.target_modules is None:
            # Default target modules for Llama/Mistral architectures
            self.target_modules = [
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ]


def get_target_modules(model) -> list:
    """Auto-detect target modules for LoRA based on model architecture."""
    # Find all linear layer names
    target_modules = set()
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.Linear):
            # Get the last part of the name (e.g., "q_proj" from "model.layers.0.self_attn.q_proj")
            short_name = name.split(".")[-1]
            target_modules.add(short_name)
    
    # Filter to attention + MLP projections (standard for Llama/Mistral)
    preferred = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
    return sorted(list(target_modules & preferred))


def format_instruction(example: dict) -> dict:
    """
    Format dataset example into instruction-following prompt template.
    
    Uses Llama 3.1 chat template format:
    <|begin_of_text|><|start_header_id|>system<|end_header_id|>
    {system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>
    {instruction}\n\n{input}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
    {output}<|eot_id|>
    """
    instruction = example.get("instruction", "")
    input_text = example.get("input", "")
    output = example.get("output", "")
    
    # Combine instruction and input
    if input_text:
        user_content = f"{instruction}\n\n{input_text}"
    else:
        user_content = instruction
    
    return {
        "text": f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>You are a helpful assistant that answers questions based on provided context.<|eot_id|><|start_header_id|>user<|end_header_id|>{user_content}<|eot_id|><|start_header_id|>assistant<|end_header_id|>{output}<|eot_id|>"
    }


def tokenize_function(examples, tokenizer, max_length: int):
    """Tokenize formatted examples."""
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_tensors="pt",
    )


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="LoRA/QLoRA fine-tuning for IntelliDocs")
    parser.add_argument("--config", type=str, default=None, help="JSON config file (optional)")
    parser.add_argument("--epochs", type=int, default=None, help="Override num_train_epochs")
    parser.add_argument("--batch-size", type=int, default=None, help="Override per_device_train_batch_size")
    parser.add_argument("--lr", type=float, default=None, help="Override learning_rate")
    parser.add_argument("--output-dir", type=str, default=None, help="Override output_dir")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Validate setup without training")
    args = parser.parse_args()
    
    # Load config
    config = FinetuneConfig()
    if args.config:
        with open(args.config) as f:
            config.__dict__.update(json.load(f))
    
    # Override from CLI
    if args.epochs:
        config.num_train_epochs = args.epochs
    if args.batch_size:
        config.per_device_train_batch_size = args.batch_size
    if args.lr:
        config.learning_rate = args.lr
    if args.output_dir:
        config.output_dir = args.output_dir
    
    print("=" * 60)
    print("IntelliDocs LoRA/QLoRA Fine-Tuning")
    print("=" * 60)
    print(f"Base model: {config.base_model_name}")
    print(f"Output dir: {config.output_dir}")
    print(f"LoRA rank: {config.lora_r}, alpha: {config.lora_alpha}")
    print(f"4-bit quantization: {config.load_in_4bit}")
    print(f"Epochs: {config.num_train_epochs}")
    print(f"Batch size: {config.per_device_train_batch_size} (grad accum: {config.gradient_accumulation_steps})")
    print(f"Learning rate: {config.learning_rate}")
    print(f"Max seq length: {config.max_seq_length}")
    print(f"Device map: {config.device_map}")
    print(f"BF16: {config.bf16}, FP16: {config.fp16}")
    print("=" * 60)
    
    # Check dataset
    dataset_path = Path(config.dataset_path)
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found at {dataset_path}")
        print("Run `python -m finetune.build_dataset` first.")
        sys.exit(1)
    
    # Check GPU
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"GPU: {gpu_name} ({gpu_mem:.1f} GB VRAM)")
        
        if gpu_mem < 8 and config.load_in_4bit:
            print("⚠️  WARNING: GPU has <8GB VRAM. 4-bit QLoRA may OOM.")
            print("   Consider: gradient_accumulation_steps=8, per_device_train_batch_size=1")
            print("   Or use Modal/Colab for training.")
    else:
        print("⚠️  No CUDA GPU detected. Training will be extremely slow on CPU.")
        print("   Use Modal or Colab for GPU training.")
        response = input("Continue anyway? [y/N]: ").strip().lower()
        if response != 'y':
            sys.exit(1)
    
    if args.dry_run:
        print("\nDry run complete. Setup validated.")
        sys.exit(0)
    
    # Load tokenizer
    print("\n[1/5] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model_name,
        trust_remote_code=True,
        use_fast=True,
    )
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    # Load dataset
    print("[2/5] Loading and formatting dataset...")
    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    print(f"       Raw examples: {len(dataset)}")
    
    # Format with chat template
    dataset = dataset.map(format_instruction, remove_columns=dataset.column_names)
    
    # Tokenize
    dataset = dataset.map(
        lambda x: tokenize_function(x, tokenizer, config.max_seq_length),
        batched=True,
        remove_columns=["text"],
    )
    
    # Train/test split
    dataset = dataset.train_test_split(test_size=1 - config.train_split, seed=42)
    train_dataset = dataset["train"]
    eval_dataset = dataset["test"]
    print(f"       Train: {len(train_dataset)}, Eval: {len(eval_dataset)}")
    
    # Configure quantization
    print("[3/5] Configuring 4-bit quantization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=config.load_in_4bit,
        bnb_4bit_compute_dtype=getattr(torch, config.bnb_4bit_compute_dtype),
        bnb_4bit_quant_type=config.bnb_4bit_quant_type,
        bnb_4bit_use_double_quant=config.use_double_quant,
    )
    
    # Load base model
    print("[4/5] Loading base model...")
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model_name,
        quantization_config=bnb_config,
        device_map=config.device_map,
        trust_remote_code=True,
        torch_dtype=getattr(torch, config.bnb_4bit_compute_dtype),
    )
    
    # Prepare for k-bit training
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=config.gradient_checkpointing)
    
    # Configure LoRA
    print("[5/5] Applying LoRA adapters...")
    target_modules = get_target_modules(model) if config.target_modules is None else config.target_modules
    print(f"       Target modules: {target_modules}")
    
    lora_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        target_modules=target_modules,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        warmup_ratio=config.warmup_ratio,
        lr_scheduler_type=config.lr_scheduler_type,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        eval_steps=config.eval_steps,
        max_steps=config.max_steps,
        fp16=config.fp16,
        bf16=config.bf16,
        gradient_checkpointing=config.gradient_checkpointing,
        optim=config.optim,
        evaluation_strategy="steps" if len(eval_dataset) > 0 else "no",
        save_strategy="steps",
        load_best_model_at_end=True if len(eval_dataset) > 0 else False,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",  # Disable wandb/tensorboard by default
        remove_unused_columns=False,
        dataloader_pin_memory=False,
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset if len(eval_dataset) > 0 else None,
        data_collator=data_collator,
    )
    
    # Train
    print("\n" + "=" * 60)
    print("Starting training...")
    print("=" * 60)
    
    if args.resume:
        trainer.train(resume_from_checkpoint=True)
    else:
        trainer.train()
    
    # Save final adapter
    print(f"\nSaving LoRA adapter to {config.output_dir}...")
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)
    print(f"Adapter saved to: {config.output_dir}")
    print("\nNext steps:")
    print("1. Merge and export to GGUF: `python -m finetune.quantize_export`")
    print("2. Load into Ollama with a Modelfile")
    print("3. Test with LLM_PROVIDER=finetuned")


if __name__ == "__main__":
    main()