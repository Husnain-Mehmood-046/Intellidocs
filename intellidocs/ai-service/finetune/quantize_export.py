#!/usr/bin/env python
"""
Merge LoRA adapter and export to GGUF for Ollama.

Why this script?
- LoRA adapters are small delta weights; they must be merged into the base model
  for standalone inference.
- GGUF is the standard format for Ollama/llama.cpp - quantized, CPU/GPU friendly.
- This script handles: merge LoRA → save merged model → convert to GGUF → create Modelfile.

Usage:
    python -m finetune.quantize_export [--adapter-path ./lora_adapter] [--output-dir ./gguf_model]

Requirements:
- llama.cpp installed (for gguf conversion): `pip install llama-cpp-python` or build from source
- Or use Ollama's built-in conversion (simpler, recommended)

Two approaches:
1. **Ollama Modelfile (recommended)**: Create a Modelfile that references the base model + adapter
2. **Full GGUF conversion**: Merge + quantize with llama.cpp (more control, larger output)

This script supports both. Approach 1 is faster and smaller; Approach 2 creates a standalone GGUF.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_llama_cpp() -> bool:
    """Check if llama.cpp conversion tools are available."""
    # Check for llama-cpp-python (has convert script)
    try:
        import llama_cpp
        return True
    except ImportError:
        pass
    
    # Check for llama.cpp binary
    for cmd in ["llama-quantize", "llama-gguf-convert", "convert.py"]:
        if shutil.which(cmd):
            return True
    
    return False


def create_modelfile(
    base_model: str,
    adapter_path: Path,
    output_path: Path,
    model_name: str = "intellidocs-finetuned",
    quantization: str = "Q4_K_M",
) -> Path:
    """
    Create an Ollama Modelfile that uses the base model + LoRA adapter.
    
    This is the RECOMMENDED approach - smaller, faster, uses Ollama's native LoRA support.
    """
    modelfile_content = f"""# IntelliDocs Fine-tuned Model
# Base: {base_model}
# Adapter: {adapter_path}
# Quantization: {quantization}

FROM {base_model}

# LoRA adapter (Ollama 0.1.34+ supports this)
ADAPTER {adapter_path.absolute()}

# Model parameters
TEMPLATE \"\"\"<|begin_of_text|><|start_header_id|>system<|end_header_id|>
{{{{ .System }}}}<|eot_id|><|start_header_id|>user<|end_header_id|>
{{{{ .Prompt }}}}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
\"\"\"

PARAMETER stop "<|eot_id|>"
PARAMETER stop "<|start_header_id|>"
PARAMETER temperature 0.0
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.1

