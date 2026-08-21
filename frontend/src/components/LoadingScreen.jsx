import React from 'react';
import { Sparkles, Cpu, Folder, FileText, CheckCircle2, RefreshCw } from 'lucide-react';

/**
 * LoadingScreen Component
 * Displays a dedicated, animated loading state when launching TeXa editor,
 * showing model loading status, workspace initialization steps, and progress.
 * Once loading is finished, it transitions automatically without requiring manual button clicks.
 */
export default function LoadingScreen({
  modelId = 'Hugging Face Model',
  currentStep = 1,
  stepMessage = 'Initializing TeXa Workspace...',
  progress = 25
}) {
  const steps = [
    {
      id: 1,
      title: 'Verifying Workspace Configuration',
      desc: 'Validating FastAPI backend & workspace folder',
      icon: Folder
    },
    {
      id: 2,
      title: 'Activating AI Model Engine',
      desc: `Loading ${modelId || 'AI model'} weights into memory`,
      icon: Cpu
    },
    {
      id: 3,
      title: 'Preparing Monaco LaTeX Editor',
      desc: 'Mounting syntax highlighter & document buffer',
      icon: FileText
    },
    {
      id: 4,
      title: 'Initializing Live LaTeX Compiler',
      desc: 'Setting up continuous compilation pipeline',
      icon: Sparkles
    }
  ];

  return (
    <div className="texa-loading-screen">
      <div className="texa-loading-card">
        {/* Header with TeXa branding and glowing pulse icon */}
        <div className="loading-card-header">
          <div className="loading-logo-badge">
            <Sparkles size={24} className="loading-logo-icon" />
          </div>
          <h2 className="loading-card-title">Launching TeXa Workspace</h2>
          <p className="loading-card-subtitle">
            Preparing your minimalist LaTeX editing environment...
          </p>
        </div>

        {/* Active Model Indicator Tag */}
        <div className="loading-model-pill">
          <Cpu size={14} className="loading-model-icon" />
          <span className="loading-model-label">Active Model:</span>
          <span className="loading-model-name">{modelId || 'TeXa AI Engine'}</span>
        </div>

        {/* Dynamic Progress Bar */}
        <div className="loading-progress-container">
          <div className="loading-progress-info">
            <span className="loading-status-text">
              <RefreshCw size={12} className="animate-spin status-spin-icon" />
              {stepMessage}
            </span>
            <span className="loading-percent-text">{Math.round(progress)}%</span>
          </div>
          <div className="loading-progress-track">
            <div
              className="loading-progress-fill"
              style={{ width: `${Math.min(100, Math.max(5, progress))}%` }}
            />
          </div>
        </div>

        {/* Step-by-Step Checklist */}
        <div className="loading-steps-list">
          {steps.map((step) => {
            const isCompleted = currentStep > step.id;
            const isCurrent = currentStep === step.id;
            const Icon = step.icon;

            return (
              <div
                key={step.id}
                className={`loading-step-item ${isCompleted ? 'completed' : ''} ${isCurrent ? 'active' : ''}`}
              >
                <div className="step-icon-wrapper">
                  {isCompleted ? (
                    <CheckCircle2 size={16} className="step-done-icon" />
                  ) : isCurrent ? (
                    <RefreshCw size={14} className="animate-spin step-active-icon" />
                  ) : (
                    <Icon size={14} className="step-pending-icon" />
                  )}
                </div>
                <div className="step-details">
                  <div className="step-title-text">{step.title}</div>
                  <div className="step-desc-text">{step.desc}</div>
                </div>
                {isCompleted && <span className="step-status-tag">Ready</span>}
                {isCurrent && <span className="step-status-tag active">Loading...</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

