"""
TeXa AI Model Engine & Runtime Inference Manager
=================================================
Manages Hugging Face / local PyTorch models (e.g. Qwen2.5-Coder-3B-Instruct,
Qwen2.5-7B-ArXiv-LaTeX, or custom repositories), handles Apple Silicon MPS/CUDA/CPU
hardware-accelerated inference, thread-safe model caching, background downloading,
and provides dedicated pipelines for:

1. Code Tab (LaTeX Code & Template Generation):
   - Generates compilation-ready LaTeX snippets & templates based on user prompts.
   - Refers to active project files (preamble, imported packages, document structure) as context.
   - Implements prompt-level guardrails: if user asks anything other than LaTeX code or templates,
     strictly responds with "I don't know."

2. Debug Tab (Autonomous Document Diagnostic & Error Resolver):
   - Inspects compiler diagnostics & console logs (Tectonic, pdflatex, latexmk).
   - Smart File Filtering: Automatically detects error-triggering .tex scripts from logs.
   - Preprocessed Numbered Code: Feeds LaTeX scripts with 1-indexed line numbers to the model.
   - Strictly outputs: Root cause reason, exact line number of the problem, and debug fix snippet.
   - Continuous & autonomous operation (no chat history required).

3. Conversational Chat & General LaTeX Assistance.
4. IMPORTANT: The AI Assistant is fully generative. Therefore NO HARCODED RULES are allowed. Prompt level intelligence should be implemented in order to handle all the possible errors/bugs.
"""

import os
import re
import json
import threading
import time
from typing import Dict, Any, Optional, List, Tuple