# System prompt
SYSTEM \"\"\"You are a helpful assistant that answers questions based on provided context. 
If the context doesn't contain enough information, say so.\"\"\"
"""
    
    modelfile_path = output_path / "Modelfile"
    modelfile_path.write_text(modelfile_content)
    print(f"Created Modelfile at {modelfile_path}")
    return modelfile_path


def create_standalone_gguf(
    base_model_name: str,
    adapter_path: Path,
    output_dir: Path,
    quantization: str = "Q4_K_M",
) -> Optional[Path]:
    """
    Merge LoRA into base model and convert to standalone GGUF using llama.cpp.
    
    This creates a single .gguf file that doesn't need the base model separately.
    Requires llama.cpp tools (convert.py + llama-quantize).
    """
    print("\n" + "=" * 60)
    print("Creating standalone GGUF (merge + quantize)")
    print("=" * 60)
    
    # Step 1: Merge LoRA into base model (save as HF format)
    print("\n[1/3] Merging LoRA adapter into base model...")
    merged_dir = output_dir / "merged_model"
    
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        import torch
        
        print(f"       Loading base model: {base_model_name}")
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        
        print(f"       Loading adapter: {adapter_path}")
        model = PeftModel.from_pretrained(base_model, str(adapter_path))
        
        print("       Merging...")
        merged_model = model.merge_and_unload()
        
        print(f"       Saving merged model to {merged_dir}")
        merged_model.save_pretrained(str(merged_dir))
        tokenizer = AutoTokenizer.from_pretrained(base_model_name)
        tokenizer.save_pretrained(str(merged_dir))
        
        # Clean up to free memory
        del model, base_model, merged_model
        torch.cuda.empty_cache()
        
    except Exception as e:
        print(f"ERROR merging model: {e}")
        return None
    
    # Step 2: Convert to GGUF using llama.cpp convert script
    print("\n[2/3] Converting to GGUF (f16)...")
    gguf_f16 = output_dir / "model-f16.gguf"
    
    # Find convert script
    convert_script = None
    for path in [
        Path.home() / "llama.cpp" / "convert.py",
        Path("/usr/local/bin/convert.py"),
        shutil.which("convert.py"),
    ]:
        if path and path.exists():
            convert_script = path
            break
    
    if not convert_script:
        print("ERROR: llama.cpp convert.py not found.")
        print("Install llama.cpp: git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make")
        print("Or: pip install llama-cpp-python (includes convert script)")
        return None
    
    cmd = [
        sys.executable, str(convert_script),
        str(merged_dir),
        "--outfile", str(gguf_f16),
        "--outtype", "f16",
    ]
    
    print(f"       Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR converting to GGUF: {result.stderr}")
        return None
    
    print(f"       Created {gguf_f16}")
    
    # Step 3: Quantize
    print(f"\n[3/3] Quantizing to {quantization}...")
    gguf_quantized = output_dir / f"model-{quantization.lower()}.gguf"
    
    quantize_bin = shutil.which("llama-quantize")
    if not quantize_bin:
        # Try common locations
        for path in [
            Path.home() / "llama.cpp" / "llama-quantize",
            Path("/usr/local/bin/llama-quantize"),
        ]:
            if path.exists():
                quantize_bin = str(path)
                break
    
    if not quantize_bin:
        print("ERROR: llama-quantize not found. Build llama.cpp first.")
        return None
    
    cmd = [quantize_bin, str(gguf_f16), str(gguf_quantized), quantization]
    print(f"       Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR quantizing: {result.stderr}")
        return None
    
    print(f"       Created {gguf_quantized}")
    
    # Clean up intermediate f16
    gguf_f16.unlink(missing_ok=True)
    shutil.rmtree(merged_dir, ignore_errors=True)
    
    return gguf_quantized


def create_ollama_model_from_gguf(gguf_path: Path, model_name: str) -> bool:
    """Import a GGUF file into Ollama."""
    print(f"\nImporting {gguf_path.name} into Ollama as '{model_name}'...")
    
    # Create a temporary Modelfile for import
    modelfile = f"""FROM {gguf_path.absolute()}
