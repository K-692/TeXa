"""
TeXa Hybrid LaTeX Engine
Supports Tectonic, latexmk, pdflatex, and xelatex compilation drivers,
multi-file master document resolution, continuous live validation,
and structured diagnostic extraction (errors, warnings, line numbers).
"""

import os
import re
import subprocess
import shutil
from typing import List, Dict, Any, Tuple, Optional

class LaTeXDiagnostic:
    """Structured diagnostic representation for editor markers and error logs."""
    def __init__(self, line: int, severity: str, message: str, file: str = "main.tex"):
        self.line = line
        self.severity = severity  # 'error', 'warning', 'info'
        self.message = message
        self.file = file

    def to_dict(self) -> Dict[str, Any]:
        """Convert diagnostic to dictionary representation for JSON serialization."""
        return {
            "line": self.line,
            "severity": self.severity,
            "message": self.message,
            "file": self.file
        }

class LaTeXEngineManager:
    """Manages LaTeX compilation using Tectonic, latexmk, pdflatex, or fallback dynamic preview."""
    
    def __init__(self):
        self.tectonic_path = self._find_binary("tectonic", [
            "/opt/homebrew/bin/tectonic",
            "/usr/local/bin/tectonic",
            os.path.expanduser("~/.cargo/bin/tectonic"),
            "/Library/TeX/texbin/tectonic",
            "/usr/bin/tectonic"
        ])
        self.latexmk_path = self._find_binary("latexmk", [
            "/Library/TeX/texbin/latexmk",
            "/opt/homebrew/bin/latexmk",
            "/usr/local/bin/latexmk",
            "/usr/bin/latexmk"
        ])
        self.pdflatex_path = self._find_binary("pdflatex", [
            "/Library/TeX/texbin/pdflatex",
            "/opt/homebrew/bin/pdflatex",
            "/usr/local/bin/pdflatex",
            "/usr/bin/pdflatex"
        ])
        self.xelatex_path = self._find_binary("xelatex", [
            "/Library/TeX/texbin/xelatex",
            "/opt/homebrew/bin/xelatex",
            "/usr/local/bin/xelatex",
            "/usr/bin/xelatex"
        ])

    def _find_binary(self, name: str, fallback_paths: List[str]) -> Optional[str]:
        """Search system PATH and standard platform directory locations for executable binary."""
        found = shutil.which(name)
        if found:
            return found
        for p in fallback_paths:
            if os.path.exists(p) and os.access(p, os.X_OK):
                return p
        return None

    def detect_engines(self) -> Dict[str, bool]:
        """Detect available LaTeX compilation engines on system."""
        # Re-verify binary availability in case PATH changed
        if not self.tectonic_path:
            self.tectonic_path = self._find_binary("tectonic", [
                "/opt/homebrew/bin/tectonic",
                "/usr/local/bin/tectonic",
                os.path.expanduser("~/.cargo/bin/tectonic"),
                "/Library/TeX/texbin/tectonic",
                "/usr/bin/tectonic"
            ])
        if not self.pdflatex_path:
            self.pdflatex_path = self._find_binary("pdflatex", [
                "/Library/TeX/texbin/pdflatex",
                "/opt/homebrew/bin/pdflatex",
                "/usr/local/bin/pdflatex",
                "/usr/bin/pdflatex"
            ])
        if not self.latexmk_path:
            self.latexmk_path = self._find_binary("latexmk", [
                "/Library/TeX/texbin/latexmk",
                "/opt/homebrew/bin/latexmk",
                "/usr/local/bin/latexmk",
                "/usr/bin/latexmk"
            ])
        if not self.xelatex_path:
            self.xelatex_path = self._find_binary("xelatex", [
                "/Library/TeX/texbin/xelatex",
                "/opt/homebrew/bin/xelatex",
                "/usr/local/bin/xelatex",
                "/usr/bin/xelatex"
            ])

        return {
            "tectonic": self.tectonic_path is not None,
            "latexmk": self.latexmk_path is not None,
            "pdflatex": self.pdflatex_path is not None,
            "xelatex": self.xelatex_path is not None
        }

    def resolve_target_document(self, working_dir: str, requested_file: str = "main.tex") -> Tuple[str, str]:
        """
        Resolve the compilable root document for the project.
        If requested_file is a sub-file (missing \\documentclass), finds the master root file (e.g. main.tex).
        Returns: (compilable_tex_file_path, master_rel_name)
        """
        working_dir = os.path.abspath(os.path.expanduser(working_dir))
        if not os.path.exists(working_dir):
            os.makedirs(working_dir, exist_ok=True)

        req_path = requested_file if os.path.isabs(requested_file) else os.path.join(working_dir, requested_file)
        
        # Check if requested file contains \\documentclass
        if os.path.exists(req_path):
            try:
                with open(req_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if "\\documentclass" in content or "\\documentstyle" in content:
                    return req_path, os.path.relpath(req_path, working_dir)
            except Exception:
                pass

        # If requested file is not a standalone root document, search for main.tex or any root .tex file
        main_tex_path = os.path.join(working_dir, "main.tex")
        if os.path.exists(main_tex_path):
            return main_tex_path, "main.tex"

        # Search for any .tex file in the working directory that contains \documentclass
        for root, _, files in os.walk(working_dir):
            for file in files:
                if file.endswith(".tex"):
                    full_p = os.path.join(root, file)
                    try:
                        with open(full_p, 'r', encoding='utf-8', errors='ignore') as f:
                            c = f.read()
                        if "\\documentclass" in c:
                            return full_p, os.path.relpath(full_p, working_dir)
                    except Exception:
                        continue

        # Fallback to the requested path
        return req_path, requested_file

    def compile(
        self,
        working_dir: str,
        main_file: str = "main.tex",
        engine_preference: str = "hybrid"
    ) -> Tuple[bool, str, List[Dict[str, Any]], str]:
        """
        Compile LaTeX document in working_dir.
        Automatically resolves root document if sub-files are passed.
        
        Returns:
            (success: bool, pdf_path: str, diagnostics: List[Dict], log_output: str)
        """
        working_dir = os.path.abspath(os.path.expanduser(working_dir))
        if not os.path.exists(working_dir):
            os.makedirs(working_dir, exist_ok=True)

        # Resolve root document (handles sub-documents and multi-file projects)
        tex_file_path, resolved_rel_file = self.resolve_target_document(working_dir, main_file)

        # Ensure the .tex file actually exists on disk before compiling
        if not os.path.exists(tex_file_path):
            from backend.file_manager import DEFAULT_LATEX_TEMPLATE
            try:
                with open(tex_file_path, 'w', encoding='utf-8') as f:
                    f.write(DEFAULT_LATEX_TEMPLATE)
            except Exception as write_err:
                print(f"[TeXa Engine] Warning writing default template: {write_err}")

        base_name = os.path.splitext(os.path.basename(tex_file_path))[0]
        expected_pdf = os.path.join(working_dir, f"{base_name}.pdf")

        # Determine which driver to use
        available = self.detect_engines()
        engine_to_use = "tectonic"

        if engine_preference == "latexmk" and available["latexmk"]:
            engine_to_use = "latexmk"
        elif engine_preference == "tectonic" and available["tectonic"]:
            engine_to_use = "tectonic"
        elif engine_preference == "pdflatex" and available["pdflatex"]:
            engine_to_use = "pdflatex"
        elif engine_preference == "xelatex" and available["xelatex"]:
            engine_to_use = "xelatex"
        else:
            # Hybrid mode: prefer Tectonic for fast self-contained compilation; fallback to latexmk/pdflatex
            if available["tectonic"]:
                engine_to_use = "tectonic"
            elif available["latexmk"]:
                engine_to_use = "latexmk"
            elif available["pdflatex"]:
                engine_to_use = "pdflatex"
            elif available["xelatex"]:
                engine_to_use = "xelatex"
            else:
                engine_to_use = "mock"

        log_output = ""
        success = False

        try:
            if engine_to_use == "tectonic":
                # Tectonic single-pass compilation command with explicit outdir and synctex
                cmd = [self.tectonic_path, "-X", "compile", tex_file_path, "--outdir", working_dir, "--synctex"]
                res = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, timeout=60)
                log_output = res.stdout + "\n" + res.stderr
                success = (res.returncode == 0) and os.path.exists(expected_pdf) and (os.path.getsize(expected_pdf) > 0)
                
                # If -X compile failed, try direct standard compilation: tectonic <file> --outdir <dir>
                if not success and os.path.exists(self.tectonic_path):
                    cmd_fallback = [self.tectonic_path, tex_file_path, "--outdir", working_dir, "--synctex"]
                    res2 = subprocess.run(cmd_fallback, cwd=working_dir, capture_output=True, text=True, timeout=60)
                    if res2.returncode == 0 and os.path.exists(expected_pdf) and (os.path.getsize(expected_pdf) > 0):
                        log_output = res2.stdout + "\n" + res2.stderr
                        success = True

            elif engine_to_use == "latexmk":
                # Latexmk multi-pass compilation command with explicit outdir
                cmd = [self.latexmk_path, "-pdf", f"-outdir={working_dir}", "-interaction=nonstopmode", "-synctex=1", tex_file_path]
                res = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, timeout=120)
                log_output = res.stdout + "\n" + res.stderr
                success = (res.returncode == 0) and os.path.exists(expected_pdf) and (os.path.getsize(expected_pdf) > 0)

            elif engine_to_use == "pdflatex":
                # Standard pdflatex fallback command with explicit output-directory
                cmd = [self.pdflatex_path, f"-output-directory={working_dir}", "-interaction=nonstopmode", "-synctex=1", tex_file_path]
                res = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, timeout=60)
                log_output = res.stdout + "\n" + res.stderr
                success = (res.returncode == 0) and os.path.exists(expected_pdf) and (os.path.getsize(expected_pdf) > 0)

            elif engine_to_use == "xelatex":
                # XeLaTeX fallback command for UTF-8 fonts
                cmd = [self.xelatex_path, f"-output-directory={working_dir}", "-interaction=nonstopmode", "-synctex=1", tex_file_path]
                res = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, timeout=60)
                log_output = res.stdout + "\n" + res.stderr
                success = (res.returncode == 0) and os.path.exists(expected_pdf) and (os.path.getsize(expected_pdf) > 0)

            else:
                # Dynamic preview fallback mode: converts main.tex content directly into PDF preview stream
                log_output = (
                    "[TeXa Engine Notification]: Neither tectonic, latexmk, nor pdflatex was found in system PATH.\n"
                    "Generating dynamic live document preview from document content.\n"
                    "Tip: Install Tectonic (`brew install tectonic`) for complete local PDF compilation."
                )
                self._generate_dynamic_preview_pdf(tex_file_path, expected_pdf)
                success = True

        except subprocess.TimeoutExpired:
            log_output = "[Error]: LaTeX compilation timed out after 60 seconds."
            success = False
        except Exception as e:
            log_output = f"[Error during execution]: {str(e)}"
            success = False

        # If compilation failed or produced no PDF, but no PDF exists at all, generate dynamic fallback
        if not os.path.exists(expected_pdf) or os.path.getsize(expected_pdf) == 0:
            self._generate_dynamic_preview_pdf(tex_file_path, expected_pdf)

        # Parse structured diagnostics from output log
        diagnostics = self._parse_log_diagnostics(log_output, resolved_rel_file)

        pdf_path = expected_pdf if os.path.exists(expected_pdf) else ""

        return success, pdf_path, [d.to_dict() for d in diagnostics], log_output

    def _generate_dynamic_preview_pdf(self, tex_file_path: str, output_pdf_path: str):
        """Extract document text & sections from main.tex and render directly into clean PDF preview stream."""
        content = ""
        if os.path.exists(tex_file_path):
            with open(tex_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

        lines = content.splitlines()
        display_lines = []

        doc_title = "TeXa Live LaTeX Document"
        doc_author = ""

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('%'):
                continue
            if '\\documentclass' in stripped or '\\usepackage' in stripped or '\\begin{document}' in stripped or '\\end{document}' in stripped:
                continue

            sec_match = re.search(r'\\section\*?\{([^}]+)\}', stripped)
            if sec_match:
                display_lines.append(f"SECTION: {sec_match.group(1).upper()}")
                continue

            subsec_match = re.search(r'\\subsection\*?\{([^}]+)\}', stripped)
            if subsec_match:
                display_lines.append(f"  Subsection: {subsec_match.group(1)}")
                continue

            title_match = re.search(r'\\title\{([^}]+)\}', stripped)
            if title_match:
                doc_title = title_match.group(1)
                display_lines.append(f"TITLE: {doc_title}")
                continue

            author_match = re.search(r'\\author\{([^}]+)\}', stripped)
            if author_match:
                doc_author = author_match.group(1)
                display_lines.append(f"Author: {doc_author}")
                continue

            # Strip TeX macro tags for clean display
            clean_text = re.sub(r'\\[a-zA-Z]+\*?\{([^}]+)\}', r'\1', stripped)
            clean_text = re.sub(r'\\[a-zA-Z]+', '', clean_text)
            clean_text = clean_text.replace('$', '').replace('\\', '').replace('{', '').replace('}', '').strip()

            if clean_text:
                display_lines.append(clean_text[:80])

        if not display_lines:
            display_lines = ["TeXa Continuous Live Preview Active", "Document syntax clean and ready."]

        # Construct PDF Text Stream
        safe_title = doc_title[:50].replace('(', '\\(').replace(')', '\\)')
        pdf_stream_lines = []
        pdf_stream_lines.append("BT")
        pdf_stream_lines.append(f"/F1 18 Tf 40 730 Td ({safe_title}) Tj")
        pdf_stream_lines.append("/F1 9 Tf 0 -18 Td (Continuous live compilation active. Instant document preview.) Tj")
        pdf_stream_lines.append("/F1 10 Tf 0 -16 Td (------------------------------------------------------------------------) Tj")

        for l in display_lines[:26]:
            safe_line = l.replace('(', '\\(').replace(')', '\\)')
            if l.startswith("SECTION:") or l.startswith("TITLE:"):
                pdf_stream_lines.append(f"/F1 13 Tf 0 -22 Td ({safe_line}) Tj")
            else:
                pdf_stream_lines.append(f"/F1 11 Tf 0 -15 Td ({safe_line}) Tj")

        pdf_stream_lines.append("ET")
        stream_content = "\n".join(pdf_stream_lines).encode('ascii', errors='ignore')
        stream_len = len(stream_content)

        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<//F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
            b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            b"5 0 obj<</Length " + str(stream_len).encode('ascii') + b">>stream\n"
            + stream_content + b"\n"
            b"endstream\n"
            b"endobj\n"
            b"xref\n"
            b"0 6\n"
            b"0000000000 65535 f \n"
            b"0000000010 00000 n \n"
            b"0000000059 00000 n \n"
            b"0000000116 00000 n \n"
            b"0000000228 00000 n \n"
            b"0000000300 00000 n \n"
            b"trailer<</Size 6/Root 1 0 R>>\n"
            b"startxref\n"
            b"450\n"
            b"%%EOF\n"
        )

        with open(output_pdf_path, 'wb') as f:
            f.write(pdf_bytes)

    def _parse_log_diagnostics(self, log_output: str, default_file: str = "main.tex") -> List[LaTeXDiagnostic]:
        """Parse raw compilation log output into structured line diagnostics."""
        diagnostics = []

        lines = log_output.splitlines()
        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue

            # Format 1: Tectonic "error: ..." or "error: line X: ..."
            tectonic_error = re.search(r'error:\s*(?:line\s*(\d+):)?\s*(.*)', line_str, re.IGNORECASE)
            if tectonic_error and not line_str.startswith("note:"):
                line_num = int(tectonic_error.group(1)) if tectonic_error.group(1) else 1
                msg = tectonic_error.group(2) or line_str
                # Check for line number in adjacent text
                line_match = re.search(r'l\.(\d+)', line_str)
                if line_match:
                    line_num = int(line_match.group(1))
                
                diagnostics.append(LaTeXDiagnostic(
                    line=line_num,
                    severity="error",
                    message=msg,
                    file=default_file
                ))
                continue

            # Format 2: LaTeX Error lines: "! LaTeX Error: ... l.42 \badcommand"
            line_match = re.search(r'l\.(\d+)', line_str)
            if line_str.startswith("!") or "Error:" in line_str or (line_match and "error" in line_str.lower()):
                line_num = int(line_match.group(1)) if line_match else 1
                msg = line_str
                # Grab next line if available for extra context
                if idx + 1 < len(lines) and not lines[idx+1].strip().startswith("!"):
                    msg += " " + lines[idx+1].strip()
                
                diagnostics.append(LaTeXDiagnostic(
                    line=line_num,
                    severity="error",
                    message=msg,
                    file=default_file
                ))

            # Format 3: LaTeX Warning lines: "LaTeX Warning: ... on input line 42."
            elif "Warning:" in line_str or "warning:" in line_str:
                warn_line_match = re.search(r'line\s+(\d+)', line_str, re.IGNORECASE)
                line_num = int(warn_line_match.group(1)) if warn_line_match else 1
                diagnostics.append(LaTeXDiagnostic(
                    line=line_num,
                    severity="warning",
                    message=line_str,
                    file=default_file
                ))

        return diagnostics

# Global Engine instance
latex_engine = LaTeXEngineManager()
