import React, { useState, useEffect, useRef } from 'react';
import Editor from '@monaco-editor/react';
import { 
  Code, Eye, Bot, Terminal, Copy, AlertCircle, FileText, Check, X, 
  Folder, FolderOpen, FolderPlus, ChevronRight, PanelLeftClose, PanelLeftOpen, 
  Plus, Edit2, Trash2, ChevronDown, ChevronUp, ZoomIn, ZoomOut,
  Bug, Sparkles, GripVertical, RefreshCw, CheckCircle2, Wand2
} from 'lucide-react';

export default function EditorPage({
  config,
  editorContent,
  setEditorContent,
  onCompile,
  isCompiling,
  pdfUrl,
  pdfTimestamp: propPdfTimestamp,
  diagnostics,
  logOutput,
  activeFile,
  isAiBoxOpen,
  toggleAiBox,
  onSelectFile,
  openTabs,
  onCloseTab
}) {
  const projectDirName = config?.working_directory
    ? config.working_directory.replace(/\/+$/, '').split('/').pop()
    : 'PROJECT';

  // Panel Resizing State
  const [splitRatioX, setSplitRatioX] = useState(48);
  const [splitRatioY, setSplitRatioY] = useState(88);

  // VS Code Style Collapsible & Resizable File Explorer Sidebar State
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(210);
  const [fileList, setFileList] = useState([]);

  // Zoom Controls State
  const [editorFontSize, setEditorFontSize] = useState(12);
  const [pdfScale, setPdfScale] = useState(100);

  // Sidebar New File, Folder & Rename File Modals
  const [showNewFileModal, setShowNewFileModal] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const [showNewFolderModal, setShowNewFolderModal] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [renameNewName, setRenameNewName] = useState('');
  const [targetRenameFile, setTargetRenameFile] = useState('');
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [collapsedFolders, setCollapsedFolders] = useState({});
  const [showDuplicateModal, setShowDuplicateModal] = useState(false);
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [duplicateTarget, setDuplicateTarget] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [targetDeleteFile, setTargetDeleteFile] = useState(null);

  // Logs Collapsed State
  const [isLogsCollapsed, setIsLogsCollapsed] = useState(false);
  const [activeLogTab, setActiveLogTab] = useState('diagnostics');

  // AI Assistant 2-Tab State: 'code' | 'debug'
  const [aiTab, setAiTab] = useState('code');

  // Tab 1: AI Code Generation State
  const [codePrompt, setCodePrompt] = useState('');
  const [isCodeLoading, setIsCodeLoading] = useState(false);
  const [codeResult, setCodeResult] = useState(null);
  const [isDraggingSnippet, setIsDraggingSnippet] = useState(false);

  // Tab 3: AI Debug Error Analyzer State
  const [isDebugLoading, setIsDebugLoading] = useState(false);
  const [debugReport, setDebugReport] = useState(null);

  const [pdfTimestamp, setPdfTimestamp] = useState(Date.now());
  const [copied, setCopied] = useState(false);

  // Floating Draggable & Resizable AI Box State
  const [aiPos, setAiPos] = useState({ x: 340, y: 50 });
  const [aiSize, setAiSize] = useState({ width: 480, height: 460 });
  const [isDraggingAi, setIsDraggingAi] = useState(false);
  const [isResizingAi, setIsResizingAi] = useState(false);

  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const debounceTimerRef = useRef(null);
  const pageContainerRef = useRef(null);
  const dragStartRef = useRef({ x: 0, y: 0, posX: 340, posY: 50 });
  const resizeStartRef = useRef({ x: 0, y: 0, width: 480, height: 460 });
  const codeAbortControllerRef = useRef(null);
  const debugAbortControllerRef = useRef(null);
  const lastDropTimeRef = useRef(0);

  // Load workspace files
  const refreshFiles = () => {
    fetch('/api/files')
      .then(res => res.json())
      .then(data => {
        const filesArray = Array.isArray(data) ? data : (data && data.files ? data.files : []);
        setFileList(filesArray);
      })
      .catch((err) => console.error('Error loading files:', err));
  };

  useEffect(() => {
    refreshFiles();
  }, [activeFile, config.working_directory]);

  // Auto-expand parent folders for active file
  useEffect(() => {
    if (activeFile && activeFile.includes('/')) {
      const parts = activeFile.split('/');
      let current = '';
      setCollapsedFolders(prev => {
        const next = { ...prev };
        for (let i = 0; i < parts.length - 1; i++) {
          current = current ? `${current}/${parts[i]}` : parts[i];
          delete next[current];
        }
        return next;
      });
    }
  }, [activeFile]);

  // Auto-compile document on first editor page load once content is ready
  const hasAutoCompiledRef = useRef(false);
  useEffect(() => {
    if (!hasAutoCompiledRef.current && onCompile && editorContent && editorContent.trim().length > 0) {
      hasAutoCompiledRef.current = true;
      onCompile(editorContent);
    }
  }, [editorContent]);

  // Update PDF viewer timestamp when PDF recompiles
  useEffect(() => {
    if (propPdfTimestamp) {
      setPdfTimestamp(propPdfTimestamp);
    } else if (pdfUrl) {
      setPdfTimestamp(Date.now());
    }
  }, [propPdfTimestamp, pdfUrl]);


  // Handle Monaco Editor Mount & Attach Live Cursor Tracking Drag-and-Drop Listeners
  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Attach native dragover and drop listeners on Monaco's DOM element for live cursor tracking
    const domNode = editor.getDomNode();
    if (domNode) {
      domNode.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        const target = editor.getTargetAtClientPoint(e.clientX, e.clientY);
        if (target && target.position) {
          editor.setPosition(target.position);
          editor.revealPosition(target.position, 0);
        }
      });

      domNode.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const now = Date.now();
        if (now - lastDropTimeRef.current < 250) {
          // Prevent duplicate drop insertion
          return;
        }
        lastDropTimeRef.current = now;

        const codeText = e.dataTransfer.getData('text/plain');
        if (codeText) {
          const target = editor.getTargetAtClientPoint(e.clientX, e.clientY);
          const pos = target?.position || editor.getPosition() || { lineNumber: 1, column: 1 };
          const textToInsert = '\n' + codeText.trim() + '\n';
          
          editor.executeEdits('ai-code-drop', [{
            range: new monaco.Range(pos.lineNumber, pos.column, pos.lineNumber, pos.column),
            text: textToInsert,
            forceMoveMarkers: true
          }]);
          
          const addedLines = textToInsert.split('\n').length - 1;
          editor.setPosition({
            lineNumber: pos.lineNumber + addedLines,
            column: 1
          });
          editor.focus();

          const updated = editor.getValue();
          setEditorContent(updated);
          if (config?.auto_validate ?? true) {
            if (debounceTimerRef.current) {
              clearTimeout(debounceTimerRef.current);
            }
            debounceTimerRef.current = setTimeout(() => {
              onCompile(updated);
            }, 300);
          }
        }
      });
    }
  };

  const autoSaveTimerRef = useRef(null);

  // Continuous Validation & Auto-Save Handler (Immediately on typing stop)
  const handleEditorChange = (value) => {
    const updated = value || '';
    setEditorContent(updated);

    // Instant Auto-Save file content to disk as soon as user stops typing (150ms debounce)
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }
    autoSaveTimerRef.current = setTimeout(() => {
      fetch('/api/file/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rel_path: activeFile, content: updated })
      }).catch(() => {});
    }, 150);

    // Auto-Compile document if auto_validate toggle is ON (300ms debounce)
    if (config?.auto_validate ?? true) {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        onCompile(updated);
      }, 300);
    }
  };



  // Jump editor cursor to line number
  const jumpToLine = (lineNum) => {
    if (editorRef.current) {
      editorRef.current.revealLineInCenter(lineNum);
      editorRef.current.setPosition({ lineNumber: lineNum, column: 1 });
      editorRef.current.focus();
    }
  };

  // Sidebar Resizing Drag Handler
  const handleMouseDownSidebarResizer = (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = sidebarWidth;

    const handleMouseMove = (moveEvent) => {
      const newWidth = Math.max(140, Math.min(450, startWidth + (moveEvent.clientX - startX)));
      setSidebarWidth(newWidth);
    };

    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  // Toggle folder collapse state in sidebar tree
  const toggleFolderCollapse = (folderPath, e) => {
    if (e) e.stopPropagation();
    setCollapsedFolders(prev => {
      const next = { ...prev };
      if (next[folderPath]) {
        delete next[folderPath];
      } else {
        next[folderPath] = true;
      }
      return next;
    });
  };

  // Check if item is visible in tree based on parent folder collapsed states
  const isItemVisible = (item) => {
    if (!item.parent_path) return true;
    const parts = item.parent_path.split('/');
    let current = '';
    for (const part of parts) {
      current = current ? `${current}/${part}` : part;
      if (collapsedFolders[current]) return false;
    }
    return true;
  };

  // Handle Create File — checks fileList for duplicates first, then calls API
  const handleCreateFile = () => {
    if (!newFileName.trim()) return;
    let targetPath = newFileName.trim();

    // Prepend selected subfolder if not already in path
    if (selectedFolder && !targetPath.startsWith(selectedFolder + '/')) {
      targetPath = `${selectedFolder}/${targetPath}`;
    }

    // Check duplicate against already-loaded file list before calling API
    const alreadyExists = fileList.some(f => f.path === targetPath);
    if (alreadyExists) {
      // Close the create modal first so only the replace popup is visible
      setShowNewFileModal(false);
      setNewFileName('');
      setDuplicateTarget({ path: targetPath, type: 'file' });
      setShowReplaceModal(true);
      return;
    }

    // No duplicate — create file directly
    fetch('/api/file/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rel_path: targetPath, content: '% New TeXa Document\n', overwrite: false })
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          refreshFiles();
          if (selectedFolder) {
            setCollapsedFolders(prev => {
              const next = { ...prev };
              delete next[selectedFolder];
              return next;
            });
          }
          onSelectFile(targetPath);
          setShowNewFileModal(false);
          setNewFileName('');
        } else if (data.status === 'exists') {
          // Race condition fallback — file appeared between list load and create
          setShowNewFileModal(false);
          setNewFileName('');
          setDuplicateTarget({ path: targetPath, type: 'file' });
          setShowReplaceModal(true);
        }
      })
      .catch(err => alert(`Error creating file: ${err}`));
  };

  // Handle Create Folder — checks fileList for duplicates first, then calls API
  const handleCreateFolder = () => {
    if (!newFolderName.trim()) return;
    let targetPath = newFolderName.trim();

    // Prepend selected subfolder if not already in path
    if (selectedFolder && !targetPath.startsWith(selectedFolder + '/')) {
      targetPath = `${selectedFolder}/${targetPath}`;
    }

    // Check duplicate against already-loaded file list before calling API
    const alreadyExists = fileList.some(f => f.path === targetPath);
    if (alreadyExists) {
      // Close the create modal first so only the replace popup is visible
      setShowNewFolderModal(false);
      setNewFolderName('');
      setDuplicateTarget({ path: targetPath, type: 'folder' });
      setShowReplaceModal(true);
      return;
    }

    // No duplicate — create folder directly
    fetch('/api/folder/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rel_path: targetPath, overwrite: false })
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          refreshFiles();
          if (selectedFolder) {
            setCollapsedFolders(prev => {
              const next = { ...prev };
              delete next[selectedFolder];
              return next;
            });
          }
          setSelectedFolder(targetPath);
          setShowNewFolderModal(false);
          setNewFolderName('');
        } else if (data.status === 'exists') {
          // Race condition fallback
          setShowNewFolderModal(false);
          setNewFolderName('');
          setDuplicateTarget({ path: targetPath, type: 'folder' });
          setShowReplaceModal(true);
        }
      })
      .catch(err => alert(`Error creating folder: ${err}`));
  };

  const handleConfirmReplace = () => {
    if (!duplicateTarget) return;
    const { path, type } = duplicateTarget;
    const endpoint = type === 'file' ? '/api/file/create' : '/api/folder/create';
    const body = type === 'file'
      ? { rel_path: path, content: '% New TeXa Document\n', overwrite: true }
      : { rel_path: path, overwrite: true };

    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          refreshFiles();
          if (type === 'file') onSelectFile(path);
          else setSelectedFolder(path);
          setShowReplaceModal(false);
          setShowNewFileModal(false);
          setShowNewFolderModal(false);
          setNewFileName('');
          setNewFolderName('');
          setDuplicateTarget(null);
        }
      })
      .catch(err => alert(`Error replacing ${type}: ${err}`));
  };

  const handleCancelReplace = () => {
    setShowReplaceModal(false);
    setDuplicateTarget(null);
  };

  // Handle Delete File or Folder — permanently removes item from workspace after confirmation
  const handleDeleteFile = () => {
    if (!targetDeleteFile) return;
    const { path, type } = targetDeleteFile;
    fetch('/api/file/delete', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rel_path: path })
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          refreshFiles();
          // If deleted file was the active editor file, fall back to main.tex
          if (type === 'file' && activeFile === path) onSelectFile('main.tex');
          // If deleted folder was selected, clear selection
          if (type === 'folder' && selectedFolder === path) setSelectedFolder(null);
        }
        setShowDeleteModal(false);
        setTargetDeleteFile(null);
      })
      .catch(err => alert(`Error deleting ${type}: ${err}`));
  };

  // Handle Rename File
  const handleRenameFile = () => {
    if (!renameNewName.trim() || !targetRenameFile) return;
    fetch('/api/file/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_rel_path: targetRenameFile, new_rel_path: renameNewName.trim() })
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          refreshFiles();
          onSelectFile(renameNewName.trim());
          setShowRenameModal(false);
          setRenameNewName('');
          setTargetRenameFile('');
        }
      })
      .catch(err => alert(`Error renaming file: ${err}`));
  };

  const handleCopyText = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleInsertText = (text) => {
    if (editorRef.current) {
      const selection = editorRef.current.getSelection();
      editorRef.current.executeEdits('ai-box', [{
        range: selection,
        text: '\n' + text + '\n',
        forceMoveMarkers: true
      }]);
      editorRef.current.focus();
      const updated = editorRef.current.getValue();
      setEditorContent(updated);
      if (config?.auto_validate ?? true) {
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }
        debounceTimerRef.current = setTimeout(() => {
          onCompile(updated);
        }, 300);
      }
    } else {
      setEditorContent(prev => prev + '\n' + text);
    }
  };

  // Cancel any in-flight AI model requests immediately (both network fetch and backend model inference)
  const handleCancelAiGeneration = () => {
    if (codeAbortControllerRef.current) {
      try { codeAbortControllerRef.current.abort(); } catch (_) {}
      codeAbortControllerRef.current = null;
    }
    if (debugAbortControllerRef.current) {
      try { debugAbortControllerRef.current.abort(); } catch (_) {}
      debugAbortControllerRef.current = null;
    }
    setIsCodeLoading(false);
    setIsDebugLoading(false);
    fetch('/api/ai/cancel', { method: 'POST' }).catch(() => {});
  };

  // Automatically terminate model generation whenever the AI box is closed
  useEffect(() => {
    if (!isAiBoxOpen) {
      handleCancelAiGeneration();
    }
  }, [isAiBoxOpen]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      handleCancelAiGeneration();
    };
  }, []);

  // Tab 1: Handle Code Template Generation
  const handleGenerateCodeTemplate = (customPrompt = '') => {
    const promptToSend = customPrompt || codePrompt;
    if (!promptToSend.trim()) return;

    if (codeAbortControllerRef.current) {
      try { codeAbortControllerRef.current.abort(); } catch (_) {}
    }
    codeAbortControllerRef.current = new AbortController();

    setIsCodeLoading(true);
    setCodeResult(null);

    fetch('/api/ai/code-template', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: codeAbortControllerRef.current.signal,
      body: JSON.stringify({
        prompt: promptToSend,
        model_id: config.selected_model
      })
    })
      .then(res => res.json())
      .then(data => {
        setIsCodeLoading(false);
        setCodeResult(data);
      })
      .catch(err => {
        if (err.name === 'AbortError') {
          setIsCodeLoading(false);
          return;
        }
        setIsCodeLoading(false);
        setCodeResult({
          status: 'error',
          is_template: false,
          response: `Error: ${err}`,
          code: ''
        });
      });
  };

  // Tab 1: Drag Start for Code Snippet Block
  const handleCodeSnippetDragStart = (e, snippetCode) => {
    e.dataTransfer.setData('text/plain', snippetCode);
    e.dataTransfer.effectAllowed = 'copy';
    setIsDraggingSnippet(true);
  };

  const handleCodeSnippetDragEnd = () => {
    setIsDraggingSnippet(false);
  };

  const lastAnalyzedSignatureRef = useRef('');

  // Tab 2: AI Debug Analysis (Triggered ONLY when user explicitly clicks Re-analyze)
  const runDebugAnalysis = () => {
    // Strictly filter error diagnostics (ignore warnings)
    const errorDiagnostics = diagnostics ? diagnostics.filter(d => d.severity === 'error') : [];
    const hasErrors = errorDiagnostics.length > 0;

    // Immediately clear previous response from the box so "generating" is shown cleanly
    setDebugReport(null);

    if (!hasErrors) {
      setIsDebugLoading(false);
      setDebugReport({
        status: 'clean',
        summary: 'All compilation checks passed. Document syntax is clean and error-free.',
        issues: [],
        advice: 'No action needed. You can continue writing your document.'
      });
      return;
    }

    if (debugAbortControllerRef.current) {
      try { debugAbortControllerRef.current.abort(); } catch (_) {}
    }
    debugAbortControllerRef.current = new AbortController();

    setIsDebugLoading(true);

    fetch('/api/ai/debug', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: debugAbortControllerRef.current.signal,
      body: JSON.stringify({
        diagnostics: errorDiagnostics,
        log_output: logOutput || '',
        active_file: activeFile || 'main.tex',
        active_content: editorContent || ''
      })
    })
      .then(res => res.json())
      .then(data => {
        setIsDebugLoading(false);
        setDebugReport(data);
      })
      .catch(err => {
        if (err.name === 'AbortError') {
          setIsDebugLoading(false);
          return;
        }
        setIsDebugLoading(false);
        setDebugReport({
          status: 'error',
          summary: `Error analyzing diagnostics: ${err}`,
          issues: []
        });
      });
  };

  // ---------------- PANEL RESIZING LOGIC ----------------

  const handleMouseDownSplitterX = (e) => {
    e.preventDefault();
    const handleMouseMoveX = (moveEvent) => {
      if (pageContainerRef.current) {
        const rect = pageContainerRef.current.getBoundingClientRect();
        const newX = ((moveEvent.clientX - rect.left) / rect.width) * 100;
        if (newX > 15 && newX < 85) {
          setSplitRatioX(newX);
        }
      }
    };
    const handleMouseUpX = () => {
      window.removeEventListener('mousemove', handleMouseMoveX);
      window.removeEventListener('mouseup', handleMouseUpX);
    };
    window.addEventListener('mousemove', handleMouseMoveX);
    window.addEventListener('mouseup', handleMouseUpX);
  };

  const handleMouseDownSplitterY = (e) => {
    e.preventDefault();
    const handleMouseMoveY = (moveEvent) => {
      if (pageContainerRef.current) {
        const rect = pageContainerRef.current.getBoundingClientRect();
        const newY = ((moveEvent.clientY - rect.top) / rect.height) * 100;
        if (newY > 15 && newY < 90) {
          setSplitRatioY(newY);
        }
      }
    };
    const handleMouseUpY = () => {
      window.removeEventListener('mousemove', handleMouseMoveY);
      window.removeEventListener('mouseup', handleMouseUpY);
    };
    window.addEventListener('mousemove', handleMouseMoveY);
    window.addEventListener('mouseup', handleMouseUpY);
  };


  // ---------------- HOVERABLE FLOATING AI BOX DRAG & RESIZE ----------------

  const handleAiHeaderMouseDown = (e) => {
    e.preventDefault();
    setIsDraggingAi(true);
    document.body.style.userSelect = 'none';
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      posX: aiPos.x,
      posY: aiPos.y
    };

    const handleMouseMove = (moveEvent) => {
      const dx = moveEvent.clientX - dragStartRef.current.x;
      const dy = moveEvent.clientY - dragStartRef.current.y;
      setAiPos({
        x: Math.max(10, Math.min(window.innerWidth - 100, dragStartRef.current.posX + dx)),
        y: Math.max(10, Math.min(window.innerHeight - 80, dragStartRef.current.posY + dy))
      });
    };

    const handleMouseUp = () => {
      setIsDraggingAi(false);
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('blur', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    window.addEventListener('blur', handleMouseUp);
  };

  const handleAiResizeMouseDown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizingAi(true);
    document.body.style.userSelect = 'none';
    resizeStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      width: aiSize.width,
      height: aiSize.height
    };

    const handleMouseMove = (moveEvent) => {
      const dx = moveEvent.clientX - resizeStartRef.current.x;
      const dy = moveEvent.clientY - resizeStartRef.current.y;
      setAiSize({
        width: Math.max(320, Math.min(window.innerWidth - 40, resizeStartRef.current.width + dx)),
        height: Math.max(220, Math.min(window.innerHeight - 60, resizeStartRef.current.height + dy))
      });
    };

    const handleMouseUp = () => {
      setIsResizingAi(false);
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('blur', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    window.addEventListener('blur', handleMouseUp);
  };

  return (
    <div className="editor-page-container" ref={pageContainerRef}>
      {/* MAIN CONTENT WORKSPACE AREA WITH VS CODE SIDEBAR */}
      <div className="workspace-flex-wrapper">
        {/* VS CODE STYLE COLLAPSIBLE & RESIZABLE FILE EXPLORER SIDEBAR */}
        <div
          className={`vscode-sidebar ${isSidebarOpen ? 'expanded' : 'collapsed'}`}
          style={{ width: isSidebarOpen ? `${sidebarWidth}px` : '36px' }}
        >
          {isSidebarOpen ? (
            <>
              <div className="sidebar-header">
                <span className="sidebar-title" title={config?.working_directory || ''}>
                  <Folder size={13} /> {projectDirName ? projectDirName.toUpperCase() : 'EXPLORER'}
                </span>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button
                    className="ai-icon-btn"
                    onClick={() => setShowNewFolderModal(true)}
                    title="Create New Folder"
                  >
                    <FolderPlus size={14} />
                  </button>
                  <button
                    className="ai-icon-btn"
                    onClick={() => {
                      if (selectedFolder) {
                        setNewFileName(`${selectedFolder}/`);
                      } else {
                        setNewFileName('');
                      }
                      setShowNewFileModal(true);
                    }}
                    title={selectedFolder ? `Create New File inside '${selectedFolder}'` : "Create New File"}
                  >
                    <Plus size={14} />
                  </button>
                  <button
                    className="ai-icon-btn"
                    onClick={() => setIsSidebarOpen(false)}
                    title="Collapse Sidebar"
                  >
                    <PanelLeftClose size={14} />
                  </button>
                </div>
              </div>

              <div
                className="sidebar-file-tree"
                onClick={(e) => {
                  // Deselect folder when clicking blank space in the sidebar tree
                  if (e.target === e.currentTarget) setSelectedFolder(null);
                }}
              >
                <div className="sidebar-folder-label" title={config?.working_directory || ''}>
                  <ChevronRight size={12} style={{ transform: 'rotate(90deg)' }} /> {projectDirName ? projectDirName.toUpperCase() : 'PROJECT FILES'}
                </div>
                {fileList.filter(isItemVisible).map((item) => {
                  const depth = item.depth || 0;
                  const paddingLeftPx = depth * 14 + 10;

                  if (item.is_dir) {
                    const isSelected = selectedFolder === item.path;
                    const isCollapsed = Boolean(collapsedFolders[item.path]);
                    const hasChildren = fileList.some(f => f.parent_path === item.path || (f.parent_path && f.parent_path.startsWith(item.path + '/')));

                    return (
                      <React.Fragment key={item.path}>
                        <div
                          className={`file-tree-item folder-item ${isSelected ? 'selected-folder' : ''}`}
                          style={{ paddingLeft: `${paddingLeftPx}px` }}
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleFolderCollapse(item.path);
                            setSelectedFolder(item.path);
                          }}
                          title={`Folder: ${item.path}`}
                        >
                          <span
                            className="folder-chevron-wrapper"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleFolderCollapse(item.path);
                            }}
                            style={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}
                          >
                            {isCollapsed ? (
                              <ChevronRight size={12} className="chevron-icon" />
                            ) : (
                              <ChevronDown size={12} className="chevron-icon" />
                            )}
                          </span>
                          {isCollapsed ? (
                            <Folder size={13} className="folder-icon" style={{ color: 'var(--accent-warning)' }} />
                          ) : (
                            <FolderOpen size={13} className="folder-icon" style={{ color: 'var(--accent-warning)' }} />
                          )}
                          <span className="file-name" style={{ fontWeight: 600 }}>{item.name}/</span>
                          <button
                            className="sidebar-rename-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              setTargetRenameFile(item.path);
                              setRenameNewName(item.name);
                              setShowRenameModal(true);
                            }}
                            title="Rename Folder"
                          >
                            <Edit2 size={11} />
                          </button>
                          <button
                            className="sidebar-delete-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              setTargetDeleteFile({ path: item.path, type: 'folder' });
                              setShowDeleteModal(true);
                            }}
                            title="Delete Folder"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                        {!isCollapsed && !hasChildren && (
                          <div
                            key={`${item.path}-empty`}
                            className="file-tree-empty-hint"
                            style={{
                              paddingLeft: `${paddingLeftPx + 24}px`,
                              fontSize: '0.70rem',
                              color: 'var(--text-subtle)',
                              fontStyle: 'italic',
                              paddingTop: '2px',
                              paddingBottom: '2px',
                              userSelect: 'none'
                            }}
                          >
                            (empty folder)
                          </div>
                        )}
                      </React.Fragment>
                    );
                  }

                  const isActive = activeFile === item.path;

                  return (
                    <div
                      key={item.path}
                      className={`file-tree-item ${isActive ? 'active' : ''}`}
                      style={{ paddingLeft: `${paddingLeftPx + 14}px` }}
                      onClick={(e) => { e.stopPropagation(); onSelectFile && onSelectFile(item.path); }}
                      title={item.path}
                    >
                      <FileText size={13} className="file-icon" />
                      <span className="file-name">{item.name}</span>
                      <button
                        className="sidebar-rename-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setTargetRenameFile(item.path);
                          setRenameNewName(item.name);
                          setShowRenameModal(true);
                        }}
                        title="Rename File"
                      >
                        <Edit2 size={11} />
                      </button>
                      <button
                        className="sidebar-delete-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setTargetDeleteFile({ path: item.path, type: 'file' });
                          setShowDeleteModal(true);
                        }}
                        title="Delete File"
                      >
                        <Trash2 size={11} />
                      </button>
                    </div>
                  );
                })}
              </div>

              {/* Sidebar Drag Resizer Handle */}
              <div
                className="sidebar-resizer"
                onMouseDown={handleMouseDownSidebarResizer}
                title="Drag to resize sidebar width"
              />
            </>
          ) : (
            /* COLLAPSED STRIP WITH UN-COLLAPSE BUTTON */
            <div className="collapsed-sidebar-strip">
              <button
                className="ai-icon-btn"
                onClick={() => setIsSidebarOpen(true)}
                title="Expand File Explorer Sidebar"
                style={{ padding: '8px' }}
              >
                <PanelLeftOpen size={16} />
              </button>
            </div>
          )}
        </div>

        {/* TOP & BOTTOM RESIZABLE EDITOR & PREVIEW PANELS */}
        <div className="editor-main-area">
          {/* TOP SECTION: Code Editor (Left) & PDF Preview (Right) */}
          <div
            className="top-split-container"
            style={{ height: isLogsCollapsed ? 'calc(100% - 34px)' : `${splitRatioY}%` }}
          >
            {/* LaTeX Code Editor with Multi-Tab Bar & Zoom Controls (Left) */}
            <div className="frame-panel" style={{ width: `${splitRatioX}%` }}>
              {/* VS Code Style Multi-Tab Header Bar with Zoom */}
              <div className="editor-tabs-bar">
                <div style={{ display: 'flex', flex: 1, overflowX: 'auto' }}>
                  {openTabs && openTabs.length > 0 ? (
                    openTabs.map((tabPath) => {
                      const isActive = tabPath === activeFile;
                      const fileName = tabPath.split('/').pop();
                      return (
                        <div
                          key={tabPath}
                          className={`editor-tab ${isActive ? 'active' : ''}`}
                          onClick={() => onSelectFile && onSelectFile(tabPath)}
                        >
                          <FileText size={12} className="tab-icon" />
                          <span>{fileName}</span>
                          {openTabs.length > 1 && (
                            <span
                              className="close-tab-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                onCloseTab && onCloseTab(tabPath);
                              }}
                              title="Close Tab"
                            >
                              <X size={11} />
                            </span>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <div className="editor-tab active">
                      <FileText size={12} className="tab-icon" />
                      <span>{activeFile}</span>
                    </div>
                  )}
                </div>

                {/* Editor Font Zoom Controls */}
                <div className="zoom-controls-group">
                  <button
                    className="zoom-btn"
                    onClick={() => setEditorFontSize(prev => Math.max(10, prev - 1))}
                    title="Editor Zoom Out"
                  >
                    <ZoomOut size={12} />
                  </button>
                  <span className="zoom-label">{editorFontSize}px</span>
                  <button
                    className="zoom-btn"
                    onClick={() => setEditorFontSize(prev => Math.min(24, prev + 1))}
                    title="Editor Zoom In"
                  >
                    <ZoomIn size={12} />
                  </button>
                </div>
              </div>

              <div className="frame-content editor-drop-zone">
                <Editor
                  height="100%"
                  defaultLanguage="latex"
                  theme={config.theme === 'dark' ? 'vs-dark' : 'light'}
                  value={editorContent}
                  onChange={handleEditorChange}
                  onMount={handleEditorDidMount}
                  loading={
                    <div className="monaco-loading-skeleton">
                      <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--accent-primary)' }} />
                      <span>Loading Monaco LaTeX Editor...</span>
                    </div>
                  }
                  options={{
                    fontSize: editorFontSize,
                    fontFamily: 'JetBrains Mono, Menlo, monospace',
                    minimap: { enabled: false },
                    wordWrap: 'on',
                    lineNumbers: 'on',
                    glyphMargin: true,
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    tabSize: 2,
                    dragAndDrop: true
                  }}
                />
              </div>
            </div>

            {/* Vertical Splitter Handle (Left vs Right) */}
            <div
              className="splitter-v"
              onMouseDown={handleMouseDownSplitterX}
              title="Drag to resize Editor and PDF Viewer width"
            />

            {/* PDF Viewer with Zoom Controls (Right) */}
            <div className="frame-panel" style={{ width: `calc(${100 - splitRatioX}% - 6px)` }}>
              <div className="frame-header">
                <div className="frame-title">
                  <Eye size={13} />
                </div>

                {/* PDF Scale Zoom Controls */}
                <div className="zoom-controls-group">
                  <button
                    className="zoom-btn"
                    onClick={() => setPdfScale(prev => Math.max(50, prev - 15))}
                    title="PDF Zoom Out"
                  >
                    <ZoomOut size={12} />
                  </button>
                  <span className="zoom-label">{pdfScale}%</span>
                  <button
                    className="zoom-btn"
                    onClick={() => setPdfScale(prev => Math.min(250, prev + 15))}
                    title="PDF Zoom In"
                  >
                    <ZoomIn size={12} />
                  </button>
                </div>
              </div>

              <div className="frame-content" style={{ overflow: 'auto', padding: 0 }}>
                {pdfUrl ? (
                  <div className="pdf-viewer-container" style={{ width: '100%', height: '100%', overflow: 'auto', position: 'relative' }}>
                    <div
                      style={{
                        width: `${pdfScale}%`,
                        height: `${pdfScale}%`,
                        minWidth: '100%',
                        minHeight: '100%',
                        transition: 'width 0.15s ease, height 0.15s ease'
                      }}
                    >
                      {(() => {
                        const cleanBase = pdfUrl.split('&t=')[0].split('?t=')[0];
                        const sep = cleanBase.includes('?') ? '&' : '?';
                        const iframeSrc = `${cleanBase}${sep}t=${pdfTimestamp}#zoom=${pdfScale}&toolbar=0&navpanes=0`;
                        return (
                          <iframe
                            key={`pdf-viewer-${activeFile}-${pdfScale}-${pdfTimestamp}`}
                            src={iframeSrc}
                            className="pdf-iframe"
                            style={{
                              width: '100%',
                              height: '100%',
                              border: 'none',
                              pointerEvents: (isDraggingAi || isResizingAi) ? 'none' : 'auto'
                            }}
                            title="LaTeX PDF Output"
                          />
                        );
                      })()}
                    </div>
                  </div>
                ) : (
                  <div className="pdf-empty-state">
                    {isCompiling ? (
                      <>
                        <RefreshCw size={32} className="animate-spin" style={{ opacity: 0.7, color: 'var(--accent-primary)' }} />
                        <div style={{ fontWeight: 600 }}>Compiling Document...</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)' }}>
                          Generating live PDF preview...
                        </div>
                      </>
                    ) : (
                      <>
                        <FileText size={32} style={{ opacity: 0.5 }} />
                        <div>PDF Output Ready</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)' }}>
                          Click Compile or edit text to view output.
                        </div>
                        <button
                          className="btn-minimal btn-primary"
                          style={{ marginTop: '8px', fontSize: '0.75rem', padding: '4px 12px' }}
                          onClick={() => onCompile && onCompile(editorContent)}
                        >
                          Compile Document
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Horizontal Splitter Handle (Top vs Bottom) */}
          {!isLogsCollapsed && (
            <div
              className="splitter-h"
              onMouseDown={handleMouseDownSplitterY}
              title="Drag to adjust height between Editor/PDF and Logs panel"
            />
          )}

          {/* BOTTOM SECTION: Collapsible Small Logs & Diagnostics (Width-to-Width) */}
          <div
            className="bottom-split-container"
            style={{ height: isLogsCollapsed ? '34px' : `calc(${100 - splitRatioY}% - 6px)` }}
          >
            <div className="frame-panel full-width-panel">
              <div className="frame-header" style={{ padding: 0 }}>
                <div className="log-tabs">
                  <div
                    className={`log-tab ${activeLogTab === 'diagnostics' ? 'active' : ''}`}
                    onClick={() => setActiveLogTab('diagnostics')}
                  >
                    <AlertCircle size={12} style={{ display: 'inline', marginRight: '4px' }} />
                    Diagnostics ({diagnostics.length})
                  </div>
                  <div
                    className={`log-tab ${activeLogTab === 'console' ? 'active' : ''}`}
                    onClick={() => setActiveLogTab('console')}
                  >
                    <Terminal size={12} style={{ display: 'inline', marginRight: '4px' }} />
                    Console Logs
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingRight: '10px' }}>
                  <button
                    className="ai-icon-btn"
                    onClick={() => setIsLogsCollapsed(prev => !prev)}
                    title={isLogsCollapsed ? 'Expand Logs Panel' : 'Collapse Logs Panel'}
                  >
                    {isLogsCollapsed ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                </div>
              </div>

              {!isLogsCollapsed && (
                <div className="frame-content">
                  <div className="log-frame-container">
                    {activeLogTab === 'diagnostics' ? (
                      <div className="log-content">
                        {diagnostics.length > 0 ? (
                          diagnostics.map((diag, index) => (
                            <div
                              key={index}
                              className={`diagnostic-item ${diag.severity}`}
                              onClick={() => jumpToLine(diag.line)}
                              title="Click to jump to line in editor"
                            >
                              <span className="line-badge">Line {diag.line}</span>
                              <span>{diag.message}</span>
                            </div>
                          ))
                        ) : (
                          <div style={{ color: 'var(--accent-success)', padding: '6px 0' }}>
                            ✔ No compilation errors or warnings. Document syntax clean.
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="log-content" style={{ whiteSpace: 'pre-wrap' }}>
                        {logOutput || 'Console output empty. Trigger compilation to view logs.'}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* HOVERABLE FLOATING & RESIZABLE INTERACTIVE 3-TAB AI ASSISTANT BOX */}
      {isAiBoxOpen && (
        <div
          className="hoverable-ai-box"
          style={{
            top: `${aiPos.y}px`,
            left: `${aiPos.x}px`,
            width: `${aiSize.width}px`,
            height: `${aiSize.height}px`
          }}
        >
          {/* Draggable Header */}
          <div className="ai-box-header" onMouseDown={handleAiHeaderMouseDown}>
            <div className="ai-box-header-title">
              <Bot size={14} className="ai-header-icon" />
              <span className="ai-header-name">AI ASSISTANT</span>
              <span className="ai-model-tag">{config.selected_model}</span>
            </div>
            <div className="ai-box-header-actions" onMouseDown={(e) => e.stopPropagation()}>
              <button
                className="ai-icon-btn close-ai-btn"
                onMouseDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleAiBox();
                }}
                title="Close AI Assistant"
                aria-label="Close AI Assistant"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* 2-TAB NAVIGATION BAR (CODE & DEBUG ONLY) */}
          <div className="ai-box-nav-tabs">
            <button
              className={`ai-box-tab-btn ${aiTab === 'code' ? 'active' : ''}`}
              onClick={() => setAiTab('code')}
            >
              <Code size={13} />
              <span>Code</span>
            </button>
            <button
              className={`ai-box-tab-btn ${aiTab === 'debug' ? 'active' : ''}`}
              onClick={() => setAiTab('debug')}
            >
              <Bug size={13} />
              <span>Debug</span>
              {diagnostics && diagnostics.filter(d => d.severity === 'error').length > 0 && (
                <span className="ai-tab-badge-error">
                  {diagnostics.filter(d => d.severity === 'error').length}
                </span>
              )}
            </button>
          </div>

          {/* TAB 1: CODE GENERATION WITH DRAG & DROP TO EDITOR */}
          {aiTab === 'code' && (
            <div className="ai-box-body">
              {/* Prompt Input Row for LaTeX Code */}
              <div className="ai-input-row">
                <input
                  type="text"
                  className="ai-input"
                  placeholder="Ask for any LaTeX code (e.g. 'table with 3 columns', 'matrix', 'subfigures', 'algorithm')..."
                  value={codePrompt}
                  onChange={(e) => setCodePrompt(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleGenerateCodeTemplate()}
                />
                <button
                  className="btn-minimal btn-primary"
                  onClick={() => handleGenerateCodeTemplate()}
                  disabled={isCodeLoading}
                  title="Generate LaTeX Code"
                >
                  {isCodeLoading ? <RefreshCw className="animate-spin" size={13} /> : <Wand2 size={13} />}
                </button>
              </div>

              {/* Code Result Area with Draggable Snippet Card */}
              <div className="template-result-area">
                {isCodeLoading ? (
                  <div className="template-loading-state">
                    <RefreshCw className="animate-spin" size={24} style={{ color: 'var(--accent-primary)', marginBottom: '8px' }} />
                    <div>Generating code with <code>{config.selected_model}</code>...</div>
                  </div>
                ) : codeResult ? (
                  codeResult.is_template === false || codeResult.status === 'unknown' ? (
                    /* Strict "I don't know." response for non-LaTeX questions */
                    <div className="ai-unknown-box">
                      <div className="ai-unknown-header">
                        <AlertCircle size={18} color="var(--accent-warning)" />
                        <span className="ai-unknown-title">{codeResult.response || "I don't know."}</span>
                      </div>
                      <p className="ai-unknown-desc">
                        The <strong>Code</strong> generator creates LaTeX snippets, environments, tables, equations, and structures. Please ask a LaTeX-related code request.
                      </p>
                    </div>
                  ) : (
                    /* Valid LaTeX Code Result Card with Draggable Snippet */
                    <div className="template-card-container">
                      <div className="template-card-header">
                        <div className="template-title-text">{codeResult.title}</div>
                        <div className="template-pkg-badges">
                          {codeResult.packages && codeResult.packages.map((pkg, idx) => (
                            <span key={idx} className="pkg-badge">\usepackage{`{${pkg}}`}</span>
                          ))}
                        </div>
                      </div>

                      {codeResult.description && (
                        <div className="template-desc-text">{codeResult.description}</div>
                      )}

                      {/* DRAGGABLE CODE BLOCK INTO MONACO EDITOR */}
                      <div
                        className={`draggable-code-card ${isDraggingSnippet ? 'is-dragging' : ''}`}
                        draggable="true"
                        onDragStart={(e) => handleCodeSnippetDragStart(e, codeResult.code)}
                        onDragEnd={handleCodeSnippetDragEnd}
                        title="Click and drag this code block directly onto any line in Monaco Editor"
                      >
                        <div className="draggable-code-header">
                          <div className="drag-handle-pill">
                            <GripVertical size={13} />
                            <span>⠿ DRAG & DROP INTO EDITOR</span>
                          </div>
                          <span className="drag-hint">Drag into editor panel</span>
                        </div>
                        <pre className="draggable-code-pre">
                          <code>{codeResult.code}</code>
                        </pre>
                      </div>

                      {/* Actions: Insert at Cursor & Copy */}
                      <div className="template-actions-row">
                        <button
                          className="btn-minimal btn-primary btn-sm"
                          onClick={() => handleInsertText(codeResult.code)}
                          title="Insert code at current editor cursor position"
                        >
                          <Check size={13} /> Insert at Cursor
                        </button>
                        <button
                          className="btn-minimal btn-sm"
                          onClick={() => handleCopyText(codeResult.code)}
                          title="Copy snippet to clipboard"
                        >
                          <Copy size={13} /> {copied ? 'Copied!' : 'Copy Snippet'}
                        </button>
                      </div>
                    </div>
                  )
                ) : (
                  /* Initial Empty State */
                  <div className="template-empty-state">
                    <Code size={30} style={{ opacity: 0.6, color: 'var(--accent-primary)', marginBottom: '8px' }} />
                    <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>LaTeX Code Generator</div>
                    <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '4px', maxWidth: '340px' }}>
                      Ask for any LaTeX code above and <strong>drag & drop</strong> the generated snippet directly into any line in your editor!
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: ERROR DIAGNOSTICS & USER-INITIATED AI DEBUG */}
          {aiTab === 'debug' && (
            <div className="ai-box-body debug-tab-body">
              {/* Header Diagnostics Summary */}
              <div className="debug-header-bar">
                <div className="debug-status-pill">
                  {isDebugLoading ? (
                    <span className="pill-loading">
                      <RefreshCw size={13} className="animate-spin" /> Generating...
                    </span>
                  ) : diagnostics && diagnostics.filter(d => d.severity === 'error').length > 0 ? (
                    <span className="pill-error">
                      <AlertCircle size={13} /> {diagnostics.filter(d => d.severity === 'error').length} Error(s) in {activeFile}
                    </span>
                  ) : (
                    <span className="pill-success">
                      <CheckCircle2 size={13} /> Document Clean (0 Errors)
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    className="btn-minimal btn-xs"
                    onClick={() => runDebugAnalysis()}
                    disabled={isDebugLoading}
                    title="Re-analyze document errors with AI"
                  >
                    <RefreshCw size={11} className={isDebugLoading ? "animate-spin" : ""} /> {isDebugLoading ? 'Generating...' : 'Re-analyze'}
                  </button>
                  <span className="debug-file-label">Active: <code>{activeFile}</code></span>
                </div>
              </div>

              {/* Debug Results Area */}
              <div className="debug-results-area">
                {isDebugLoading ? (
                  <div className="template-loading-state" style={{ padding: '36px 16px', textAlign: 'center' }}>
                    <RefreshCw className="animate-spin" size={26} style={{ color: 'var(--accent-primary)', marginBottom: '12px' }} />
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-main)', marginBottom: '4px' }}>Generating Debug Analysis...</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      Inspecting error diagnostics & source code with <code>{config.selected_model || 'TeXa AI'}</code>...
                    </div>
                  </div>
                ) : debugReport ? (
                  debugReport.status === 'clean' ? (
                    /* Clean State Output */
                    <div className="debug-clean-card">
                      <div className="debug-clean-header">
                        <CheckCircle2 size={20} color="var(--accent-success)" />
                        <span style={{ fontWeight: 700, color: 'var(--accent-success)' }}>Document Syntax is Clean!</span>
                      </div>
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-main)', margin: '8px 0' }}>
                        {debugReport.summary}
                      </p>
                      {debugReport.advice && (
                        <div className="debug-advice-box">
                          {debugReport.advice}
                        </div>
                      )}
                    </div>
                  ) : (
                    /* Issues Found Output List with Step-by-Step Resolution */
                    <div className="debug-issues-container">
                      <div className="debug-summary-banner">
                        <AlertCircle size={14} color="var(--accent-error)" />
                        <span>{debugReport.summary}</span>
                      </div>

                      {debugReport.issues && debugReport.issues.map((issue, idx) => {
                        const snippetToUse = issue.fix_code || issue.solution || '';
                        return (
                          <div key={idx} className={`debug-issue-card ${issue.severity || 'error'}`}>
                            {/* Issue Top Row */}
                            <div className="debug-issue-top">
                              <span className="issue-title-text">
                                <strong>#{idx + 1}</strong> {issue.title}
                              </span>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                {issue.file && (
                                  <span className="debug-file-badge">{issue.file}</span>
                                )}
                                <button
                                  className="line-jump-badge"
                                  onClick={() => jumpToLine(issue.line)}
                                  title="Click to jump to line in editor"
                                >
                                  Line {issue.line}
                                </button>
                              </div>
                            </div>

                            {/* Context Line Preview */}
                            {issue.context_line && (
                              <div className="issue-code-snippet">
                                <code>{issue.context_line}</code>
                              </div>
                            )}

                            {/* Root Cause */}
                            <div className="issue-detail-row cause-row">
                              <span className="detail-label cause-label">Root Cause:</span>
                              <span className="detail-value">{issue.root_cause}</span>
                            </div>

                            {/* Solution */}
                            <div className="issue-detail-row solution-row">
                              <span className="detail-label solution-label">Solution:</span>
                              <span className="detail-value solution-value">{issue.solution}</span>
                            </div>

                            {/* DRAGGABLE LATEX FIX CODE BLOCK INTO MONACO EDITOR */}
                            {snippetToUse && (
                              <div className="debug-fix-code-section" style={{ marginTop: '10px' }}>
                                <div
                                  className={`draggable-code-card ${isDraggingSnippet ? 'is-dragging' : ''}`}
                                  draggable="true"
                                  onDragStart={(e) => handleCodeSnippetDragStart(e, snippetToUse)}
                                  onDragEnd={handleCodeSnippetDragEnd}
                                  title="Click and drag this LaTeX fix code directly into Monaco Editor"
                                >
                                  <div className="draggable-code-header">
                                    <div className="drag-handle-pill">
                                      <GripVertical size={13} />
                                      <span>⠿ DRAG FIX INTO EDITOR</span>
                                    </div>
                                    <span className="drag-hint">Drag into editor panel</span>
                                  </div>
                                  <pre className="draggable-code-pre">
                                    <code>{snippetToUse}</code>
                                  </pre>
                                </div>

                                <div className="template-actions-row" style={{ marginTop: '6px' }}>
                                  <button
                                    className="btn-minimal btn-primary btn-xs"
                                    onClick={() => handleInsertText(snippetToUse)}
                                    title="Insert LaTeX fix code at current cursor position in editor"
                                  >
                                    <Check size={12} /> Insert at Cursor
                                  </button>
                                  <button
                                    className="btn-minimal btn-xs"
                                    onClick={() => handleCopyText(snippetToUse)}
                                    title="Copy LaTeX fix code to clipboard"
                                  >
                                    <Copy size={12} /> Copy Code
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )
                ) : (
                  /* Initial State: Ready to run AI Analysis or Clean */
                  diagnostics && diagnostics.filter(d => d.severity === 'error').length > 0 ? (
                    <div className="debug-empty-state" style={{ padding: '28px 16px', textAlign: 'center' }}>
                      <AlertCircle size={32} style={{ color: 'var(--accent-error)', marginBottom: '10px', opacity: 0.9 }} />
                      <div style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-main)' }}>
                        {diagnostics.filter(d => d.severity === 'error').length} Compilation Error(s) Detected
                      </div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '8px auto 16px', maxWidth: '360px' }}>
                        Errors were detected in <code>{activeFile}</code>. Click <strong>Re-analyze</strong> to run AI model diagnostic and generate draggable LaTeX fixes.
                      </div>
                      <button
                        className="btn-minimal btn-primary btn-sm"
                        onClick={() => runDebugAnalysis()}
                        style={{ margin: '0 auto', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                      >
                        <Wand2 size={13} /> Run AI Debug Analysis
                      </button>
                    </div>
                  ) : (
                    <div className="debug-empty-state">
                      <CheckCircle2 size={30} style={{ opacity: 0.7, color: 'var(--accent-success)', marginBottom: '8px' }} />
                      <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>Document Syntax is Clean</div>
                      <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '4px', maxWidth: '340px' }}>
                        No compiler errors detected. If an error occurs during compilation, click Re-analyze to generate solutions.
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {/* Bottom-Right Corner Resize Grip Handle */}
          <div
            className="ai-box-resizer"
            onMouseDown={handleAiResizeMouseDown}
            title="Drag to resize AI box height and width"
          />
        </div>
      )}

      {/* Global Transparent Overlay for 100% Smooth Dragging & Resizing Without Mouse Event Loss */}
      {(isDraggingAi || isResizingAi) && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 99999,
            cursor: isResizingAi ? 'nwse-resize' : 'move',
            userSelect: 'none',
            background: 'transparent'
          }}
          onMouseUp={() => {
            setIsDraggingAi(false);
            setIsResizingAi(false);
            document.body.style.userSelect = '';
          }}
        />
      )}

      {/* CREATE NEW FILE MODAL */}
      {showNewFileModal && (
        <div className="modal-backdrop">
          <div className="wizard-modal" style={{ maxWidth: '400px' }}>
            <div className="wizard-header">
              <div className="wizard-title"><Plus size={15} /> Create New File</div>
              <button className="ai-icon-btn" onClick={() => setShowNewFileModal(false)}><X size={14} /></button>
            </div>
            <div className="wizard-body">
              <label className="form-label">
                {selectedFolder ? `Creating inside '${selectedFolder}/'` : 'File Name (e.g. `chapter1.tex`, `ref.bib`):'}
              </label>
              <input
                type="text"
                className="form-input"
                value={newFileName}
                onChange={(e) => setNewFileName(e.target.value)}
                placeholder="filename.tex"
                autoFocus
              />
            </div>
            <div className="wizard-footer" style={{ gap: '8px' }}>
              <button className="btn-minimal btn-primary" onClick={handleCreateFile}>Create</button>
              <button className="btn-minimal" onClick={() => setShowNewFileModal(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* CREATE NEW FOLDER MODAL */}
      {showNewFolderModal && (
        <div className="modal-backdrop">
          <div className="wizard-modal" style={{ maxWidth: '400px' }}>
            <div className="wizard-header">
              <div className="wizard-title"><FolderPlus size={15} /> Create New Folder</div>
              <button className="ai-icon-btn" onClick={() => setShowNewFolderModal(false)}><X size={14} /></button>
            </div>
            <div className="wizard-body">
              <label className="form-label">Folder Name (e.g. `figures`, `sections`):</label>
              <input
                type="text"
                className="form-input"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="foldername"
                autoFocus
              />
            </div>
            <div className="wizard-footer" style={{ gap: '8px' }}>
              <button className="btn-minimal btn-primary" onClick={handleCreateFolder}>Create Folder</button>
              <button className="btn-minimal" onClick={() => setShowNewFolderModal(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* RENAME FILE MODAL */}
      {showRenameModal && (
        <div className="modal-backdrop">
          <div className="wizard-modal" style={{ maxWidth: '400px' }}>
            <div className="wizard-header">
              <div className="wizard-title"><Edit2 size={15} /> Rename File</div>
              <button className="ai-icon-btn" onClick={() => setShowRenameModal(false)}><X size={14} /></button>
            </div>
            <div className="wizard-body">
              <label className="form-label">New File Name for `{targetRenameFile}`:</label>
              <input
                type="text"
                className="form-input"
                value={renameNewName}
                onChange={(e) => setRenameNewName(e.target.value)}
                placeholder="newname.tex"
                autoFocus
              />
            </div>
            <div className="wizard-footer" style={{ gap: '8px' }}>
              <button className="btn-minimal btn-primary" onClick={handleRenameFile}>Rename</button>
              <button className="btn-minimal" onClick={() => setShowRenameModal(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* DUPLICATE FILE / FOLDER REPLACE OR CANCEL MODAL */}
      {showReplaceModal && (
        <div className="modal-backdrop">
          <div className="wizard-modal" style={{ maxWidth: '420px' }}>
            <div className="wizard-header">
              <div className="wizard-title" style={{ color: 'var(--accent-warning)' }}>
                <AlertCircle size={15} /> {duplicateTarget?.type === 'folder' ? 'Folder Already Exists' : 'File Already Exists'}
              </div>
              <button className="ai-icon-btn" onClick={handleCancelReplace}><X size={14} /></button>
            </div>
            <div className="wizard-body">
              <p style={{ fontSize: '0.85rem', color: 'var(--text-main)', margin: '0 0 10px 0', lineHeight: 1.4 }}>
                A {duplicateTarget?.type || 'item'} named <strong>{duplicateTarget?.path}</strong> already exists in this workspace.
              </p>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.4 }}>
                Do you want to replace it with the new {duplicateTarget?.type || 'item'} or cancel creation?
              </p>
            </div>
            <div className="wizard-footer" style={{ gap: '8px' }}>
              <button className="btn-minimal btn-primary" onClick={handleConfirmReplace}>
                Replace {duplicateTarget?.type === 'folder' ? 'Folder' : 'File'}
              </button>
              <button className="btn-minimal" onClick={handleCancelReplace}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE FILE CONFIRMATION MODAL */}
      {showDeleteModal && (
        <div className="modal-backdrop">
          <div className="wizard-modal" style={{ maxWidth: '400px' }}>
            <div className="wizard-header">
              <div className="wizard-title" style={{ color: 'var(--accent-danger, #bf616a)' }}>
                <Trash2 size={15} /> Delete {targetDeleteFile?.type === 'folder' ? 'Folder' : 'File'}
              </div>
              <button className="ai-icon-btn" onClick={() => { setShowDeleteModal(false); setTargetDeleteFile(null); }}>
                <X size={14} />
              </button>
            </div>
            <div className="wizard-body">
              <p style={{ fontSize: '0.85rem', color: 'var(--text-main)', margin: '0 0 10px 0', lineHeight: 1.5 }}>
                Are you sure you want to permanently delete this {targetDeleteFile?.type || 'item'}?
                {targetDeleteFile?.type === 'folder' && (
                  <span style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    All files inside the folder will also be deleted.
                  </span>
                )}
              </p>
              <p style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-danger, #bf616a)', fontFamily: 'var(--font-mono)', margin: '0 0 10px 0', wordBreak: 'break-all' }}>
                {targetDeleteFile?.path}
              </p>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.4 }}>
                This action cannot be undone.
              </p>
            </div>
            <div className="wizard-footer" style={{ gap: '8px' }}>
              <button
                className="btn-minimal btn-danger"
                onClick={handleDeleteFile}
              >
                Delete
              </button>
              <button
                className="btn-minimal"
                onClick={() => { setShowDeleteModal(false); setTargetDeleteFile(null); }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}





