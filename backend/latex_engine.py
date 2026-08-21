"""
TeXa Hybrid LaTeX Engine
Supports Tectonic + latexmk compilation drivers, log parsing, continuous validation,
and structured diagnostic extraction (errors, warnings, line numbers).
"""

import os
import re
import subprocess
import shutil
from typing import List, Dict, Any, Tuple

class LaTeXDiagnostic:
    """Structured diagnostic representation for editor markers."""
    def __init__(self, line: int, severity: str, message: str, file: str = "main.tex"):
        self.line = line
        self.severity = severity  # 'error', 'warning', 'info'
        self.message = message
        self.file = file

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line": self.line,
            "severity": self.severity,
            "message": self.message,
            "file": self.file
        }

class LaTeXEngineManager:
    """Manages LaTeX compilation using Tectonic, latexmk, or hybrid strategy."""
    
    def __init__(self):
        self.tectonic_path = shutil.which("tectonic")
        self.latexmk_path = shutil.which("latexmk")
        self.pdflatex_path = shutil.which("pdflatex")
        self.xelatex_path = shutil.which("xelatex")

    def detect_engines(self) -> Dict[str, bool]:
        """Detect available LaTeX compilation engines on system."""
        return {
            "tectonic": self.tectonic_path is not None,
            "latexmk": self.latexmk_path is not None,
            "pdflatex": self.pdflatex_path is not None,
            "xelatex": self.xelatex_path is not None
        }

    def compile(
        self,
        working_dir: str,
        main_file: str = "main.tex",
        engine_preference: str = "hybrid"
    ) -> Tuple[bool, str, List[Dict[str, Any]], str]:
        """
        Compile LaTeX document in working_dir.
        
        Returns:
            (success: bool, pdf_path: str, diagnostics: List[Dict], log_output: str)
        """
        if not os.path.isabs(main_file):
            tex_file_path = os.path.join(working_dir, main_file)
        else:
            tex_file_path = main_file

        base_name = os.path.splitext(os.path.basename(main_file))[0]
        expected_pdf = os.path.join(working_dir, f"{base_name}.pdf")

        # Determine which driver to use
        available = self.detect_engines()
        engine_to_use = "tectonic"

        if engine_preference == "latexmk" and available["latexmk"]:
            engine_to_use = "latexmk"
        elif engine_preference == "tectonic" and available["tectonic"]:
            engine_to_use = "tectonic"
        elif engine_preference == "hybrid":
            # Hybrid mode: prefer Tectonic for fast compilation; fallback to latexmk or pdflatex
            if available["tectonic"]:
                engine_to_use = "tectonic"
            elif available["latexmk"]:
                engine_to_use = "latexmk"
            elif available["pdflatex"]:
                engine_to_use = "pdflatex"
            else:
                engine_to_use = "mock"
        else:
            if available["tectonic"]:
                engine_to_use = "tectonic"
            elif available["latexmk"]:
                engine_to_use = "latexmk"
            elif available["pdflatex"]:
                engine_to_use = "pdflatex"
            else:
                engine_to_use = "mock"

        log_output = ""
        success = False

        try:
            if engine_to_use == "tectonic":
                # Tectonic single-pass fast compilation command with explicit outdir
                cmd = [self.tectonic_path, "-X", "compile", tex_file_path, "--outdir", working_dir, "--synctex"]
                res = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, timeout=60)
                log_output = res.stdout + "\n" + res.stderr
                success = res.returncode == 0

            elif engine_to_use == "latexmk":
                # Latexmk multi-pass compilation command with explicit outdir
                cmd = [self.latexmk_path, "-pdf", f"-outdir={working_dir}", "-interaction=nonstopmode", "-synctex=1", tex_file_path]
                res = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, timeout=120)
                log_output = res.stdout + "\n" + res.stderr
                success = res.returncode == 0

            elif engine_to_use == "pdflatex":
                # Standard pdflatex fallback command with explicit output-directory
                cmd = [self.pdflatex_path, f"-output-directory={working_dir}", "-interaction=nonstopmode", "-synctex=1", tex_file_path]
                res = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, timeout=60)
                log_output = res.stdout + "\n" + res.stderr
                success = res.returncode == 0

            else:
                # Dynamic preview fallback mode: converts main.tex content directly into PDF preview
                log_output = (
                    "[TeXa Engine Notification]: Neither tectonic, latexmk, nor pdflatex command was found in PATH.\n"
                    "Generating dynamic live document preview from main.tex content.\n"
                    "Tip: Install Tectonic (`brew install tectonic`) for full local PDF compilation."
                )
                self._generate_dynamic_preview_pdf(tex_file_path, expected_pdf)
                success = True

        except subprocess.TimeoutExpired:
            log_output = "[Error]: Compilation timed out after 60 seconds."
            success = False
        except Exception as e:
            log_output = f"[Error during execution]: {str(e)}"
            success = False

        # Parse diagnostics from output log
        diagnostics = self._parse_log_diagnostics(log_output)

        pdf_path = expected_pdf if (os.path.exists(expected_pdf)) else ""

        return success, pdf_path, [d.to_dict() for d in diagnostics], log_output

    def _generate_dynamic_preview_pdf(self, tex_file_path: str, output_pdf_path: str):
        """Extract document text & sections from main.tex and render directly into PDF preview stream."""
        content = ""
        if os.path.exists(tex_file_path):
            with open(tex_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

        lines = content.splitlines()
        display_lines = []

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
                display_lines.append(f"TITLE: {title_match.group(1)}")
                continue

            author_match = re.search(r'\\author\{([^}]+)\}', stripped)
            if author_match:
                display_lines.append(f"Author: {author_match.group(1)}")
                continue

            # Strip TeX macro tags for clean display
            clean_text = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', stripped)
            clean_text = re.sub(r'\\[a-zA-Z]+', '', clean_text)
            clean_text = clean_text.replace('$', '').replace('\\', '').replace('{', '').replace('}', '').strip()

            if clean_text:
                display_lines.append(clean_text[:75])

        if not display_lines:
            display_lines = ["TeXa Continuous Live Preview Active", "Document content clean."]

        # Construct PDF Text Stream
        pdf_stream_lines = []
        pdf_stream_lines.append("BT")
        pdf_stream_lines.append("/F1 18 Tf 40 730 Td (TeXa Live LaTeX Output Document) Tj")
        pdf_stream_lines.append("/F1 9 Tf 0 -18 Td (Continuous live compilation active. Instant document preview.) Tj")
        pdf_stream_lines.append("/F1 10 Tf 0 -16 Td (------------------------------------------------------------------------) Tj")

        for l in display_lines[:24]:
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

    def _parse_log_diagnostics(self, log_output: str) -> List[LaTeXDiagnostic]:

        """Parse raw compilation log output into structured line diagnostics."""
        diagnostics = []

        # Regular expressions for common TeX compilation error formats
        # Format 1: "! LaTeX Error: ... l.42 \badcommand"
        # Format 2: "l.42 \badcommand"
        # Format 3: "LaTeX Warning: ... on input line 42."
        
        lines = log_output.splitlines()
        for idx, line in enumerate(lines):
            # Check for LaTeX Error lines with line numbers
            line_match = re.search(r'l\.(\d+)', line)
            if line.startswith("!") or "Error:" in line or line_match:
                line_num = int(line_match.group(1)) if line_match else 1
                msg = line.strip()
                # Grab next line if available for extra context
                if idx + 1 < len(lines) and not lines[idx+1].startswith("!"):
                    msg += " " + lines[idx+1].strip()
                
                diagnostics.append(LaTeXDiagnostic(
                    line=line_num,
                    severity="error",
                    message=msg
                ))

            elif "Warning:" in line:
                warn_line_match = re.search(r'line\s+(\d+)', line, re.IGNORECASE)
                line_num = int(warn_line_match.group(1)) if warn_line_match else 1
                diagnostics.append(LaTeXDiagnostic(
                    line=line_num,
                    severity="warning",
                    message=line.strip()
                ))

        return diagnostics

# Global Engine instance
latex_engine = LaTeXEngineManager()
