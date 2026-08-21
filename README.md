<p align="center">
  <img src="frontend/src/assets/logo.png" alt="TeXa Logo" width="220" />
</p>

<p align="center">
  <strong>Minimalist, Privacy-First, Local AI-Powered LaTeX Editor & Live Compiler</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/Vite-8-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/PyTorch-MPS%20%7C%20CUDA%20%7C%20CPU-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch" />
  <img src="https://img.shields.io/badge/Monaco_Editor-VS_Code_Core-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white" alt="Monaco" />
</p>

---

## 📖 Overview

**TeXa** is a modern, distraction-free LaTeX editor powered by **local, on-device generative AI**. Built with high performance and privacy in mind, TeXa allows you to compose documents, generate complex mathematical templates, diagnose compiler errors, and preview live-rendered PDFs—all without sending a single line of your code or research data to external cloud APIs.

Whether you are writing academic papers, mathematical proofs, resumes, or lecture slides, TeXa combines the power of open-weight Large Language Models with the speed of hybrid LaTeX compilation.

---

## ✨ Key Features

- **🧠 Zero-Cloud Local AI Inference**

  - Runs Hugging Face models locally using **PyTorch** with full hardware acceleration:
    - ⚡ **Apple Silicon (MPS)** for M1/M2/M3/M4 Macs.
    - 🚀 **NVIDIA CUDA** for GeForce/RTX/Tesla GPUs.
    - ⚙️ **Optimized Multi-Threaded CPU** fallback.
  - Supports popular lightweight architectures like **Qwen 2.5 Coder (1.5B / 3B / 7B)**, **Google Gemma 3 (1B / 4B)**, **Llama 3.2**, or any custom CausalLM from Hugging Face Hub.
- **⚡ Hybrid LaTeX Compilation & Instant PDF Viewer**

  - Works with **Tectonic** (automatic on-the-fly package fetching), **latexmk**, or **pdflatex**.
  - Includes continuous validation that compiles your documents as you write.
  - Integrated full-featured PDF viewer with page navigation, zoom, and fit modes.
- **📝 AI Code & Template Generation**

  - Dedicated prompt-to-LaTeX generator with active document context awareness.
  - Instantly produces clean code for tables (`booktabs`), mathematical systems, TikZ flowcharts, and full document boilerplate.
  - Guardrailed to ensure clean, strictly compilation-ready LaTeX.
- **🛠️ Autonomous Compiler Diagnostic & Error Resolver**

  - Automatically parses compilation logs and identifies the exact file and line number causing the issue.
  - Preprocesses line-numbered snippets and delivers root-cause explanations with 1-click copyable fixes.
- **💻 VS Code-Grade Monaco Editor**

  - Full syntax highlighting for LaTeX and TeX macros.
  - Integrated error squiggles and diagnostic markers.
  - Multi-tab document navigation with unsaved change badges and clean indentation.
- **📁 Project Workspace & File Management**

  - Nested directory tree navigation with file and folder creation, deletion, and renaming.
  - Configurable custom project directories.
- **🎨 Minimalist Dark & Light Themes**

  - Fully responsive, sleek UI with customizable dark and light modes.

---

## 🛠️ Required Tools & Prerequisites

Before installing TeXa, ensure you have the following prerequisites installed on your system:

