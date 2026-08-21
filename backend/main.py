"""
TeXa FastAPI Server Main Entry Point
Exposes REST APIs, WebSockets, static file server for TeXa web application.
"""

import os
import time
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from backend.config import config_state
from backend.latex_engine import latex_engine
from backend.ai_engine import ai_engine
from backend.file_manager import file_manager

app = FastAPI(title="TeXa - AI-Powered LaTeX Editor API", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active websocket log connections
active_connections: List[WebSocket] = []

async def broadcast_log(message: str):
    """Broadcast raw compilation log or status updates to all active WebSocket clients."""
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception:
            pass

# Request / Response Pydantic Models
class ConfigUpdateRequest(BaseModel):
    working_directory: Optional[str] = None
    active_file: Optional[str] = None
    selected_model: Optional[str] = None
    custom_model_id: Optional[str] = None
    hf_token: Optional[str] = None
    compiler_engine: Optional[str] = None
    auto_validate: Optional[bool] = None
    theme: Optional[str] = None

class SaveFileRequest(BaseModel):
    rel_path: str = "main.tex"
    content: str

class CompileRequest(BaseModel):
    rel_path: str = "main.tex"
    content: Optional[str] = None

class SelectModelRequest(BaseModel):
    model_id: str
    is_custom: bool = False
    hf_token: Optional[str] = None

class SetHFTokenRequest(BaseModel):
    hf_token: str

class AIPromptRequest(BaseModel):
    task_type: str = "custom"  # 'custom', 'fix_error', 'explain', 'generate_equation'
    prompt: str = ""
    latex_context: str = ""

class CreateFileRequest(BaseModel):
    rel_path: str
    content: Optional[str] = ""
    overwrite: Optional[bool] = False

class CreateFolderRequest(BaseModel):
    rel_path: str
    overwrite: Optional[bool] = False

class RenameFileRequest(BaseModel):
    old_rel_path: str
    new_rel_path: str

class AIChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    latex_context: Optional[str] = ""

class AICodeTemplateRequest(BaseModel):
    prompt: str
    model_id: Optional[str] = None

class AIDebugRequest(BaseModel):
    diagnostics: Optional[List[Dict[str, Any]]] = []
    log_output: Optional[str] = ""
    active_file: Optional[str] = "main.tex"
    active_content: Optional[str] = ""

class LoadModelRequest(BaseModel):
    model_id: str
    hf_token: Optional[str] = None

# ----------------- CONFIGURATION ENDPOINTS -----------------

@app.get("/api/config")
def get_config():
    """Fetch current app configuration state."""
    return config_state.get_config()

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    """Update app configuration."""
    updated = config_state.update_config(req.model_dump(exclude_unset=True))
    return updated

@app.post("/api/browse-directory")
def browse_directory():
    """
    Opens native system folder chooser dialog and returns the selected directory path.
    On macOS: uses native AppleScript osascript folder picker.
    Fallback: uses Tkinter askdirectory if available.
    """
    import subprocess
    import platform

    chosen_path = None
    system_os = platform.system().lower()

    if system_os == "darwin":
        try:
            script = (
                'tell application "System Events"\n'
                'activate\n'
                'set chosenFolder to choose folder with prompt "Select TeXa Working Directory"\n'
                'return POSIX path of chosenFolder\n'
                'end tell'
            )
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=180
            )
            if result.returncode == 0:
                raw_path = result.stdout.strip()
                if raw_path:
                    chosen_path = raw_path
        except Exception as osascript_err:
            print(f"[TeXa Workspace] osascript directory chooser warning: {osascript_err}")

    # Fallback to Tkinter on other platforms or if osascript failed
    if not chosen_path:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            raw_path = filedialog.askdirectory(title="Select TeXa Working Directory")
            root.destroy()
            if raw_path:
                chosen_path = str(raw_path).strip()
        except Exception as tk_err:
            print(f"[TeXa Workspace] Tkinter fallback folder chooser warning: {tk_err}")

    if chosen_path:
        # Normalize and remove trailing slash (except root '/')
        chosen_path = os.path.expanduser(chosen_path.strip())
        if len(chosen_path) > 1 and chosen_path.endswith("/"):
            chosen_path = chosen_path.rstrip("/")

        os.makedirs(chosen_path, exist_ok=True)
        # Ensure default main.tex exists if directory is empty
        main_tex = os.path.join(chosen_path, "main.tex")
        if not os.path.exists(main_tex):
            from backend.file_manager import DEFAULT_LATEX_TEMPLATE
            try:
                with open(main_tex, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_LATEX_TEMPLATE)
            except Exception as write_err:
                print(f"[TeXa Workspace] Warning creating default main.tex: {write_err}")

        config_state.update_config({"working_directory": chosen_path})
        return {
            "status": "ok",
            "path": chosen_path,
            "exists": os.path.exists(chosen_path)
        }

    return {
        "status": "cancelled",
        "path": config_state.get_config().working_directory
    }

