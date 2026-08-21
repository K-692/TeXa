"""
TeXa Backend Configuration & Global State Manager
Maintains app settings: working directory, selected AI model, compiler preference, and active state.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field
import dotenv

# Load environment variables from .env if present in project root
TEXA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(TEXA_DIR, ".env")
if os.path.exists(ENV_PATH):
    dotenv.load_dotenv(ENV_PATH)

class AppConfig(BaseModel):
    """Configuration model for TeXa application."""
    working_directory: str = Field(default_factory=lambda: os.environ.get("WORKING_DIRECTORY") or os.path.expanduser("~/TeXa_Projects"))
    active_file: str = "main.tex"
    selected_model: Optional[str] = None
    custom_model_id: Optional[str] = None
    hf_token: Optional[str] = Field(default_factory=lambda: os.environ.get("HF_TOKEN"))
    compiler_engine: str = "hybrid"  # Options: 'hybrid', 'tectonic', 'latexmk'
    auto_validate: bool = True       # Continuous Validation toggle (VS Code style)
    theme: str = "dark"              # Theme preference: 'dark' or 'light'

class ConfigState:
    """Singleton configuration manager for backend runtime."""
    def __init__(self):
        self.config = AppConfig()
        # Ensure default project directory exists and is normalized to absolute path
        raw_dir = self.config.working_directory
        if not os.path.isabs(raw_dir):
            norm_dir = os.path.abspath(os.path.join(TEXA_DIR, raw_dir))
        else:
            norm_dir = os.path.abspath(os.path.expanduser(raw_dir))
        self.config.working_directory = norm_dir
        os.makedirs(norm_dir, exist_ok=True)

    def get_config(self) -> AppConfig:
        # Refresh HF_TOKEN from environment if set
        if not self.config.hf_token and os.environ.get("HF_TOKEN"):
            self.config.hf_token = os.environ.get("HF_TOKEN")
        return self.config

    def update_config(self, new_data: dict) -> AppConfig:
        for key, value in new_data.items():
            if hasattr(self.config, key) and value is not None:
                if key == "working_directory":
                    raw_val = str(value).strip()
                    if not os.path.isabs(raw_val):
                        dir_val = os.path.abspath(os.path.join(TEXA_DIR, raw_val))
                    else:
                        dir_val = os.path.abspath(os.path.expanduser(raw_val))
                    if len(dir_val) > 1 and dir_val.endswith("/"):
                        dir_val = dir_val.rstrip("/")
                    os.makedirs(dir_val, exist_ok=True)
                    setattr(self.config, key, dir_val)
                    os.environ["WORKING_DIRECTORY"] = dir_val
                    try:
                        if os.path.exists(ENV_PATH):
                            dotenv.set_key(ENV_PATH, "WORKING_DIRECTORY", dir_val)
                    except Exception:
                        pass
                else:
                    setattr(self.config, key, value)

        # If hf_token was updated, persist to .env and environment
        if "hf_token" in new_data and new_data["hf_token"] is not None:
            token_val = str(new_data["hf_token"]).strip()
            os.environ["HF_TOKEN"] = token_val
            self.config.hf_token = token_val
            try:
                # Ensure .env file exists
                if not os.path.exists(ENV_PATH):
                    with open(ENV_PATH, "w") as f:
                        f.write(f"HF_TOKEN={token_val}\n")
                else:
                    dotenv.set_key(ENV_PATH, "HF_TOKEN", token_val)
            except Exception as e:
                print(f"[TeXa Config] Warning: Could not persist HF_TOKEN to .env: {e}")

        return self.config

# Global instance
config_state = ConfigState()

