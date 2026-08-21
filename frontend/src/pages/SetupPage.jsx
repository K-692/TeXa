import React, { useState, useEffect, useRef } from 'react';
import {
  Folder,
  Cpu,
  Download,
  ArrowRight,
  Check,
  FolderPlus,
  Sparkles,
  RefreshCw,
  Key,
  HelpCircle,
  HardDrive,
  Eye,
  EyeOff,
  AlertCircle
} from 'lucide-react';

export default function SetupPage({ config, updateConfig, onLaunchEditor }) {
  // Setup State Management
  const [workingDir, setWorkingDir] = useState(config.working_directory || '/Users/krish/Desktop/TeXa/projects');
  const [customModelId, setCustomModelId] = useState(config.custom_model_id || '');
  const [selectedModel, setSelectedModel] = useState(config.selected_model || '');
  const [hfToken, setHfToken] = useState(config.hf_token || '');
  const [showToken, setShowToken] = useState(false);
  const [tokenSaved, setTokenSaved] = useState(false);
  const [downloadedModels, setDownloadedModels] = useState([]);

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning!';
    if (hour < 17) return 'Good Afternoon!';
    if (hour < 22) return 'Good Evening!';
    return 'Good Night!';
  };

  const [aiStatus, setAiStatus] = useState({
    status: 'not_loaded',
    progress: 0,
    message: 'No AI model loaded.',
    download_speed: '0.0 MB/s',
    downloaded_size: '0 MB',
    total_size: '0 MB',
    eta: '0s',
    has_downloaded_models: false
  });

  // Fetch installed local models and AI status on load without triggering any model loads
  const fetchModels = () => {
    fetch('/api/ai/models')
      .then(res => res.json())
      .then(data => {
        if (data.presets) {
          setDownloadedModels(data.presets);
          // If no model is currently selected and we have downloaded models, default to first downloaded
          if (!selectedModel && data.presets.length > 0) {
            setSelectedModel(data.presets[0].id);
          }
        }
        if (data.status) {
          setAiStatus(data.status);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchModels();
  }, []);

  // Update token state when config changes
  useEffect(() => {
    if (config.hf_token) {
      setHfToken(config.hf_token);
    }
    if (config.working_directory) {
      setWorkingDir(config.working_directory);
    }
    if (config.selected_model) {
      setSelectedModel(config.selected_model);
    }
  }, [config]);

  // Poll download progress when downloading
  useEffect(() => {
    let interval;
    if (aiStatus.status === 'downloading') {
      interval = setInterval(() => {
        fetch('/api/ai/status')
          .then(res => res.json())
          .then(data => {
            setAiStatus(data);
            if (data.status === 'ready') {
              fetchModels();
            }
          })
          .catch(() => {});
      }, 800);
    }
    return () => clearInterval(interval);
  }, [aiStatus.status]);

  // Handle Token Save to .env
  const handleSaveToken = (tokenToSave) => {
    const tokenVal = (typeof tokenToSave === 'string' ? tokenToSave : hfToken).trim();
    fetch('/api/ai/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hf_token: tokenVal })
    })
      .then(res => res.json())
      .then(() => {
        setTokenSaved(true);
        updateConfig({ hf_token: tokenVal });
        setTimeout(() => setTokenSaved(false), 3000);
      })
      .catch(err => console.error('Failed to save HF token:', err));
  };

  const handleDownloadModel = (modelIdToDownload) => {
    const modelId = (modelIdToDownload || customModelId || selectedModel || '').trim();
    if (!modelId) {
      alert('Please enter a valid Hugging Face Model ID (e.g. google/gemma-3-1b-it).');
      return;
    }

    setSelectedModel(modelId);
    setCustomModelId(modelId);

    // Save token if entered
    if (hfToken.trim()) {
      handleSaveToken(hfToken);
    }

    fetch('/api/ai/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_id: modelId,
        is_custom: true,
        hf_token: hfToken.trim() || undefined
      })
    })
      .then(res => res.json())
      .then(data => {
        if (data.status) {
          setAiStatus({
            status: 'downloading',
            progress: 10,
            message: `Downloading ${modelId}... Meanwhile, sit back, relax, and grab a coffee ☕!`,
            download_speed: 'Active',
            downloaded_size: '0 MB',
            total_size: '...',
            eta: '...'
          });
        }
      })
      .catch(err => alert(`Failed to initiate download: ${err}`));
  };

  const [isBrowsingDir, setIsBrowsingDir] = useState(false);

  // Direct Native System Folder Dialog Selection Handler
  const handleBrowseDirectory = async () => {
    setIsBrowsingDir(true);
    try {
      const res = await fetch('/api/browse-directory', { method: 'POST' });
      const data = await res.json();
      if (data && data.status === 'ok' && data.path) {
        setWorkingDir(data.path);
        updateConfig({ working_directory: data.path });
      }
    } catch (err) {
      console.error('Failed to open system folder dialog:', err);
    } finally {
      setIsBrowsingDir(false);
    }
  };

  const handleLaunch = () => {
    const activeModel = (selectedModel || customModelId || '').trim();
    if (!activeModel) {
      alert('Please enter or select a Hugging Face model before launching.');
      return;
    }

    const finalWorkingDir = workingDir.trim() || config.working_directory || '/Users/krish/Desktop/TeXa/projects';

    if (onLaunchEditor) {
      onLaunchEditor({
        working_directory: finalWorkingDir,
        selected_model: activeModel,
        custom_model_id: activeModel,
        hf_token: hfToken.trim() || undefined,
        compiler_engine: 'hybrid'
      });
    }
  };

  const effectiveModel = selectedModel || customModelId;

  return (
    <div className="setup-page">
      <div className="setup-card">
        <div className="setup-header">
          <div className="setup-title">
            <Sparkles size={20} className="setup-icon" /> {getGreeting()}
          </div>
          <div className="setup-subtitle">
            Configure your local workspace folder and select your customized Hugging Face model for LaTeX generation.
          </div>
        </div>

        {/* 1. Project Working Directory Selector with Native System Folder Dialog */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Folder size={14} /> Select Working Directory
          </label>

          <div className="browse-dir-row">
            <input
              type="text"
              className="form-input"
              value={workingDir}
              onChange={(e) => {
                setWorkingDir(e.target.value);
                updateConfig({ working_directory: e.target.value });
              }}
              onBlur={(e) => {
                const val = e.target.value.trim();
                if (val) {
                  setWorkingDir(val);
                  updateConfig({ working_directory: val });
                }
              }}
              placeholder="/Users/krish/Desktop/TeXa/projects"
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn-minimal btn-primary"
              onClick={handleBrowseDirectory}
              disabled={isBrowsingDir}
              style={{ whiteSpace: 'nowrap', padding: '8px 16px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              title="Open system folder picker to choose your working directory"
            >
              {isBrowsingDir ? <RefreshCw size={14} className="animate-spin" /> : <FolderPlus size={14} />} Browse
            </button>
          </div>
          <div className="form-hint">
            Directly choose or enter your target project folder. TeXa opens, edits, and compiles LaTeX documents in this workspace.
          </div>
        </div>

        {/* 2. Hugging Face Access Token (Optional) - Positioned before model cards */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Key size={14} /> Hugging Face Token (Optional)
            </span>
            {tokenSaved && (
              <span style={{ fontSize: '0.70rem', color: 'var(--accent-success)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Check size={12} /> Saved in .env
              </span>
            )}
          </label>

          <div className="browse-dir-row">
            <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center' }}>
              <input
                type={showToken ? 'text' : 'password'}
                className="form-input"
                value={hfToken}
                onChange={(e) => setHfToken(e.target.value)}
                onBlur={() => hfToken && handleSaveToken(hfToken)}
                placeholder="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                style={{ width: '100%', paddingRight: '36px' }}
              />
              <button
                type="button"
                className="ai-icon-btn"
                style={{ position: 'absolute', right: '8px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
                onClick={() => setShowToken(!showToken)}
              >
                {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            <button
              className="btn-minimal"
              onClick={() => handleSaveToken(hfToken)}
              style={{ whiteSpace: 'nowrap', padding: '6px 14px' }}
            >
              <Check size={13} /> Save Token
            </button>
          </div>
          <div className="form-hint">
            Optional: Enables faster download bandwidth and access to gated models (e.g. Gemma, Llama). Saved securely in your local .env file.
          </div>
        </div>

        {/* 3. Downloaded Models List (Cards of the models) */}
        {downloadedModels.length > 0 && (
          <div className="form-group">
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <HardDrive size={13} /> Locally Downloaded Models
              </span>
              <span style={{ fontSize: '0.70rem', color: 'var(--accent-success)' }}>
                {downloadedModels.length} model(s) available in TeXa/models
              </span>
            </label>

            <div className="models-grid">
              {downloadedModels.map((model) => {
                const isSelected = selectedModel === model.id;
                return (
                  <div
                    key={model.id}
                    className={`model-card-small ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      setSelectedModel(model.id);
                    }}
                  >
                    <div className="model-card-top">
                      <span className="param-badge">{model.param_display || 'AI Model'}</span>
                      <span className="status-badge downloaded" title="Available in TeXa/models">
                        <Check size={11} /> Ready
                      </span>
                    </div>
                    <div className="model-card-title">{model.name}</div>
                    <div className="model-card-desc">{model.id}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 4. Custom Hugging Face Model Input */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Cpu size={13} /> Hugging Face Model ID
          </label>

          <div className="browse-dir-row">
            <input
              type="text"
              className="form-input"
              value={customModelId}
              onChange={(e) => {
                setCustomModelId(e.target.value);
                if (e.target.value.trim()) {
                  setSelectedModel(e.target.value);
                }
              }}
              placeholder="e.g. google/gemma-3-1b-it, meta-llama/Llama-3.2-1B-Instruct, Qwen/Qwen2.5-Coder-3B-Instruct"
              style={{ flex: 1 }}
            />
            <button
              className="btn-minimal btn-primary"
              onClick={() => handleDownloadModel(customModelId)}
              style={{ whiteSpace: 'nowrap', padding: '6px 14px' }}
            >
              <Download size={13} /> Download Model
            </button>
          </div>
          <div className="form-hint">
            Enter any standard Hugging Face model repository ID. TeXa will safely download weights and tokenizer into your local models folder.
          </div>
        </div>

        {/* 5. Persistent Coffee Download Message & Static Spinner (No Progress Bar) */}
        {aiStatus.status === 'downloading' && (
          <div className="download-spinner-container">
            <RefreshCw size={16} className="animate-spin download-spinner-icon" />
            <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>
              Downloading {effectiveModel || 'model'}... Meanwhile, sit back, relax, and grab a coffee ☕!
            </span>
          </div>
        )}

        {/* 6. Launch Editor Action Button */}
        <div className="setup-footer">
          <button
            className="btn-minimal btn-primary launch-btn"
            onClick={handleLaunch}
            disabled={!effectiveModel}
            style={{ opacity: effectiveModel ? 1 : 0.6 }}
          >
            Launch TeXa Editor <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}



