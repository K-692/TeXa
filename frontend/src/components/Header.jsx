import React from 'react';
import { Play, Save, Home, Sun, Moon, Bot, RefreshCw, Zap } from 'lucide-react';
import texaLogo from '../assets/logo.png';

export default function Header({
  currentPage,
  onCompile,
  isCompiling,
  errorCount,
  onSaveAll,
  onRequestHome,
  theme,
  toggleTheme,
  isAiBoxOpen,
  toggleAiBox,
  config,
  updateConfig
}) {
  const isAutoCompile = config?.auto_validate ?? true;

  const handleToggleAutoCompile = () => {
    const nextState = !isAutoCompile;
    if (updateConfig) {
      updateConfig({ auto_validate: nextState });
    }
    if (nextState && onCompile) {
      onCompile();
    }
  };


  return (
    <header className="top-header">
      <div
        className="brand-title"
        onClick={currentPage === 'editor' ? onRequestHome : undefined}
        style={{ cursor: currentPage === 'editor' ? 'pointer' : 'default' }}
        title={currentPage === 'editor' ? 'Return to Home / Setup' : undefined}
      >
        <img src={texaLogo} alt="TeXa" className="brand-logo" />
        <span className="brand-subtitle">Text to LaTeX Assistant</span>
      </div>

      <div className="header-actions">
        {currentPage === 'editor' && (
          <>
            {/* FIRST TAB BUTTON: AI ASSISTANT OVERLAY */}
            <button
              className={`btn-minimal ${isAiBoxOpen ? 'btn-active-ai' : ''}`}
              onClick={toggleAiBox}
              title="Toggle AI Assistant Box"
              style={{ fontWeight: 600 }}
            >
              <Bot size={13} />
              {isAiBoxOpen ? 'AI Assistant' : 'AI Assistant'}
            </button>

            {/* INTERACTIVE AUTO-COMPILE TOGGLE SWITCH */}
            <div
              className="auto-compile-toggle-wrapper"
              onClick={handleToggleAutoCompile}
              title="Toggle automatic compilation on text changes"
            >
              <span className="auto-compile-text">
                <Zap size={11} style={{ color: isAutoCompile ? 'var(--accent-primary)' : 'var(--text-subtle)' }} />
                Auto-Compile
              </span>
              <div className={`switch-track ${isAutoCompile ? 'on' : 'off'}`}>
                <div className="switch-thumb" />
              </div>
            </div>

            <button
              className="btn-minimal"
              onClick={onSaveAll}
              title="Save all changes to disk"
            >
              <Save size={13} />
              Save
            </button>

            <button
              className="btn-minimal btn-primary"
              onClick={onCompile}
              disabled={isCompiling}
              title="Trigger Manual LaTeX Compilation"
            >
              {isCompiling ? <RefreshCw className="animate-spin" size={13} /> : <Play size={13} />}
              Compile
            </button>

            <button
              className="btn-minimal"
              onClick={onRequestHome}
              title="Return to Home / Setup Page"
            >
              <Home size={13} />
              Home
            </button>

          </>
        )}

        <button
          className="btn-minimal"
          onClick={toggleTheme}
          title="Toggle Minimal Dark/Light Theme"
        >
          {theme === 'dark' ? <Sun size={13} /> : <Moon size={13} />}
        </button>
      </div>
    </header>
  );
}