PARAMETER temperature 0.0
PARAMETER top_p 0.9
"""
    
    modelfile_path = gguf_path.parent / "Modelfile.import"
    modelfile_path.write_text(modelfile)
    
    cmd = ["ollama", "create", model_name, "-f", str(modelfile_path)]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    modelfile_path.unlink(missing_ok=True)
    
    if result.returncode != 0:
        print(f"ERROR importing to Ollama: {result.stderr}")
        return False
    
    print(f"Successfully created Ollama model: {model_name}")
    return True


def create_ollama_model_from_modelfile(modelfile_path: Path, model_name: str) -> bool:
    """Create Ollama model from Modelfile (LoRA adapter approach)."""
    print(f"\nCreating Ollama model '{model_name}' from Modelfile...")
    
    cmd = ["ollama", "create", model_name, "-f", str(modelfile_path)]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"ERROR creating Ollama model: {result.stderr}")
        return False
    
    print(f"Successfully created Ollama model: {model_name}")
    return True


def test_model(model_name: str) -> bool:
    """Test the model with a simple prompt."""
    print(f"\nTesting model '{model_name}'...")
    
    import requests
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": "What is IntelliDocs?",
                "stream": False,
                "options": {"temperature": 0.0}
            },
            timeout=60
        )
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {result.get('response', '')[:200]}...")
            return True
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error testing model: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Merge LoRA and export to GGUF for Ollama")
    parser.add_argument("--adapter-path", type=str, default="./lora_adapter",
                        help="Path to LoRA adapter (default: ./lora_adapter)")
    parser.add_argument("--base-model", type=str, default="meta-llama/Meta-Llama-3.1-8B-Instruct",
                        help="Base model name (default: meta-llama/Meta-Llama-3.1-8B-Instruct)")
    parser.add_argument("--output-dir", type=str, default="./gguf_model",
                        help="Output directory (default: ./gguf_model)")
    parser.add_argument("--model-name", type=str, default="intellidocs-finetuned",
                        help="Ollama model name (default: intellidocs-finetuned)")
    parser.add_argument("--quantization", type=str, default="Q4_K_M",
                        choices=["Q4_K_M", "Q4_K_S", "Q5_K_M", "Q8_0", "F16"],
                        help="GGUF quantization (default: Q4_K_M)")
    parser.add_argument("--method", type=str, default="modelfile",
                        choices=["modelfile", "gguf"],
                        help="Export method: modelfile (LoRA adapter) or gguf (standalone)")
    parser.add_argument("--skip-import", action="store_true",
                        help="Skip Ollama import (just create files)")
    parser.add_argument("--test", action="store_true",
                        help="Test model after import")
    args = parser.parse_args()
    
    adapter_path = Path(args.adapter_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("IntelliDocs LoRA → GGUF Export")
    print("=" * 60)
    print(f"Adapter: {adapter_path}")
    print(f"Base model: {args.base_model}")
    print(f"Output dir: {output_dir}")
    print(f"Method: {args.method}")
    print(f"Quantization: {args.quantization}")
    print(f"Ollama model name: {args.model_name}")
    print("=" * 60)
    
    # Verify adapter exists
    if not adapter_path.exists():
        print(f"ERROR: Adapter not found at {adapter_path}")
        print("Run `python -m finetune.train_lora` first.")
        sys.exit(1)
    
    success = False
    
    if args.method == "modelfile":
        # Approach 1: Modelfile with LoRA adapter (recommended)
        print("\nUsing Modelfile approach (LoRA adapter)...")
        modelfile_path = create_modelfile(
            args.base_model,
            adapter_path,
            output_dir,
            args.model_name,
            args.quantization,
        )
        
        if not args.skip_import:
            success = create_ollama_model_from_modelfile(modelfile_path, args.model_name)
        else:
            print("\nSkipping Ollama import (--skip-import).")
            print(f"To import manually: ollama create {args.model_name} -f {modelfile_path}")
            success = True
    
    else:
        # Approach 2: Standalone GGUF
        print("\nUsing standalone GGUF approach...")
        if not check_llama_cpp():
            print("ERROR: llama.cpp tools not found.")
            print("Install: git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make")
            print("Or use --method modelfile (recommended)")
            sys.exit(1)
        
        gguf_path = create_standalone_gguf(
            args.base_model,
            adapter_path,
            output_dir,
            args.quantization,
        )
        
        if gguf_path and not args.skip_import:
            success = create_ollama_model_from_gguf(gguf_path, args.model_name)
        elif gguf_path:
            print(f"\nSkipping Ollama import (--skip-import).")
            print(f"To import manually: ollama create {args.model_name} -f {gguf_path.parent}/Modelfile.import")
            success = True
        else:
            success = False
    
    if success and args.test:
        test_model(args.model_name)
    
    print("\n" + "=" * 60)
    if success:
        print("EXPORT COMPLETE!")
        print("=" * 60)
        print(f"Model name for Ollama: {args.model_name}")
        print(f"Use in IntelliDocs: Set OLLAMA_MODEL={args.model_name} and LLM_PROVIDER=finetuned")
        print(f"Or update config.py FINETUNED_MODEL = '{args.model_name}'")
    else:
        print("EXPORT FAILED!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()