@app.get("/api/engines")
def get_engines():
    """Detect installed LaTeX compilers on system."""
    return latex_engine.detect_engines()

# ----------------- FILE MANAGER ENDPOINTS -----------------

@app.get("/api/files")
def list_files():
    """List files in active project working directory in hierarchical order."""
    cfg = config_state.get_config()
    files = file_manager.list_files(cfg.working_directory)
    return {"files": files, "count": len(files)}

@app.get("/api/file/read")
def read_file(path: str = "main.tex"):
    """Read a specific document file."""
    cfg = config_state.get_config()
    try:
        content = file_manager.read_file(cfg.working_directory, path)
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/file/save")
def save_file(req: SaveFileRequest):
    """Save document file content."""
    cfg = config_state.get_config()
    try:
        file_manager.write_file(cfg.working_directory, req.rel_path, req.content)
        return {"status": "success", "path": req.rel_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/file/create")
def create_file(req: CreateFileRequest):
    """Create a new file in active workspace. Return exists status if duplicate."""
    cfg = config_state.get_config()
    try:
        file_manager.create_file(cfg.working_directory, req.rel_path, req.content or "", req.overwrite or False)
        return {"status": "success", "path": req.rel_path}
    except FileExistsError as e:
        return {"status": "exists", "message": str(e), "path": req.rel_path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/folder/create")
def create_folder(req: CreateFolderRequest):
    """Create a new folder in active workspace. Return exists status if duplicate."""
    cfg = config_state.get_config()
    try:
        file_manager.create_folder(cfg.working_directory, req.rel_path, req.overwrite or False)
        return {"status": "success", "path": req.rel_path}
    except FileExistsError as e:
        return {"status": "exists", "message": str(e), "path": req.rel_path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/file/rename")
def rename_file(req: RenameFileRequest):
    """Rename an existing file in workspace."""
    cfg = config_state.get_config()
    try:
        file_manager.rename_file(cfg.working_directory, req.old_rel_path, req.new_rel_path)
        return {"status": "success", "old_path": req.old_rel_path, "new_path": req.new_rel_path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class DeleteFileRequest(BaseModel):
    """Request model for deleting a file or folder."""
    rel_path: str  # Relative path of file/folder to delete


@app.delete("/api/file/delete")
def delete_file(req: DeleteFileRequest):
    """Permanently delete a file or folder from the active workspace."""
    cfg = config_state.get_config()
    try:
        file_manager.delete_file(cfg.working_directory, req.rel_path)
        return {"status": "success", "path": req.rel_path}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------- COMPILATION ENDPOINTS -----------------

@app.post("/api/compile")
async def compile_document(req: CompileRequest):
    """
    Compile LaTeX document using chosen hybrid engine.
    Performs continuous validation & returns diagnostics + output log.
    Always ensures the output PDF is updated and cache-busted for the live preview.
    """
    cfg = config_state.get_config()
    
    # Auto-save file content if provided in request
    if req.content is not None:
        file_manager.write_file(cfg.working_directory, req.rel_path, req.content)

    # Perform compilation
    success, pdf_path, diagnostics, log_output = latex_engine.compile(
        working_dir=cfg.working_directory,
        main_file=req.rel_path,
        engine_preference=cfg.compiler_engine
    )

    # Broadcast log to websocket
    await broadcast_log(log_output)

    pdf_available = bool(success and pdf_path and os.path.exists(pdf_path))
    pdf_filename = os.path.basename(pdf_path) if (pdf_path and os.path.exists(pdf_path)) else f"{os.path.splitext(os.path.basename(req.rel_path))[0]}.pdf"
    cache_bust = int(time.time() * 1000)

    return {
        "success": success,
        "pdf_available": pdf_available,
        "pdf_url": f"/api/pdf?file={pdf_filename}&t={cache_bust}" if pdf_available else None,
        "pdf_filename": pdf_filename,
        "timestamp": cache_bust,
        "diagnostics": diagnostics,
        "log_output": log_output
    }

@app.get("/api/pdf")
def get_pdf(file: Optional[str] = Query(None), t: Optional[str] = Query(None)):
    """
    Serve compiled PDF binary for PDF viewer frame with strict cache-busting headers.
    Ensures browser preview immediately refreshes whenever a newly compiled PDF is saved.
    """
    cfg = config_state.get_config()
    target_file = file or (os.path.splitext(cfg.active_file)[0] + ".pdf")
    pdf_path = os.path.join(cfg.working_directory, target_file)

    if not os.path.exists(pdf_path):
        # Trigger on-demand compilation if PDF file is not present yet
        latex_engine.compile(cfg.working_directory, cfg.active_file)

    if not os.path.exists(pdf_path):
        # Fallback to active file .pdf
        base_name = os.path.splitext(cfg.active_file)[0]
        fallback_path = os.path.join(cfg.working_directory, f"{base_name}.pdf")
        if os.path.exists(fallback_path):
            pdf_path = fallback_path

    if not os.path.exists(pdf_path):
        # Fallback to main.pdf
        fallback_main = os.path.join(cfg.working_directory, "main.pdf")
        if os.path.exists(fallback_main):
            pdf_path = fallback_main

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF output could not be generated.")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={os.path.basename(pdf_path)}",
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0, post-check=0, pre-check=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

# ----------------- AI ENGINE ENDPOINTS -----------------

@app.get("/api/ai/models")
def get_ai_models():
    """Get downloaded model list and current model loading status."""
    return {
        "presets": ai_engine.get_presets(),
        "status": ai_engine.get_status()
    }

@app.post("/api/ai/token")
def set_hf_token(req: SetHFTokenRequest):
    """Save Hugging Face Access Token to .env and runtime state."""
    token_val = req.hf_token.strip()
    config_state.update_config({"hf_token": token_val})
    ai_engine.set_hf_token(token_val)
    return {
        "status": "success",
        "message": "Hugging Face token saved to .env and active runtime."
    }

@app.post("/api/ai/select")
def select_ai_model(req: SelectModelRequest):
    """Select and trigger download/load for Hugging Face model."""
    model_id = req.model_id.strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="Model ID cannot be empty.")
    
    # Save HF token if provided
    if req.hf_token:
        config_state.update_config({"hf_token": req.hf_token.strip()})
        ai_engine.set_hf_token(req.hf_token.strip())

    # Update app configuration
    config_state.update_config({
        "selected_model": model_id,
        "custom_model_id": model_id if req.is_custom else None
    })

    # Trigger background download
    ai_engine.start_model_download(model_id, req.hf_token)

    return {
        "status": "downloading",
        "selected_model": model_id,
        "message": f"Download initiated for {model_id}. Meanwhile, sit back, relax, and grab a coffee ☕!"
    }

@app.post("/api/ai/load")
async def load_ai_model(req: LoadModelRequest):
    """
    Explicitly load and activate selected model into memory.
    Invoked when user launches TeXa editor.
    """
    model_id = req.model_id.strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="Model ID cannot be empty.")
    
    if req.hf_token:
        config_state.update_config({"hf_token": req.hf_token.strip()})
        ai_engine.set_hf_token(req.hf_token.strip())

    # Run heavy model loading in a background worker thread to keep server responsive
    success = await asyncio.to_thread(ai_engine.load_model, model_id)
    if not success:
        raise HTTPException(status_code=500, detail=ai_engine.status_message)

    config_state.update_config({"selected_model": model_id})
    return {
        "status": "ready",
        "model_id": model_id,
        "message": f"Model {model_id} loaded successfully."
    }

@app.get("/api/ai/status")
def get_ai_status():
    """Get live download/load progress of active model."""
    return ai_engine.get_status()

@app.post("/api/ai/prompt")
async def process_ai_prompt(req: AIPromptRequest):
    """Process user AI prompt against active model asynchronously."""
    cfg = config_state.get_config()
    response_text = await asyncio.to_thread(
        ai_engine.process_ai_request,
        task_type=req.task_type,
        prompt=req.prompt,
        latex_context=req.latex_context,
        working_dir=cfg.working_directory,
        active_file=cfg.active_file
    )
    return {
        "model": ai_engine.active_model_id,
        "task_type": req.task_type,
        "response": response_text
    }

@app.post("/api/ai/chat")
async def process_ai_chat(req: AIChatRequest):
    """Process interactive chat conversation thread against active model asynchronously."""
    cfg = config_state.get_config()
    response_text = await asyncio.to_thread(
        ai_engine.process_chat_request,
        messages=req.messages,
        latex_context=req.latex_context or "",
        working_dir=cfg.working_directory,
        active_file=cfg.active_file
    )
    return {
        "model": cfg.selected_model or ai_engine.active_model_id,
        "response": response_text
    }

@app.post("/api/ai/code-template")
async def process_code_template(req: AICodeTemplateRequest):
    """
    Generate LaTeX code snippet template asynchronously with prompt guardrails
    and project reference context.
    Strictly returns 'I don't know.' if prompt is not asking for a LaTeX template.
    """
    cfg = config_state.get_config()
    model_to_use = req.model_id or cfg.selected_model or ai_engine.active_model_id
    result = await asyncio.to_thread(
        ai_engine.generate_code_template,
        prompt=req.prompt,
        model_id=model_to_use,
        working_dir=cfg.working_directory,
        active_file=cfg.active_file
    )
    return result

@app.post("/api/ai/debug")
async def process_debug_analysis(req: AIDebugRequest):
    """
    Perform deep diagnostics and console log analysis against working directory files asynchronously.
    Identifies error-triggering files, preprocesses with numbered lines, and generates fix suggestions.
    Strictly focuses on error diagnostics only (warnings excluded).
    """
    cfg = config_state.get_config()
    model_to_use = cfg.selected_model or ai_engine.active_model_id
    error_diags = [d for d in (req.diagnostics or []) if d.get("severity") == "error"]
    result = await asyncio.to_thread(
        ai_engine.debug_document_errors,
        diagnostics=error_diags,
        log_output=req.log_output or "",
        active_file=req.active_file or cfg.active_file,
        active_content=req.active_content or "",
        working_dir=cfg.working_directory,
        model_id=model_to_use
    )
    return result

@app.post("/api/ai/cancel")
def cancel_ai_generation():
    """
    Terminates any active local AI model inference immediately.
    Triggered when user closes the AI Assistant box or aborts a task.
    """
    ai_engine.cancel_generation()
    return {"status": "cancelled", "message": "Model generation cancelled successfully"}



# ----------------- WEBSOCKET FOR LIVE LOGS -----------------

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# ----------------- STATIC FRONTEND MOUNTING & ROOT HANDLERS -----------------

frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

@app.get("/")
def serve_root_index():
    """Serve single-page frontend application index."""
    index_file = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return Response(
        content="<html><body><h2>TeXa editor frontend is initializing. Please refresh in a moment.</h2></body></html>",
        media_type="text/html"
    )

@app.get("/favicon.ico")
def serve_favicon():
    """Serve application favicon if available."""
    fav_file = os.path.join(frontend_dist, "favicon.ico")
    if os.path.exists(fav_file):
        return FileResponse(fav_file)
    return Response(status_code=204)

if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

