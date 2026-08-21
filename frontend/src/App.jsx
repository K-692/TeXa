import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import SetupPage from './pages/SetupPage';
import EditorPage from './pages/EditorPage';
import LoadingScreen from './components/LoadingScreen';
import { AlertCircle, Save, Home, Settings, X, HelpCircle } from 'lucide-react';
import './styles/minimal.css';

export default function App() {
  // Home (Setup) page is always the initial landing page on launch
  const [currentPage, setCurrentPage] = useState('setup'); // 'setup' | 'editor'
  const [theme, setTheme] = useState('dark');
  const [isAiBoxOpen, setIsAiBoxOpen] = useState(false);
  const [showNoModelAlert, setShowNoModelAlert] = useState(false);
  const [showSaveHomeModal, setShowSaveHomeModal] = useState(false);
  const [hasDownloadedModel, setHasDownloadedModel] = useState(false);
  
  // Workspace Launching & AI Model Loading Screen State
  const [isLaunchingWorkspace, setIsLaunchingWorkspace] = useState(false);
  const [launchStep, setLaunchStep] = useState(1);
  const [launchProgress, setLaunchProgress] = useState(20);
  const [launchMessage, setLaunchMessage] = useState('Initializing TeXa Workspace...');
  
  const [config, setConfig] = useState({
    working_directory: '/Users/krish/Desktop/TeXa/projects',
    active_file: 'main.tex',
    selected_model: '',
    custom_model_id: null,
    hf_token: null,
    compiler_engine: 'hybrid',
    auto_validate: true,
    theme: 'dark'
  });

  const [editorContent, setEditorContent] = useState('');
  const [openTabs, setOpenTabs] = useState(['main.tex']);
  const [isCompiling, setIsCompiling] = useState(false);
  const [pdfUrl, setPdfUrl] = useState('/api/pdf?file=main.pdf');
  const [pdfTimestamp, setPdfTimestamp] = useState(Date.now());
  const [diagnostics, setDiagnostics] = useState([]);
  const [logOutput, setLogOutput] = useState('');

  // Apply theme attribute and tab title to document element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.title = 'TeXa';
  }, [theme]);

  // Load app config & check model availability on initial mount (pure info fetch, no heavy model loading)
  const checkModelStatus = () => {
    fetch('/api/ai/models')
      .then(res => res.json())
      .then(data => {
        if (data.status) {
          const isDownloaded = data.status.has_downloaded_models || data.status.is_active_model_downloaded;
          setHasDownloadedModel(Boolean(isDownloaded));
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetch('/api/config')
      .then(res => res.json())
      .then(data => {
        if (data) {
          setConfig(data);
          if (data.theme) setTheme(data.theme);
        }
      })
      .catch(() => {});

    checkModelStatus();

    // Read active document content and compile
    fetch('/api/file/read?path=main.tex')
      .then(res => res.json())
      .then(data => {
        if (data && data.content) {
          setEditorContent(data.content);
          handleCompile(data.content, 'main.tex');
        }
      })
      .catch(() => {});
  }, []);

  // Update Config Handler with optimistic local state update
  const handleUpdateConfig = (newConfigData) => {
    setConfig(prev => ({ ...prev, ...newConfigData }));
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfigData)
    })
      .then(res => res.json())
      .then(updated => {
        setConfig(updated);
        checkModelStatus();
      })
      .catch(err => console.error('Failed to update config:', err));
  };

  // Switch Active File in Editor & add to Open Tabs
  const handleSelectFile = (relPath) => {
    handleUpdateConfig({ active_file: relPath });
    if (!openTabs.includes(relPath)) {
      setOpenTabs(prev => [...prev, relPath]);
    }
    fetch(`/api/file/read?path=${encodeURIComponent(relPath)}`)
      .then(res => res.json())
      .then(data => {
        if (data && data.content !== undefined) {
          setEditorContent(data.content);
          if (config.auto_validate ?? true) {
            handleCompile(data.content, relPath);
          }
        }
      })
      .catch(err => console.error('Error loading file:', err));
  };

  const handleCloseTab = (tabPath) => {
    const nextTabs = openTabs.filter(t => t !== tabPath);
    setOpenTabs(nextTabs);
    if (config.active_file === tabPath && nextTabs.length > 0) {
      handleSelectFile(nextTabs[nextTabs.length - 1]);
    }
  };

  // Save active file content to backend
  const handleSaveAll = () => {
    const targetFile = config.active_file || 'main.tex';
    fetch('/api/file/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rel_path: targetFile,
        content: editorContent
      })
    })
      .then(res => res.json())
      .then(() => {
        // Trigger background compile on save
        handleCompile(editorContent, targetFile);
      })
      .catch(err => console.error('Failed to save file:', err));
  };

  // Compile Handler - Directly invokes /api/compile which persists latest buffer and returns diagnostics
  const handleCompile = (currentContent = null, targetFile = null) => {
    setIsCompiling(true);
    const contentToSend = (typeof currentContent === 'string' && currentContent !== null) ? currentContent : editorContent;
    const fileToCompile = targetFile || config.active_file || 'main.tex';

    return fetch('/api/compile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rel_path: fileToCompile,
        content: contentToSend
      })
    })
      .then(res => res.json())
      .then(data => {
        setIsCompiling(false);
        setDiagnostics(data.diagnostics || []);
        setLogOutput(data.log_output || '');
        if (data.pdf_url) {
          setPdfUrl(data.pdf_url);
          setPdfTimestamp(data.timestamp || Date.now());
        }
      })
      .catch(err => {
        setIsCompiling(false);
        setLogOutput(`Compilation network error: ${err}`);
      });
  };

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    handleUpdateConfig({ theme: newTheme });
  };

  // AI Box click handler: check model availability and handle termination when closing
  const handleToggleAiBox = () => {
    if (isAiBoxOpen) {
      // User is closing the AI Box: terminate any active model run
      fetch('/api/ai/cancel', { method: 'POST' }).catch(() => {});
      setIsAiBoxOpen(false);
      return;
    }

    fetch('/api/ai/models')
      .then(res => res.json())
      .then(data => {
        const isDownloaded = data.status && (data.status.has_downloaded_models || data.status.is_active_model_downloaded);
        if (!isDownloaded) {
          setIsAiBoxOpen(false);
          setShowNoModelAlert(true);
        } else {
          setIsAiBoxOpen(true);
        }
      })
      .catch(() => {
        if (!hasDownloadedModel) {
          setIsAiBoxOpen(false);
          setShowNoModelAlert(true);
        } else {
          setIsAiBoxOpen(true);
        }
      });
  };

  // Request Home navigation with Save Progress popup modal
  const handleRequestHome = () => {
    setShowSaveHomeModal(true);
  };

  // Orchestrated launch workflow with live LoadingScreen and automatic transition
  const handleLaunchEditor = async (launchOptions = {}) => {
    setIsLaunchingWorkspace(true);
    setLaunchStep(1);
    setLaunchProgress(20);
    setLaunchMessage('Saving workspace configuration...');

    const newConfigData = {
      ...config,
      ...(launchOptions || {})
    };

    const targetModel = newConfigData.selected_model || config.selected_model || '';

    try {
      // Step 1: Save workspace & config
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfigData)
      });
      setConfig(prev => ({ ...prev, ...newConfigData }));

      // Step 2: Activate / Load AI Model into Memory
      setLaunchStep(2);
      setLaunchProgress(40);
      setLaunchMessage(`Activating AI model (${targetModel})...`);

      if (targetModel) {
        // Start load request
        const loadPromise = fetch('/api/ai/load', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model_id: targetModel,
            hf_token: newConfigData.hf_token
          })
        });

        // Poll progress during model load
        let loadFinished = false;
        loadPromise.finally(() => { loadFinished = true; });

        let currentP = 40;
        while (!loadFinished) {
          await new Promise(r => setTimeout(r, 400));
          if (loadFinished) break;
          currentP = Math.min(currentP + 6, 75);
          setLaunchProgress(currentP);
          try {
            const statusRes = await fetch('/api/ai/status');
            const statusData = await statusRes.json();
            if (statusData && statusData.message) {
              setLaunchMessage(statusData.message);
            }
          } catch (_) {}
        }

        await loadPromise.catch(err => console.warn('Model load warning:', err));
      }

      checkModelStatus();

      // Step 3: Fetch active document content & verify file buffers
      setLaunchStep(3);
      setLaunchProgress(85);
      setLaunchMessage('Mounting Monaco LaTeX editor & compiling workspace preview...');

      const activeFile = newConfigData.active_file || config.active_file || 'main.tex';
      let loadedContent = '';
      const fileRes = await fetch(`/api/file/read?path=${encodeURIComponent(activeFile)}`).catch(() => null);
      if (fileRes && fileRes.ok) {
        const fileData = await fileRes.json().catch(() => null);
        if (fileData && fileData.content !== undefined) {
          loadedContent = fileData.content;
          setEditorContent(loadedContent);
        }
      }

      // Pre-compile document so PDF is immediately ready upon entering editor
      try {
        const compRes = await fetch('/api/compile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            rel_path: activeFile,
            content: loadedContent
          })
        });
        const compData = await compRes.json();
        if (compData && compData.pdf_url) {
          setPdfUrl(compData.pdf_url);
          setPdfTimestamp(compData.timestamp || Date.now());
        }
        if (compData && compData.diagnostics) {
          setDiagnostics(compData.diagnostics);
        }
        if (compData && compData.log_output) {
          setLogOutput(compData.log_output);
        }
      } catch (compileErr) {
        console.warn('Initial compilation warning:', compileErr);
      }

      // Step 4: Finalizing & Mounting workspace (smooth automatic transition)
      await new Promise(r => setTimeout(r, 200));
      setLaunchStep(4);
      setLaunchProgress(100);
      setLaunchMessage('Workspace ready! Launching editor...');

      await new Promise(r => setTimeout(r, 250));

      // Automatic entry into the editor
      setIsLaunchingWorkspace(false);
      setCurrentPage('editor');
    } catch (err) {
      console.error('Launch sequence error:', err);
      setIsLaunchingWorkspace(false);
      setCurrentPage('editor');
    }
  };

  return (
    <div className="app-container">
      <Header
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        config={config}
        updateConfig={handleUpdateConfig}
        onCompile={() => handleCompile()}
        isCompiling={isCompiling}
        errorCount={diagnostics.filter(d => d.severity === 'error').length}
        onSaveAll={handleSaveAll}
        onRequestHome={handleRequestHome}
        theme={theme}
        toggleTheme={toggleTheme}
        isAiBoxOpen={isAiBoxOpen}
        toggleAiBox={handleToggleAiBox}
      />

      {/* DEDICATED MODEL & WORKSPACE LOADING SCREEN */}
      {isLaunchingWorkspace && (
        <LoadingScreen
          modelId={config.selected_model || config.custom_model_id || 'AI Model'}
          currentStep={launchStep}
          stepMessage={launchMessage}
          progress={launchProgress}
        />
      )}

      {currentPage === 'setup' ? (
        <SetupPage
          config={config}
          updateConfig={handleUpdateConfig}
          onLaunchEditor={handleLaunchEditor}
        />
      ) : (
        <EditorPage
          config={config}
          editorContent={editorContent}
          setEditorContent={setEditorContent}
          onCompile={handleCompile}
          isCompiling={isCompiling}
          pdfUrl={pdfUrl}
          pdfTimestamp={pdfTimestamp}
          diagnostics={diagnostics}
          logOutput={logOutput}
          activeFile={config.active_file || 'main.tex'}
          isAiBoxOpen={isAiBoxOpen}
          toggleAiBox={handleToggleAiBox}
          onSelectFile={handleSelectFile}
          openTabs={openTabs}
          onCloseTab={handleCloseTab}
        />
      )}

      {/* SAVE PROGRESS BEFORE HOME MODAL */}
      {showSaveHomeModal && (
        <div className="modal-backdrop">
          <div className="alert-modal" style={{ borderColor: 'var(--border-focus)' }}>
            <div className="alert-modal-header">
              <div className="alert-modal-title">
                <HelpCircle size={18} color="var(--accent-primary)" /> Save Workspace Progress?
              </div>
              <button className="ai-icon-btn" onClick={() => setShowSaveHomeModal(false)}>
                <X size={15} />
              </button>
            </div>
            <div className="alert-modal-body">
              Would you like to save all edits to `{config.active_file}` before returning to the Home / Setup page?
            </div>
            <div className="alert-modal-footer">
              <button
                className="btn-minimal btn-primary"
                onClick={() => {
                  handleSaveAll();
                  setShowSaveHomeModal(false);
                  setCurrentPage('setup');
                }}
              >
                <Save size={13} /> Save & Go Home
              </button>
              <button
                className="btn-minimal"
                onClick={() => {
                  setShowSaveHomeModal(false);
                  setCurrentPage('setup');
                }}
              >
                Discard & Go Home
              </button>
              <button className="btn-minimal" onClick={() => setShowSaveHomeModal(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* NO MODEL POP-UP ALERT MODAL */}
      {showNoModelAlert && (
        <div className="modal-backdrop">
          <div className="alert-modal">
            <div className="alert-modal-header">
              <div className="alert-modal-title">
                <AlertCircle size={18} color="var(--accent-warning)" /> No AI Model Available
              </div>
              <button className="ai-icon-btn" onClick={() => setShowNoModelAlert(false)}>
                <X size={15} />
              </button>
            </div>
            <div className="alert-modal-body">
              No AI model is downloaded or available in your TeXa models folder yet.
              <br /><br />
              Please download or select an AI model from the Home page first to enable the AI Box.
            </div>
            <div className="alert-modal-footer">
              <button
                className="btn-minimal btn-primary"
                onClick={() => {
                  setShowNoModelAlert(false);
                  setCurrentPage('setup');
                }}
              >
                <Home size={13} /> Go to Home
              </button>
              <button className="btn-minimal" onClick={() => setShowNoModelAlert(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}