| Tool                    | Minimum Version | Description                                                                                                                                      |
| :---------------------- | :-------------- | :----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Python**        | `3.10+`       | Backend server, API, and PyTorch AI engine                                                                                                       |
| **Node.js & npm** | `18.0+`       | Frontend web interface and Vite asset pipeline                                                                                                   |
| **LaTeX Engine**  | Any             | **[Tectonic](https://tectonic-typesetting.github.io/)** *(Highly Recommended)*, **TeX Live**, **MacTeX**, or **MiKTeX** |
| **Git**           | `2.0+`        | Version control for cloning and updates                                                                                                          |

---

## 🚀 Installation & Setup Guide

Follow the instructions below for your operating system:

### 🍎 macOS Setup

1. **Install Prerequisites via Homebrew** (if not already installed):

   ```bash
   brew install python node tectonic git
   ```
2. **Clone the Repository**:

   ```bash
   git clone https://github.com/K-692/TeXa.git
   cd TeXa
   ```
3. **Set Up Python Virtual Environment**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. **Install Python Dependencies**:

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
5. **Install Frontend Dependencies & Build Assets**:

   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```
6. **Launch TeXa**:

   ```bash
   python run.py
   ```

   *TeXa will start the backend server and automatically open `http://localhost:8000` in your default browser.*

---

### 🪟 Windows Setup

1. **Install Prerequisites** via [Winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) or manual installers:

   ```powershell
   winget install Python.Python.3.11
   winget install OpenJS.NodeJS.LTS
   winget install Git.Git
   winget install TectonicTypesetting.Tectonic
   ```

   *(Alternative LaTeX: [MiKTeX](https://miktex.org/download))*
2. **Clone the Repository**:

   ```powershell
   git clone https://github.com/K-692/TeXa.git
   cd TeXa
   ```
3. **Set Up Python Virtual Environment**:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
4. **Install Python Dependencies**:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
5. **Install Frontend Dependencies & Build Assets**:

   ```powershell
   cd frontend
   npm install
   npm run build
   cd ..
   ```
6. **Launch TeXa**:

   ```powershell
   python run.py
   ```

---

### 🐧 Linux Setup (Ubuntu / Debian / Fedora / Arch)

1. **Install Prerequisites**:

   - **Ubuntu / Debian**:
     ```bash
     sudo apt update
     sudo apt install -y python3 python3-venv python3-pip nodejs npm git
     # Install Tectonic (recommended fast standalone compiler)
     sudo apt install -y tectonic || curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh
     ```
   - **Fedora**:
     ```bash
     sudo dnf install -y python3 python3-pip nodejs git tectonic
     ```
   - **Arch Linux**:
     ```bash
     sudo pacman -S python python-pip nodejs npm git tectonic
     ```
2. **Clone the Repository**:

   ```bash
   git clone https://github.com/K-692/TeXa.git
   cd TeXa
   ```
3. **Set Up Python Virtual Environment**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. **Install Python Dependencies**:

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
5. **Install Frontend Dependencies & Build Assets**:

   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```
6. **Launch TeXa**:

   ```bash
   python run.py
   ```

---

## ⚙️ Configuration & Environment Settings

TeXa comes with an environment configuration file: `.env`.

```bash
# Hugging Face Access Token
# Required only for gated models (e.g. google/gemma-3-1b-it, meta-llama/Llama-3.2-3B-Instruct)
# Create a free read token at: https://huggingface.co/settings/tokens
HF_TOKEN=

# Default LaTeX Workspace Directory
# Can be a relative path (./projects) or an absolute directory (~/TeXa_Projects)
WORKING_DIRECTORY=./projects
```

> **Tip**: You can also configure your Hugging Face Token, selected model, and project directory directly within the TeXa user interface via the **Settings (⚙️)** modal.

---

## 🤖 Recommended AI Models

TeXa supports any Hugging Face CausalLM model. For best performance on personal laptops and desktops:

| Model ID                             | VRAM / RAM | Description                                                                        |
| :----------------------------------- | :--------- | :--------------------------------------------------------------------------------- |
| `Qwen/Qwen2.5-Coder-1.5B-Instruct` | ~3 GB      | Ultra-fast, lightweight model ideal for quick syntax and equations.                |
| `Qwen/Qwen2.5-Coder-3B-Instruct`   | ~5 GB      | **Recommended**. Outstanding LaTeX syntax and table generation.              |
| `google/gemma-3-1b-it`             | ~2.5 GB    | Google's high-efficiency lightweight multimodal/text model.*(Requires HF Token)* |
| `meta-llama/Llama-3.2-3B-Instruct` | ~5 GB      | Versatile general assistance and document debugging.*(Requires HF Token)*        |
| `Custom Model ID`                  | Variable   | Enter any Hugging Face model identifier in the UI model picker.                    |

*Downloaded weights are stored locally in the `models/` directory for offline reuse.*

---

## 📂 Project Architecture

```
TeXa/
├── backend/                  # FastAPI Application & AI Engines
│   ├── main.py               # REST & WebSocket API Endpoints
│   ├── ai_engine.py          # PyTorch / MPS / CUDA Model Inference & Prompts
│   ├── latex_engine.py       # Tectonic / Latexmk Compiler & Log Diagnostics
│   ├── file_manager.py       # Workspace File Tree & File I/O
│   └── config.py             # Global State & .env Manager
├── frontend/                 # React + Vite Web Application
│   ├── src/
│   │   ├── components/       # Monaco Editor, PDF Viewer, File Tree, AI Panel
│   │   ├── assets/           # Logo & Icons
│   │   ├── styles/           # CSS & Design System
│   │   └── App.jsx           # Main Application Layout
│   ├── package.json          # Node Dependencies
│   └── vite.config.js        # Vite Configuration
├── models/                   # Local Hugging Face Models Cache (ignored in git)
├── projects/                 # Default LaTeX Workspace
│   └── main.tex              # Starter LaTeX Document
├── run.py                    # Single-Command Cross-Platform Launcher
├── requirements.txt          # Python Dependencies
├── .env                      # Environment Variables Template
└── README.md                 # Project Documentation
```

---

## ⌨️ Shortcuts & Tips

- <kbd>Cmd</kbd> / <kbd>Ctrl</kbd> + <kbd>S</kbd> : Save active document and trigger compilation.
- <kbd>Cmd</kbd> / <kbd>Ctrl</kbd> + <kbd>B</kbd> : Manual compile document to PDF.
- **Continuous Validation**: When enabled in Settings, TeXa compiles your document seamlessly in the background as you type.

---

## 🤝 Contributing

Contributions, feature suggestions, and pull requests are welcome!

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## 📄 License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