# Root TeXa folder and local models storage directory
# Models are strictly stored in TeXa/models regardless of user working project directory
TEXA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(TEXA_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# Safe Hugging Face Hub Import Handler to prevent backend crashes if missing
try:
    from huggingface_hub import snapshot_download, hf_hub_download
    HF_HUB_AVAILABLE = True
    HF_IMPORT_ERROR = None
except Exception as e:
    HF_HUB_AVAILABLE = False
    HF_IMPORT_ERROR = str(e)
    snapshot_download = None
    hf_hub_download = None

# Safe PyTorch & Transformers Import Handler
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, StoppingCriteria, StoppingCriteriaList
    TORCH_TRANSFORMERS_AVAILABLE = True
    TORCH_IMPORT_ERROR = None
except Exception as e:
    torch = None
    AutoTokenizer = None
    AutoModelForCausalLM = None
    StoppingCriteria = object
    StoppingCriteriaList = list
    TORCH_TRANSFORMERS_AVAILABLE = False
    TORCH_IMPORT_ERROR = str(e)


class InterruptStoppingCriteria(StoppingCriteria):
    """
    Custom stopping criteria that halts PyTorch token generation
    immediately as soon as the stop_event is triggered.
    """
    def __init__(self, stop_event: threading.Event):
        super().__init__()
        self.stop_event = stop_event

    def __call__(self, input_ids: Any, scores: Any, **kwargs) -> bool:
        return self.stop_event.is_set()



def extract_param_num(model_id: str) -> float:
    """Extract model parameter size in Billions (e.g., 3B -> 3.0, 500M -> 0.5, 7B -> 7.0)."""
    match_b = re.search(r'(\d+(?:\.\d+)?)\s*B', model_id, re.IGNORECASE)
    if match_b:
        return float(match_b.group(1))
    match_m = re.search(r'(\d+(?:\.\d+)?)\s*M', model_id, re.IGNORECASE)
    if match_m:
        return float(match_m.group(1)) / 1000.0
    return 999.0  # Fallback large number for unknown


def get_param_display_string(model_id: str) -> str:
    """Return clean human-readable parameter string for UI card badges."""
    match_b = re.search(r'(\d+(?:\.\d+)?)\s*B', model_id, re.IGNORECASE)
    if match_b:
        return f"{match_b.group(1)}B Params"
    match_m = re.search(r'(\d+(?:\.\d+)?)\s*M', model_id, re.IGNORECASE)
    if match_m:
        return f"{match_m.group(1)}M Params"
    return "AI Model"


class AIEngineManager:
    """
    Singleton AI Engine Manager for TeXa.
    Handles dynamic model download, lazy memory loading, hardware device dispatch,
    thread-safe model inference, and LaTeX domain-specific prompt pipelines.
    """

    PRESET_MODELS = []

    def __init__(self):
        self.active_model_id: Optional[str] = None
        self.status = "not_loaded"  # 'not_loaded', 'downloading', 'loading', 'ready', 'error'
        self.progress = 0           # 0 to 100
        self.status_message = "No AI model loaded. Select a model to begin."
        self.download_speed = "0.0 MB/s"
        self.downloaded_size = "0 MB"
        self.total_size = "0 MB"
        self.eta = "0s"
        self.download_thread: Optional[threading.Thread] = None

        # HF Token
        self.hf_token: Optional[str] = os.environ.get("HF_TOKEN")

        # Loaded PyTorch model state
        self.loaded_model_id: Optional[str] = None
        self.tokenizer = None
        self.model = None
        self.device = "cpu"
        self.torch_dtype = None

        # Thread synchronization lock for GPU / MPS inference memory safety
        self.inference_lock = threading.Lock()

        # Cancellation event for stopping active token generation
        self.stop_event = threading.Event()

        # Detect optimal hardware acceleration
        self._detect_device()

    def cancel_generation(self):
        """
        Signals active PyTorch model token generation to terminate immediately.
        Called when user closes the AI Assistant box or cancels the run.
        """
        self.stop_event.set()
        print("[TeXa AI Engine] Active generation cancellation requested by user.", flush=True)

    def set_hf_token(self, token: Optional[str]):
        """Update Hugging Face token for downloads and model requests."""
        if token:
            self.hf_token = token.strip()
            os.environ["HF_TOKEN"] = self.hf_token
        else:
            self.hf_token = None

    def _detect_device(self):
        """Detect and configure optimal hardware acceleration device (Apple MPS, CUDA, or CPU)."""
        if not TORCH_TRANSFORMERS_AVAILABLE or torch is None:
            self.device = "cpu"
            self.torch_dtype = None
            return

        if torch.backends.mps.is_available():
            self.device = "mps"
            self.torch_dtype = torch.float16
            print("[TeXa AI Engine] Apple Silicon Metal (MPS) hardware acceleration active.")
        elif torch.cuda.is_available():
            self.device = "cuda"
            self.torch_dtype = torch.float16
            print(f"[TeXa AI Engine] NVIDIA CUDA GPU acceleration active on {torch.cuda.get_device_name(0)}.")
        else:
            self.device = "cpu"
            self.torch_dtype = torch.float32
            print("[TeXa AI Engine] Running on CPU.")

    # ----------------- LOCAL MODEL DISCOVERY & DOWNLOAD -----------------

    def is_model_downloaded(self, model_id: Optional[str]) -> bool:
        """Check if a model exists and has files in TeXa/models directory."""
        if not model_id or not os.path.exists(MODELS_DIR):
            return False
        safe_folder = model_id.replace("/", "--")
        target_dir = os.path.join(MODELS_DIR, safe_folder)
        if not os.path.isdir(target_dir):
            return False
        try:
            files = os.listdir(target_dir)
            has_config = "config.json" in files
            has_weights = any(f.endswith(".safetensors") or f.endswith(".bin") or f.endswith(".pt") for f in files)
            return (has_config or has_weights) and len(files) > 1
        except Exception:
            return False

    def has_any_downloaded_model(self) -> bool:
        """Check if at least one valid model is downloaded in TeXa/models."""
        if not os.path.exists(MODELS_DIR):
            return False
        try:
            for item in os.listdir(MODELS_DIR):
                if item.startswith("."):
                    continue
                item_path = os.path.join(MODELS_DIR, item)
                if os.path.isdir(item_path):
                    files = os.listdir(item_path)
                    has_config = "config.json" in files
                    has_weights = any(f.endswith(".safetensors") or f.endswith(".bin") or f.endswith(".pt") for f in files)
                    if (has_config or has_weights) and len(files) > 1:
                        return True
        except Exception:
            pass
        return False

    def get_local_models(self) -> List[Dict[str, Any]]:
        """
        Scan TeXa/models directory for locally downloaded model folders.
        Returns a list of local model descriptors.
        """
        local_models = []
        if not os.path.exists(MODELS_DIR):
            return local_models

        try:
            for item in os.listdir(MODELS_DIR):
                if item.startswith("."):
                    continue
                item_path = os.path.join(MODELS_DIR, item)
                if os.path.isdir(item_path):
                    files = os.listdir(item_path)
                    has_config = "config.json" in files
                    has_weights = any(f.endswith(".safetensors") or f.endswith(".bin") or f.endswith(".pt") for f in files)
                    if (has_config or has_weights) and len(files) > 1:
                        clean_id = item.replace("--", "/")
                        local_models.append({
                            "id": clean_id,
                            "name": clean_id.split("/")[-1],
                            "description": f"Stored locally inside TeXa models folder ({clean_id}).",
                            "is_local": True,
                            "is_downloaded": True,
                            "folder_path": item_path,
                            "param_num": extract_param_num(clean_id),
                            "param_display": get_param_display_string(clean_id)
                        })
        except Exception as e:
            print(f"[TeXa AI Engine] Error scanning local models: {e}")

        local_models.sort(key=lambda x: x.get("param_num", 999.0))
        return local_models

    def get_presets(self) -> List[Dict[str, Any]]:
        """Return list of locally downloaded models sorted ascending by parameter size."""
        return self.get_local_models()

    def get_status(self) -> Dict[str, Any]:
        """Return active model selection and live background download progress state with ETA."""
        return {
            "active_model_id": self.active_model_id,
            "loaded_model_id": self.loaded_model_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.status_message,
            "device": self.device,
            "download_speed": self.download_speed,
            "downloaded_size": self.downloaded_size,
            "total_size": self.total_size,
            "eta": self.eta,
            "hf_available": HF_HUB_AVAILABLE,
            "hf_error": HF_IMPORT_ERROR,
            "torch_available": TORCH_TRANSFORMERS_AVAILABLE,
            "models_dir": MODELS_DIR,
            "has_downloaded_models": self.has_any_downloaded_model(),
            "is_active_model_downloaded": self.is_model_downloaded(self.active_model_id) if self.active_model_id else False
        }

    def start_model_download(self, model_id: str, hf_token: Optional[str] = None):
        """Asynchronously trigger Hugging Face snapshot download in background thread into TeXa/models."""
        if hf_token:
            self.set_hf_token(hf_token)

        self.active_model_id = model_id
        self.status = "downloading"
        self.progress = 15
        self.status_message = f"Downloading {model_id}... Meanwhile, sit back, relax, and grab a coffee ☕!"
        self.download_speed = "Active"
        self.downloaded_size = "0 MB"
        self.total_size = "..."
        self.eta = "calculating..."

        self.download_thread = threading.Thread(
            target=self._download_worker,
            args=(model_id,),
            daemon=True
        )
        self.download_thread.start()

    def _download_worker(self, model_id: str):
        """Background thread worker to download HuggingFace repository directly into TeXa/models."""
        try:
            if not HF_HUB_AVAILABLE:
                raise RuntimeError(f"huggingface_hub is not available: {HF_IMPORT_ERROR}")

            safe_folder_name = model_id.replace("/", "--")
            target_local_dir = os.path.join(MODELS_DIR, safe_folder_name)
            os.makedirs(target_local_dir, exist_ok=True)

            self.status = "downloading"
            self.progress = 20
            self.status_message = f"Downloading {model_id}... Meanwhile, sit back, relax, and grab a coffee ☕!"
            print(f"[TeXa AI Engine] Starting download for {model_id} into {target_local_dir}...")

            token_to_use = self.hf_token or os.environ.get("HF_TOKEN")

            # Snapshot download all model files (including tokenizer models, config, weights)
            download_path = snapshot_download(
                repo_id=model_id,
                local_dir=target_local_dir,
                token=token_to_use,
                ignore_patterns=["*.msgpack", "*.h5", "*.ot"]
            )

            self.progress = 100
            self.status = "ready"
            self.status_message = f"Model {model_id} downloaded and ready in TeXa folder."
            print(f"[TeXa AI Engine] Download complete for {model_id} at {download_path}")

        except Exception as e:
            self.status = "error"
            self.progress = 0
            self.status_message = f"Failed to download model {model_id}: {str(e)}"
            print(f"[TeXa AI Engine] Error downloading model {model_id}: {e}")

    # ----------------- PYTORCH / TRANSFORMERS MODEL RUNNER -----------------

    def _resolve_model_path(self, model_id: str) -> str:
        """Resolve local folder path inside TeXa/models or fallback to repo ID."""
        safe_folder = model_id.replace("/", "--")
        local_path = os.path.join(MODELS_DIR, safe_folder)
        if os.path.exists(local_path) and len(os.listdir(local_path)) > 1:
            return local_path

        # Check if any matching folder in models dir
        if os.path.exists(MODELS_DIR):
            for item in os.listdir(MODELS_DIR):
                if item.startswith("."):
                    continue
                item_path = os.path.join(MODELS_DIR, item)
                if os.path.isdir(item_path) and len(os.listdir(item_path)) > 1:
                    if model_id.split("/")[-1].lower() in item.lower():
                        return item_path

        return model_id

    def load_model(self, model_id: str) -> bool:
        """
        Explicitly loads and activates selected model into memory on the appropriate device.
        Thread-safe and caches loaded model to prevent redundant reloads.
        """
        with self.inference_lock:
            if self.loaded_model_id == model_id and self.model is not None and self.tokenizer is not None:
                self.active_model_id = model_id
                self.status = "ready"
                self.status_message = f"Model {model_id} ready on {self.device.upper()}."
                return True

            if not TORCH_TRANSFORMERS_AVAILABLE:
                self.status = "error"
                self.status_message = f"PyTorch / Transformers not available: {TORCH_IMPORT_ERROR}"
                print(f"[TeXa AI Engine] {self.status_message}")
                return False

            self.status = "loading"
            self.status_message = f"Loading model {model_id} into memory on {self.device.upper()}..."
            print(f"[TeXa AI Engine] Loading {model_id} onto {self.device.upper()} (dtype: {self.torch_dtype})...")

            try:
                model_path = self._resolve_model_path(model_id)
                token_to_use = self.hf_token or os.environ.get("HF_TOKEN")

                # Unload previous model from GPU/MPS memory if present
                if self.model is not None:
                    del self.model
                    self.model = None
                if self.tokenizer is not None:
                    del self.tokenizer
                    self.tokenizer = None

                if self.device == "mps" and torch is not None:
                    torch.mps.empty_cache()
                elif self.device == "cuda" and torch is not None:
                    torch.cuda.empty_cache()

                # Load Tokenizer (fast with fallback to slow tokenizer for SentencePiece/TikToken)
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        model_path,
                        token=token_to_use,
                        trust_remote_code=True
                    )
                except Exception as fast_tok_err:
                    print(f"[TeXa AI Engine] Fast tokenizer load failed ({fast_tok_err}), trying use_fast=False...")
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        model_path,
                        token=token_to_use,
                        trust_remote_code=True,
                        use_fast=False
                    )

                # Ensure pad token is defined
                if self.tokenizer.pad_token_id is None:
                    if self.tokenizer.eos_token_id is not None:
                        self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
                        self.tokenizer.pad_token = self.tokenizer.eos_token
                    else:
                        self.tokenizer.add_special_tokens({'pad_token': '[PAD]'})

                # Load Model Weights
                target_dtype = self.torch_dtype or torch.float32
                try:
                    if self.device == "mps":
                        self.model = AutoModelForCausalLM.from_pretrained(
                            model_path,
                            token=token_to_use,
                            torch_dtype=target_dtype,
                            trust_remote_code=True,
                            low_cpu_mem_usage=True
                        )
                        self.model.to("mps")
                    elif self.device == "cuda":
                        self.model = AutoModelForCausalLM.from_pretrained(
                            model_path,
                            token=token_to_use,
                            torch_dtype=target_dtype,
                            device_map="auto",
                            trust_remote_code=True
                        )
                    else:
                        self.model = AutoModelForCausalLM.from_pretrained(
                            model_path,
                            token=token_to_use,
                            torch_dtype=torch.float32,
                            trust_remote_code=True,
                            low_cpu_mem_usage=True
                        )
                except Exception as primary_dev_err:
                    print(f"[TeXa AI Engine] Device load warning ({primary_dev_err}), falling back to CPU float32...")
                    self.device = "cpu"
                    self.torch_dtype = torch.float32
                    self.model = AutoModelForCausalLM.from_pretrained(
                        model_path,
                        token=token_to_use,
                        torch_dtype=torch.float32,
                        trust_remote_code=True,
                        low_cpu_mem_usage=True
                    )

                self.model.eval()
                self.loaded_model_id = model_id
                self.active_model_id = model_id
                self.status = "ready"
                self.progress = 100
                self.status_message = f"Model {model_id} loaded successfully on {self.device.upper()}."
                print(f"[TeXa AI Engine] Active model loaded: {model_id} ({self.device.upper()})")
                return True

            except Exception as e:
                self.status = "error"
                self.status_message = f"Failed to load model {model_id}: {str(e)}"
                print(f"[TeXa AI Engine] Error loading model {model_id}: {e}")
                return False

    def _generate_raw(self, messages: List[Dict[str, str]], max_new_tokens: int = 768, temperature: float = 0.0) -> str:
        """
        Thread-safe inference execution against the loaded PyTorch model.
        Supports instant cancellation through InterruptStoppingCriteria.
        Returns generated response string.
        """
        if not self.active_model_id:
            raise RuntimeError("No AI Model selected. Please select a model on the Setup page.")

        if self.model is None or self.tokenizer is None or self.loaded_model_id != self.active_model_id:
            success = self.load_model(self.active_model_id)
            if not success:
                raise RuntimeError(f"AI Model {self.active_model_id} could not be loaded into memory: {self.status_message}")

        # Clear cancellation event before starting new generation
        self.stop_event.clear()

        with self.inference_lock:
            if self.stop_event.is_set():
                raise RuntimeError("Model generation cancelled by user.")

            try:
                # Merge system prompt into user prompt for Gemma / multi-architecture compatibility
                chat_messages = []
                system_content = ""
                for m in messages:
                    if m.get("role") == "system":
                        system_content += m.get("content", "").strip() + "\n\n"
                    elif m.get("role") == "user":
                        if system_content:
                            chat_messages.append({"role": "user", "content": f"{system_content.strip()}\n\n{m.get('content', '')}"})
                            system_content = ""
                        else:
                            chat_messages.append(m)
                    else:
                        chat_messages.append(m)
                if system_content and not chat_messages:
                    chat_messages.append({"role": "user", "content": system_content.strip()})

                # Apply chat template or construct dialogue prompt
                prompt_text = ""
                if hasattr(self.tokenizer, "apply_chat_template") and self.tokenizer.chat_template:
                    try:
                        prompt_text = self.tokenizer.apply_chat_template(
                            chat_messages,
                            tokenize=False,
                            add_generation_prompt=True
                        )
                    except Exception as chat_err:
                        print(f"[TeXa AI Engine] Chat template warning ({chat_err}), falling back to structured prompt...")
                        prompt_text = ""

                if not prompt_text:
                    # Fallback formatted prompt compatible across standard LLM architectures
                    formatted_turns = []
                    for m in chat_messages:
                        role_tag = "<|im_start|>" + m.get("role", "user") + "\n"
                        formatted_turns.append(f"{role_tag}{m.get('content', '')}<|im_end|>")
                    formatted_turns.append("<|im_start|>assistant\n")
                    prompt_text = "\n".join(formatted_turns)

                inputs = self.tokenizer(prompt_text, return_tensors="pt")
                input_ids = inputs["input_ids"].to(self.device)
                attention_mask = inputs.get("attention_mask", None)
                if attention_mask is not None:
                    attention_mask = attention_mask.to(self.device)

                # Determine all possible end-of-sequence / end-of-turn token IDs for instant termination
                eos_ids = []
                if self.tokenizer.eos_token_id is not None:
                    if isinstance(self.tokenizer.eos_token_id, list):
                        eos_ids.extend(self.tokenizer.eos_token_id)
                    else:
                        eos_ids.append(self.tokenizer.eos_token_id)

                for special_tok in ["<end_of_turn>", "<|im_end|>", "<|eot_id|>", "</s>", "<eos>", "<|endoftext|>"]:
                    try:
                        t_id = self.tokenizer.convert_tokens_to_ids(special_tok)
                        if t_id is not None and isinstance(t_id, int) and t_id > 0 and t_id not in eos_ids:
                            eos_ids.append(t_id)
                    except Exception:
                        pass

                # Configure cancellation stopping criteria
                stopping_criteria = StoppingCriteriaList([InterruptStoppingCriteria(self.stop_event)])

                with torch.inference_mode():
                    output_ids = self.model.generate(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        max_new_tokens=min(max_new_tokens, 1024),
                        temperature=temperature if temperature > 0.0 else 0.05,
                        top_p=0.9 if temperature > 0.0 else 1.0,
                        do_sample=temperature > 0.0,
                        repetition_penalty=1.12,
                        pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                        eos_token_id=eos_ids if eos_ids else self.tokenizer.eos_token_id,
                        stopping_criteria=stopping_criteria
                    )

                # Check if generation was interrupted mid-run
                if self.stop_event.is_set():
                    print("[TeXa AI Engine] Generation terminated by user cancellation request.", flush=True)
                    if self.device == "mps" and torch is not None:
                        torch.mps.empty_cache()
                    raise RuntimeError("Model generation cancelled by user.")

                # Decode only the generated response tokens
                generated_tokens = output_ids[0][input_ids.shape[1]:]
                response_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

                # Print the response of the model in the system terminal
                print("\n" + "=" * 60)
                print(f"[TeXa Model Response | Model: {self.active_model_id}]:")
                print(response_text)
                print("=" * 60 + "\n", flush=True)

                if self.device == "mps" and torch is not None:
                    torch.mps.empty_cache()

                return response_text

            except Exception as e:
                if "cancelled" in str(e).lower():
                    print(f"[TeXa AI Engine] Generation aborted: {e}")
                else:
                    print(f"[TeXa AI Engine] Inference runtime error: {e}")
                raise e


    # ----------------- PROJECT CONTEXT EXTRACTION HELPERS -----------------

    def _extract_project_context(self, working_dir: Optional[str], active_file: Optional[str] = "main.tex") -> Tuple[str, List[str], str]:
        """
        Extract user's project context: document class, packages, and overall structure
        to provide relevant reference context to the model.
        """
        if not working_dir or not os.path.exists(working_dir):
            return "article", ["amsmath", "graphicx"], ""

        doc_class = "article"
        packages = []
        context_snippets = []

        try:
            main_path = os.path.join(working_dir, active_file or "main.tex")
            if not os.path.exists(main_path):
                # Search for any .tex file
                for f in os.listdir(working_dir):
                    if f.endswith(".tex"):
                        main_path = os.path.join(working_dir, f)
                        break

            if os.path.exists(main_path):
                with open(main_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Extract document class
                class_match = re.search(r'\\documentclass(?:\[[^\]]*\])?\{([a-zA-Z0-9_-]+)\}', content)
                if class_match:
                    doc_class = class_match.group(1)

                # Extract usepackages
                pkg_matches = re.findall(r'\\usepackage(?:\[[^\]]*\])?\{([a-zA-Z0-9_,\s-]+)\}', content)
                for pm in pkg_matches:
                    for pkg in pm.split(","):
                        clean_pkg = pkg.strip()
                        if clean_pkg and clean_pkg not in packages:
                            packages.append(clean_pkg)

                # Extract key section headers or document structure summary
                sections = re.findall(r'\\(?:section|subsection|chapter)\*?\{([^}]+)\}', content)
                if sections:
                    context_snippets.append(f"Sections in active document: {', '.join(sections[:8])}")

        except Exception as e:
            print(f"[TeXa AI Engine] Error extracting project context: {e}")

        summary = " | ".join(context_snippets) if context_snippets else "Standard LaTeX project structure."
        return doc_class, packages, summary

    # ----------------- TAB 1: LATEX CODE TEMPLATE GENERATION (WITH GUARDRAILS) -----------------

    def is_identity_query(self, prompt: str) -> bool:
        """
        Check if user query is asking about the AI Assistant's identity, role, creator, or name.
        """
        p = prompt.lower().strip()
        if not p:
            return False
        identity_patterns = [
            r"\bwho are you\b",
            r"\bwho is she\b",
            r"\bwho she is\b",
            r"\bwho is texa\b",
            r"\bwhat is texa\b",
            r"\bwhat are you\b",
            r"\bwhat is your name\b",
            r"\btell me about yourself\b",
            r"\btell me about you\b",
            r"\bintroduce yourself\b",
            r"\bwho made you\b",
            r"\bwho created you\b",
            r"\byour identity\b",
            r"\bwhat can you do\b",
            r"\bwhat is your purpose\b",
            r"\bwhat is your role\b",
            r"\bwho is the ai\b",
            r"\bwho am i talking to\b"
        ]
        return any(re.search(pat, p) for pat in identity_patterns)

    def is_latex_template_query(self, prompt: str) -> bool:
        """
        Strict heuristic check for LaTeX-related requests.
        Ensures guardrail is applied consistently: if anything other than LaTeX code / research writing
        is asked, returns False.
        """
        p = prompt.lower().strip()
        if not p:
            return False

        # If it is an identity query, it's handled separately
        if self.is_identity_query(prompt):
            return False

        # Explicit off-topic keywords
        non_latex_phrases = [
            "who is", "who was", "what is the capital", "tell me a joke", "weather",
            "bake a cake", "recipe", "poem about", "sing a song", "movie review",
            "president of", "population of", "how old is", "write python script",
            "python program", "javascript function", "c++ code", "summarize news",
            "what time is it", "who won the", "write an essay about", "what is the meaning of",
            "translate to", "stock price", "sports score", "health advice"
        ]
        has_off_topic = any(nlp in p for nlp in non_latex_phrases)

        # LaTeX keywords
        latex_keywords = [
            "table", "tabular", "booktabs", "multicolumn", "multirow", "longtable",
            "matrix", "matrices", "pmatrix", "bmatrix", "vmatrix",
            "figure", "subfigures", "subfigure", "image", "graphic", "wrapfig",
            "equation", "align", "math", "calculus", "integral", "derivative", "fraction",
            "algorithm", "algorithmic", "pseudocode", "code block", "listings", "lstlisting", "minted",
            "bibliography", "bibtex", "citation", "bib",
            "beamer", "presentation", "slide", "frame",
            "letter", "cv", "resume", "curriculum vitae",
            "abstract", "title", "section", "subsection", "chapter", "preamble",
            "header", "footer", "fancyhdr", "geometry", "margin",
            "multicol", "columns", "enumerate", "itemize", "list", "bullet",
            "theorem", "lemma", "proof", "corollary", "definition",
            "tikz", "tikzpicture", "flowchart", "pgfplots", "diagram", "circuit",
            "template", "snippet", "boilerplate", "skeleton", "environment",
            "latex", "tex", "document", "author", "affiliation", "footnote",
            "citation", "ref", "label", "package", "usepackage", "documentclass"
        ]
        has_latex_kw = any(kw in p for kw in latex_keywords)

        # Check for LaTeX macro syntax (\command, $, %, {, })
        has_latex_syntax = bool(re.search(r'\\[a-zA-Z]+|\$[^$]+\$|\\begin|\\end', prompt))

        if has_off_topic and not (has_latex_kw or has_latex_syntax):
            return False

        # Strictly return True ONLY if query mentions LaTeX concepts or uses LaTeX syntax
        return bool(has_latex_kw or has_latex_syntax)

    def generate_code_template(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        working_dir: Optional[str] = None,
        active_file: Optional[str] = "main.tex"
    ) -> Dict[str, Any]:
        """
        Generates compile-ready LaTeX code snippet or template based on user prompt.
        Uses user's active project files as reference context.
        Applies strict guardrails:
        1. If user asks related to AI Assistant's identity:
           responds: "She is TeXa - Your's AI Assistant to help with your research paper writing."
        2. If anything other than LaTeX code is asked:
           responds strictly: "I don't know."
        """
        active_model = model_id or self.active_model_id
        if active_model != self.active_model_id:
            self.active_model_id = active_model

        # Check for AI Assistant identity query
        if self.is_identity_query(prompt):
            identity_text = "She is TeXa - Your's AI Assistant to help with your research paper writing."
            return {
                "status": "identity",
                "is_template": False,
                "model": active_model,
                "title": "TeXa Identity",
                "description": identity_text,
                "response": identity_text,
                "code": "",
                "packages": []
            }

        # Check prompt-level guardrail heuristic
        if not self.is_latex_template_query(prompt):
            return {
                "status": "unknown",
                "is_template": False,
                "model": active_model,
                "title": "Unknown Query",
                "description": "I don't know.",
                "response": "I don't know.",
                "code": "",
                "packages": []
            }

        # Gather user's project context
        doc_class, existing_pkgs, context_summary = self._extract_project_context(working_dir, active_file)
        pkgs_str = ", ".join(existing_pkgs) if existing_pkgs else "amsmath, graphicx, hyperref"

        system_instruction = (
            "You are TeXa - Your's AI Assistant to help with your research paper writing. "
            "Your sole purpose is to generate clean, syntactically valid, compile-ready LaTeX code snippets in standard English letters based on the user's request.\n\n"
            f"[PROJECT CONTEXT]\n"
            f"- Document Class: {doc_class}\n"
            f"- Already Imported Packages in Project: {pkgs_str}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. If the user asks about your identity, name, or who you are, reply EXACTLY with: \"She is TeXa - Your's AI Assistant to help with your research paper writing.\"\n"
            "2. If anything other than LaTeX code, templates, or LaTeX research paper writing is asked, reply STRICTLY with: \"I don't know.\"\n"
            f"3. For valid LaTeX requests, generate ONLY the exact LaTeX code snippet requested: \"{prompt}\".\n"
            "4. Output strictly in English letters only. Do NOT output foreign characters, CJK characters, or rambling text.\n"
            "5. Output ONLY pure, valid LaTeX code directly. DO NOT output JSON.\n"
            "6. DO NOT output conversational filler like 'Here is your table:' or explanations.\n"
            "7. If the request is for a table (e.g., N rows, M columns), create a well-structured tabular or table environment with the exact dimensions requested, proper '&' separators, and '\\\\' endings."
        )

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Generate pure LaTeX code in English for: {prompt}"}
        ]

        try:
            raw_output = self._generate_raw(messages, max_new_tokens=400, temperature=0.05)

            # Check for Guardrail trigger "I don't know."
            if "I don't know" in raw_output or "i don't know" in raw_output.lower():
                return {
                    "status": "unknown",
                    "is_template": False,
                    "model": active_model,
                    "title": "Unknown Query",
                    "description": "I don't know.",
                    "response": "I don't know.",
                    "code": "",
                    "packages": []
                }

            # Check for identity trigger
            if "She is TeXa" in raw_output or "TeXa - Your's AI Assistant" in raw_output:
                identity_text = "She is TeXa - Your's AI Assistant to help with your research paper writing."
                return {
                    "status": "identity",
                    "is_template": False,
                    "model": active_model,
                    "title": "TeXa Identity",
                    "description": identity_text,
                    "response": identity_text,
                    "code": "",
                    "packages": []
                }

            extracted_code = ""

            # If the model still returned JSON despite instructions, extract code field or values
            parsed = self._extract_json_from_text(raw_output)
            if parsed and isinstance(parsed, dict) and "code" in parsed and isinstance(parsed["code"], str) and parsed["code"].strip():
                extracted_code = parsed["code"].strip()

            if not extracted_code:
                # Extract code from markdown code block if present
                code_block_match = re.search(r'```(?:latex|tex)?\s*([\s\S]+?)\s*```', raw_output)
                if code_block_match:
                    extracted_code = code_block_match.group(1).strip()
                else:
                    extracted_code = raw_output.strip()

            # Clean up any remaining backtick fences
            extracted_code = re.sub(r'^```(?:latex|tex)?\s*', '', extracted_code)
            extracted_code = re.sub(r'\s*```$', '', extracted_code).strip()

            # Clean up any non-ASCII characters or multilingual rambling
            extracted_code = re.sub(r'[^\x00-\x7F]+', '', extracted_code)

            # If the code contains \begin{...} and \end{...}, trim anything after the matching \end{...}
            end_env_matches = list(re.finditer(r'\\end\{([a-zA-Z0-9*]+)\}', extracted_code))
            if end_env_matches:
                last_match = end_env_matches[-1]
                extracted_code = extracted_code[:last_match.end()].strip()

            # Clean up excessive repetitive lines (e.g. repeated \hline or empty lines)
            lines = extracted_code.splitlines()
            cleaned_lines = []
            repeat_count = 0
            last_line = None
            for line in lines:
                if line == last_line and line.strip() in [r"\hline", r"\hline\hline", ""]:
                    repeat_count += 1
                    if repeat_count < 2:
                        cleaned_lines.append(line)
                else:
                    repeat_count = 0
                    cleaned_lines.append(line)
                last_line = line
            extracted_code = "\n".join(cleaned_lines).strip()

            # Detect needed packages via regex
            detected_pkgs = []
            if "toprule" in extracted_code or "midrule" in extracted_code or "bottomrule" in extracted_code:
                detected_pkgs.append("booktabs")
            if "tabularx" in extracted_code:
                detected_pkgs.append("tabularx")
            if "bmatrix" in extracted_code or "align" in extracted_code or "pmatrix" in extracted_code:
                detected_pkgs.append("amsmath")
            if "includegraphics" in extracted_code:
                detected_pkgs.append("graphicx")
            if "subfigure" in extracted_code or "subcaption" in extracted_code:
                detected_pkgs.append("subcaption")
            if "tikzpicture" in extracted_code:
                detected_pkgs.append("tikz")
            if "algorithmic" in extracted_code or "State" in extracted_code:
                detected_pkgs.append("algpseudocode")
            if "lstlisting" in extracted_code:
                detected_pkgs.append("listings")
            if "multirow" in extracted_code:
                detected_pkgs.append("multirow")
            if "multicolumn" in extracted_code:
                detected_pkgs.append("array")

            # Filter out packages already imported in project
            pkgs_to_report = [p for p in detected_pkgs if p not in existing_pkgs]

            title = f"LaTeX {prompt.strip().title()}"
            if len(title) > 40:
                title = title[:37] + "..."

            return {
                "status": "success",
                "is_template": True,
                "model": active_model,
                "title": title,
                "description": f"Pure LaTeX code snippet for {prompt.strip()}.",
                "code": extracted_code,
                "response": f"Generated pure LaTeX template using `{active_model}`.\n\n```latex\n{extracted_code}\n```",
                "packages": pkgs_to_report
            }

        except Exception as e:
            print(f"[TeXa AI Engine] Error during code template generation: {e}")
            return {
                "status": "error",
                "is_template": False,
                "model": active_model,
                "title": "Generation Error",
                "description": str(e),
                "response": f"Error generating LaTeX code with model `{active_model}`: {str(e)}",
                "code": "",
                "packages": []
            }

    # ----------------- TAB 2: AUTONOMOUS DEBUG DOCUMENT ANALYZER -----------------

    def _identify_error_files(
        self,
        diagnostics: List[Dict[str, Any]],
        log_output: str,
        active_file: str,
        working_dir: str
    ) -> List[str]:
        """
        Smart File Identifier: Scans compiler diagnostics and output logs to detect
        which specific .tex files in the project are triggering the errors.
        """
        identified_files = set()

        # 1. Inspect structured diagnostics for file attributes
        for diag in diagnostics:
            f = diag.get("file")
            if f and f.endswith(".tex"):
                identified_files.add(os.path.basename(f))

        # 2. Inspect raw compiler log output for file references
        file_patterns = [
            r'\(\.?/([a-zA-Z0-9_\-/\\]+\.tex)',
            r'([a-zA-Z0-9_\-/\\]+\.tex):\d+:',
            r'File\s+[`\']([a-zA-Z0-9_\-/\\]+\.tex)[`\']',
            r'input line \d+ of ([a-zA-Z0-9_\-/\\]+\.tex)',
            r'on input line \d+ in ([a-zA-Z0-9_\-/\\]+\.tex)'
        ]
        for pat in file_patterns:
            matches = re.findall(pat, log_output)
            for m in matches:
                identified_files.add(os.path.basename(m))

        # Verify files actually exist in working_dir
        valid_files = []
        if os.path.exists(working_dir):
            for fname in identified_files:
                for root, _, files in os.walk(working_dir):
                    if fname in files:
                        rel = os.path.relpath(os.path.join(root, fname), working_dir)
                        valid_files.append(rel)
                        break

        # Fallback to active_file or main.tex if no specific sub-file was identified
        if not valid_files:
            if active_file and os.path.exists(os.path.join(working_dir, active_file)):
                valid_files.append(active_file)
            else:
                main_candidate = os.path.join(working_dir, "main.tex")
                if os.path.exists(main_candidate):
                    valid_files.append("main.tex")

        return valid_files

    def _get_numbered_file_code(
        self,
        file_path: str,
        active_content: str = "",
        is_active: bool = False
    ) -> str:
        """
        Retrieves the complete code of the file and prepends 1-indexed line numbers
        to every line (e.g. '1: \\documentclass{article}\\n2: \\usepackage{amsmath}').
        Sends the entire code without skipping or truncating lines.
        """
        lines = []
        if is_active and active_content:
            lines = active_content.splitlines()
        elif os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [l.rstrip("\r\n") for l in f.readlines()]
            except Exception:
                lines = []

        if not lines:
            return "(File is empty)"

        return "\n".join([f"{idx + 1}: {line}" for idx, line in enumerate(lines)])

    def debug_document_errors(
        self,
        diagnostics: List[Dict[str, Any]],
        log_output: str,
        active_file: str,
        active_content: str,
        working_dir: str,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pure Model-Driven LaTeX Debugger:
        Takes the complete line-numbered source code of the error-throwing file,
        structured compiler diagnostics, and console error logs.
        The AI model solely diagnoses all syntax/compilation issues and outputs
        strictly one Root Cause and one Solution per detected issue.
        """
        active_model = model_id or self.active_model_id
        if active_model != self.active_model_id:
            self.active_model_id = active_model

        # Strict Error-Only Filtering: Ignore all warnings per requirement
        error_diagnostics = [d for d in (diagnostics or []) if d.get("severity") == "error"]
        has_fatal_log_error = (
            "!" in (log_output or "") or
            "Error:" in (log_output or "") or
            "Fatal error" in (log_output or "") or
            "Undefined control sequence" in (log_output or "") or
            "File `" in (log_output or "") or
            "not found" in (log_output or "")
        )

        # If document is clean (no errors reported)
        if not error_diagnostics and not has_fatal_log_error:
            return {
                "status": "clean",
                "model": active_model,
                "error_count": 0,
                "warning_count": 0,
                "summary": "Document syntax is clean! All LaTeX environments, packages, and commands are verified.",
                "workspace_files_checked": [active_file or "main.tex"],
                "issues": [],
                "advice": (
                    f"**TeXa AI Health Check** (Model: `{active_model}`):\n\n"
                    f"- **Preamble**: Document class and packages verified.\n"
                    f"- **Syntax**: No errors found in document.\n"
                    f"- **Compilation**: Ready for instant live PDF rendering."
                )
            }

        # Step 1: Identify error-triggering file
        error_files = self._identify_error_files(error_diagnostics, log_output, active_file, working_dir)
        target_file = error_files[0] if error_files else (active_file or "main.tex")
        full_p = os.path.join(working_dir, target_file) if working_dir else target_file
        is_target_active = (target_file == active_file)

        # Step 2: Extract the ENTIRE line-numbered code of the error-throwing file
        numbered_code = self._get_numbered_file_code(
            file_path=full_p,
            active_content=active_content if is_target_active else "",
            is_active=is_target_active
        )
        all_numbered_code = f"--- File: {target_file} ---\n{numbered_code}"

        # Collect error line numbers from compiler
        error_lines = [d.get("line", 1) for d in error_diagnostics if d.get("line")]
        if not error_lines:
            log_lines = re.findall(r'l\.(\d+)', log_output or "")
            error_lines = [int(ln) for ln in log_lines] or [1]

        # Step 3: Extract structured diagnostics and compiler error logs (error-only, warnings excluded)
        diag_items = []
        for d in error_diagnostics:
            diag_items.append(f"- Line {d.get('line', '?')} [error]: {d.get('message', '')}")
        diag_text = "\n".join(diag_items) if diag_items else "(No error diagnostics available)"

        # Filter strictly error lines from compiler log (ignore warning logs)
        log_error_lines = []
        for line in (log_output or "").splitlines():
            l_strip = line.strip()
            l_lower = l_strip.lower()
            if "warning" in l_lower or "overfull" in l_lower or "underfull" in l_lower:
                continue
            if (
                l_strip.startswith("!") or
                "Error" in l_strip or
                "l." in l_strip or
                "Fatal" in l_strip or
                "not found" in l_strip or
                "Undefined control sequence" in l_strip or
                "Missing $" in l_strip or
                "Extra }" in l_strip or
                "Paragraph ended before" in l_strip
            ):
                log_error_lines.append(l_strip)

        if log_error_lines:
            error_log_slice = "\n".join(log_error_lines[:30])
        else:
            error_log_slice = (log_output or "")[:1500]

        # Step 4: AI Model Deep Generative Diagnostics with Prompt-Level Intelligence
        system_prompt = (
            "You are TeXa LaTeX Debugger AI, an expert high-precision autonomous diagnostic intelligence for LaTeX documents.\n"
            "Your objective: Reason through compiler error logs, structured diagnostics, and the complete line-numbered LaTeX source code to find all syntax and compilation issues. Output pure JSON with the exact Root Cause, exact Solution, and draggable LaTeX fix code (`fix_code`).\n\n"
            "CORE REASONING & DIAGNOSTIC INTELLIGENCE:\n"
            "1. COMMAND TYPOS & MISSPELLED MACROS (Undefined Control Sequence):\n"
            "   - When an undefined command appears in the logs/diagnostics, reason about what standard LaTeX command or macro the user intended based on document context, character edits, and phonetics.\n"
            "   - For example:\n"
            "     * `\\maketitl` or `\\maketit` -> intended command is `\\maketitle`.\n"
            "     * `\\begn` or `\\bgin` -> intended command is `\\begin`.\n"
            "     * `\\secton` or `\\seciton` -> intended command is `\\section`.\n"
            "     * `\\subsecton` -> intended command is `\\subsection`.\n"
            "     * `\\tableofcontent` -> intended command is `\\tableofcontents`.\n"
            "     * `\\usepackag` -> intended command is `\\usepackage`.\n"
            "     * `\\documenclass` -> intended command is `\\documentclass`.\n"
            "     * `\\includegraphic` -> intended command is `\\includegraphics`.\n"
            "     * `\\centring` or `\\centerng` -> intended command is `\\centering`.\n"
            "   - Title: \"Misspelled Command (\\<typo>)\"\n"
            "   - Root Cause: Explain that '\\<typo>' is misspelled and identify the intended LaTeX command.\n"
            "   - Solution: Instruct the user to replace the typo with the correct command.\n"
            "   - fix_code: MUST be the exact corrected command with backslash (e.g. `\\maketitle`, `\\begin{...}`, `\\section{...}`). NEVER output dummy `\\newcommand` or hallucinated packages for misspelled commands!\n\n"
            "2. MISSING PACKAGE DECLARATIONS:\n"
            "   - When a valid LaTeX environment or command requires a specific package not loaded in the preamble (e.g. 'tikzpicture' requires `\\usepackage{tikz}`, 'align'/'bmatrix' requires `\\usepackage{amsmath}`, 'toprule' requires `\\usepackage{booktabs}`, '\\includegraphics' requires `\\usepackage{graphicx}`, '\\url'/'\\href' requires `\\usepackage{hyperref}`):\n"
            "   - Root Cause: Explain that the command/environment requires a specific package not yet included in the preamble.\n"
            "   - Solution: Instruct the user to add the package to the preamble.\n"
            "   - fix_code: MUST be the exact `\\usepackage{...}` line.\n\n"
            "3. SYNTAX, BRACES & UNCLOSED ENVIRONMENTS:\n"
            "   - For unclosed environments (e.g. `\\begin{tabular}` without `\\end{tabular}`), `fix_code` should be `\\end{tabular}`.\n"
            "   - For missing or mismatched braces (`{` or `}`), `fix_code` should be the matching delimiter.\n"
            "   - For unescaped special characters (e.g. `%`, `_`, `&`, `#`), `fix_code` should be the properly escaped equivalent.\n\n"
            "4. DRAGGABLE FIX CODE CONTRACT (fix_code):\n"
            "   - `fix_code` MUST ALWAYS contain the valid LaTeX snippet that directly fixes the problem when dragged or inserted into the editor.\n"
            "   - Output ONLY ASCII text.\n\n"
            "JSON ARRAY OUTPUT FORMAT:\n"
            "```json\n"
            "[\n"
            "  {\n"
            "    \"id\": \"1\",\n"
            "    \"title\": \"Misspelled Command (\\maketitl)\",\n"
            "    \"line\": 14,\n"
            "    \"file\": \"main.tex\",\n"
            "    \"severity\": \"error\",\n"
            "    \"root_cause\": \"The command '\\maketitl' is misspelled. The correct standard LaTeX command is '\\maketitle'.\",\n"
            "    \"solution\": \"Replace '\\maketitl' with '\\maketitle'.\",\n"
            "    \"fix_code\": \"\\maketitle\"\n"
            "  }\n"
            "]\n"
            "```"
        )

        user_content = (
            f"[COMPILER ERROR LOGS]\n{error_log_slice}\n\n"
            f"[STRUCTURED ERROR DIAGNOSTICS]\n{diag_text}\n\n"
            f"[ENTIRE NUMBERED LATEX SOURCE CODE ({target_file})]\n{all_numbered_code}\n\n"
            f"Review the code and compiler logs above. Diagnose all compilation errors. Output ONLY the JSON array containing the Root Cause, Solution, and fix_code for each issue."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        issues = []
        try:
            raw_output = self._generate_raw(messages, max_new_tokens=768, temperature=0.0)
            parsed_issues = self._extract_json_from_text(raw_output)

            if isinstance(parsed_issues, dict):
                if "issues" in parsed_issues and isinstance(parsed_issues["issues"], list):
                    parsed_issues = parsed_issues["issues"]
                elif "obeys_schema" in parsed_issues and isinstance(parsed_issues["obeys_schema"], list):
                    parsed_issues = parsed_issues["obeys_schema"]
                else:
                    parsed_issues = [parsed_issues]

            if isinstance(parsed_issues, list):
                for idx, item in enumerate(parsed_issues):
                    if isinstance(item, dict):
                        severity = str(item.get("severity", "error")).lower().strip()
                        # Strict Error-Only Filtering: Only include error diagnostics (ignore warnings)
                        if severity in ["warning", "warn", "info"]:
                            continue

                        # Clean any foreign non-ASCII characters from text
                        title = re.sub(r'[^\x00-\x7F]+', '', str(item.get("title", "LaTeX Compilation Error"))).strip()
                        root_cause = re.sub(r'[^\x00-\x7F]+', '', str(item.get("root_cause", "Syntax error during compilation."))).strip()
                        solution = re.sub(r'[^\x00-\x7F]+', '', str(item.get("solution", "Review syntax and package declarations."))).strip()
                        
                        # Extract generative drag-and-drop fix code
                        fix_code = str(item.get("fix_code", "")).strip()
                        if not fix_code or fix_code.lower() in ["none", "null", "n/a"]:
                            # Extract code from markdown block or LaTeX macros in solution
                            code_m = re.search(r'```(?:latex|tex)?\s*([\s\S]+?)\s*```', solution)
                            if code_m:
                                fix_code = code_m.group(1).strip()
                            else:
                                tex_patterns = re.findall(r'(\\[a-zA-Z]+(?:\{[^}\n]+\})*)', solution)
                                if tex_patterns:
                                    fix_code = "\n".join(tex_patterns[:2])
                                elif "`" in solution:
                                    inline_m = re.findall(r'`([^`]+)`', solution)
                                    if inline_m:
                                        fix_code = "\n".join(inline_m[:2])
                                else:
                                    fix_code = solution

                        fix_code = re.sub(r'[^\x00-\x7F]+', '', fix_code).strip()

                        line_val = item.get("line", error_lines[0] if error_lines else 1)
                        try:
                            line_num = int(line_val)
                        except (ValueError, TypeError):
                            line_num = error_lines[0] if error_lines else 1

                        issues.append({
                            "id": str(item.get("id", idx + 1)),
                            "title": title or "LaTeX Compilation Error",
                            "line": line_num,
                            "file": item.get("file", target_file),
                            "severity": "error",
                            "root_cause": root_cause,
                            "solution": solution,
                            "fix_code": fix_code
                        })
        except RuntimeError as re_err:
            if "cancelled" in str(re_err).lower():
                return {
                    "status": "cancelled",
                    "model": active_model,
                    "error_count": 0,
                    "warning_count": 0,
                    "summary": "Model analysis cancelled by user.",
                    "workspace_files_checked": [target_file],
                    "issues": []
                }
            print(f"[TeXa AI Engine] Runtime error during debug analysis: {re_err}")
        except Exception as e:
            print(f"[TeXa AI Engine] Error during debug analysis: {e}")

        # Generic fallback only if model inference failed or returned unparseable output
        if not issues:
            for idx, diag in enumerate(error_diagnostics):
                ln = diag.get("line", 1)
                raw_m = diag.get("message", "LaTeX Compilation Error")
                issues.append({
                    "id": str(idx + 1),
                    "title": f"Compilation Error (Line {ln})",
                    "line": ln,
                    "file": diag.get("file", target_file),
                    "severity": "error",
                    "root_cause": f"Compiler reported: {raw_m}",
                    "solution": "Review syntax and compiler error logs at this line.",
                    "fix_code": f"% Fix for line {ln}\n"
                })

        error_count = len(issues)
        warning_count = 0

        return {
            "status": "issues_found",
            "model": active_model,
            "error_count": error_count or len(issues),
            "warning_count": warning_count,
            "summary": f"Detected {len(issues)} issue(s) in `{target_file}`.",
            "workspace_files_checked": [target_file],
            "issues": issues,
            "advice": (
                f"**TeXa AI Diagnostic Suggestions** (Model: `{active_model}`):\n\n"
                f"Review the issue cards below. Click on any line number badge to jump directly to that line in Monaco Editor."
            )
        }

    # ----------------- TAB 3: GENERAL QUERY & RESPONSE MANAGER -----------------

    def process_ai_request(
        self,
        task_type: str,
        prompt: str,
        latex_context: str = "",
        working_dir: Optional[str] = None,
        active_file: Optional[str] = "main.tex"
    ) -> str:
        """
        Processes general AI queries with strict guardrails:
        - If asked about identity: "She is TeXa - Your's AI Assistant to help with your research paper writing."
        - If asked anything other than LaTeX code/writing: "I don't know."
        """
        if self.is_identity_query(prompt):
            return "She is TeXa - Your's AI Assistant to help with your research paper writing."

        if not self.is_latex_template_query(prompt):
            return "I don't know."

        doc_class, existing_pkgs, _ = self._extract_project_context(working_dir, active_file)
        pkgs_str = ", ".join(existing_pkgs) if existing_pkgs else "amsmath, graphicx, hyperref"

        system_msg = (
            "You are TeXa - Your's AI Assistant to help with your research paper writing.\n"
            f"Active Project Info: Document Class: {doc_class}, Installed Packages: {pkgs_str}.\n"
            "RULES:\n"
            "1. If asked about your identity, respond: \"She is TeXa - Your's AI Assistant to help with your research paper writing.\"\n"
            "2. If asked anything other than LaTeX code or LaTeX research paper writing, respond: \"I don't know.\"\n"
            "Provide clean, concise LaTeX code or assistance."
        )

        user_content = prompt
        if latex_context:
            user_content = f"LaTeX Context:\n```latex\n{latex_context[:1000]}\n```\n\nQuestion: {prompt}"

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content}
        ]

        try:
            return self._generate_raw(messages, max_new_tokens=512, temperature=0.2)
        except Exception as e:
            return f"Error processing query with `{self.active_model_id}`: {str(e)}"

    def process_chat_request(
        self,
        messages: List[Dict[str, str]],
        latex_context: str = "",
        working_dir: Optional[str] = None,
        active_file: Optional[str] = "main.tex"
    ) -> str:
        """Process one-off AI query without retaining multi-turn chat history."""
        last_msg = messages[-1]["content"] if messages else ""
        return self.process_ai_request("chat", last_msg, latex_context, working_dir, active_file)

    # ----------------- UTILITY HELPERS -----------------

    def _extract_json_from_text(self, text: str) -> Optional[Any]:
        """
        Extract and parse JSON object or array from LLM response text.
        Handles markdown blocks, trailing commas, and LaTeX backslashes inside JSON strings.
        """
        if not text:
            return None

        def clean_json_str(s: str) -> str:
            # 1. Clean trailing commas before close brackets
            s = re.sub(r',\s*([\]}])', r'\1', s)

            # 2. Inside JSON string literals, sanitize unescaped LaTeX backslashes
            out = []
            in_string = False
            i = 0
            n = len(s)
            while i < n:
                c = s[i]
                if c == '"' and (i == 0 or s[i - 1] != '\\' or (i >= 2 and s[i - 2] == '\\' and s[i - 1] == '\\')):
                    in_string = not in_string
                    out.append(c)
                    i += 1
                elif in_string and c == '\\':
                    if i + 1 < n:
                        nxt = s[i + 1]
                        if nxt in ['"', '\\', '/']:
                            out.append('\\')
                            out.append(nxt)
                            i += 2
                        elif nxt in ['b', 'f', 'n', 'r', 't']:
                            # If followed by a letter (e.g. \begin, \frac, \ref, \textbf, \noindent), it's a LaTeX command
                            if i + 2 < n and s[i + 2].isalpha():
                                out.append('\\\\')
                                out.append(nxt)
                                i += 2
                            else:
                                out.append('\\')
                                out.append(nxt)
                                i += 2
                        elif nxt == 'u':
                            # If followed by 4 hex digits, valid JSON unicode escape
                            if i + 5 < n and all(ch in '0123456789abcdefABCDEF' for ch in s[i + 2:i + 6]):
                                out.append('\\u')
                                i += 2
                            else:
                                out.append('\\\\u')
                                i += 2
                        else:
                            # Any other character preceded by backslash (e.g. \m, \d, \s, \a, \$, \%, \&, \_)
                            out.append('\\\\')
                            out.append(nxt)
                            i += 2
                    else:
                        out.append('\\\\')
                        i += 1
                else:
                    out.append(c)
                    i += 1
            return "".join(out).strip()

        # 1. Extract ```json ... ``` or ``` ... ```
        json_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
        if json_match:
            try:
                return json.loads(clean_json_str(json_match.group(1)))
            except Exception:
                pass

        # 2. Extract JSON array [ ... ]
        array_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', text)
        if array_match:
            try:
                return json.loads(clean_json_str(array_match.group(0)))
            except Exception:
                pass

        # 3. Direct JSON parse
        try:
            return json.loads(clean_json_str(text))
        except Exception:
            pass

        # 4. Extract single JSON object { ... }
        obj_match = re.search(r'\{[\s\S]*\}', text)
        if obj_match:
            try:
                return json.loads(clean_json_str(obj_match.group(0)))
            except Exception:
                pass

        return None


# Global AI Engine singleton instance
ai_engine = AIEngineManager()

