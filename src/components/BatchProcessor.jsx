/**
 * BatchProcessor.jsx — Parametric AI
 * Evaluator Batch Processor with Park UI Design System Aesthetics.
 * Drag-and-drop CSV/Excel upload → autonomous web sourcing + Gemini extraction → 252-column Unilog Excel download.
 */

import React, { useState, useRef, useCallback } from 'react';
import {
  Upload,
  FileSpreadsheet,
  CheckCircle,
  Loader2,
  Download,
  XCircle,
  AlertTriangle,
  Zap,
  Globe,
  Brain,
  Table2,
  FileDown,
  RotateCcw,
  Info,
  Layers,
  Sparkles
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

// ── Pipeline stages shown during processing ──────────────────────────────────
const PIPELINE_STAGES = [
  { icon: Globe,           label: 'DuckDuckGo Autonomous Search', desc: 'Sourcing OEM manufacturer domain URLs' },
  { icon: Upload,          label: 'Scraping Specification Text',  desc: 'Extracting product HTML, PDFs & tables' },
  { icon: Brain,           label: 'Gemini Flash LLM Extraction',  desc: 'Parsing 50-slot key/value/UOM triplets' },
  { icon: Table2,          label: 'Mapping 252-Column Schema',    desc: 'Formatting to Unilog master delivery format' },
  { icon: FileSpreadsheet, label: 'Generating Excel Workbook',    desc: 'Serializing openpyxl production deliverable' },
];

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileChip({ file, onRemove }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '12px',
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)', padding: '10px 14px',
    }}>
      <div style={{ background: 'rgba(0, 242, 254, 0.12)', padding: '8px', borderRadius: 'var(--radius-sm)' }}>
        <FileSpreadsheet size={20} color="var(--accent-cyan)" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {file.name}
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{formatBytes(file.size)}</div>
      </div>
      {onRemove && (
        <button
          onClick={onRemove}
          className="park-btn park-btn-ghost park-btn-icon"
          title="Remove file"
        >
          <XCircle size={18} color="var(--text-muted)" />
        </button>
      )}
    </div>
  );
}

function StageTimeline({ activeStage, done }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {PIPELINE_STAGES.map((stage, idx) => {
        const StageIcon = stage.icon;
        const isActive  = activeStage === idx && !done;
        const isPast    = done || activeStage > idx;
        const isFuture  = !done && activeStage < idx;
        return (
          <div
            key={idx}
            style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '10px 12px', borderRadius: 'var(--radius-md)',
              background: isActive ? 'rgba(0, 242, 254, 0.06)' : isPast ? 'rgba(16, 185, 129, 0.05)' : 'var(--bg-subtle)',
              border: `1px solid ${isActive ? 'rgba(0, 242, 254, 0.3)' : isPast ? 'rgba(16, 185, 129, 0.2)' : 'var(--border-default)'}`,
              transition: 'all 0.3s ease',
              opacity: isFuture ? 0.45 : 1,
            }}
          >
            <div style={{
              width: '32px', height: '32px', borderRadius: 'var(--radius-sm)', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: isActive ? 'rgba(0, 242, 254, 0.15)' : isPast ? 'rgba(16, 185, 129, 0.15)' : 'var(--bg-surface)',
            }}>
              {isActive ? (
                <Loader2 size={16} color="var(--accent-cyan)" className="animate-spin" />
              ) : isPast ? (
                <CheckCircle size={16} color="var(--accent-emerald)" />
              ) : (
                <StageIcon size={16} color="var(--text-muted)" />
              )}
            </div>

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: isActive ? 'var(--accent-cyan)' : isPast ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                {stage.label}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{stage.desc}</div>
            </div>

            <span className={`park-badge ${isActive ? 'park-badge-cyan' : isPast ? 'park-badge-emerald' : 'park-badge-neutral'}`} style={{ fontSize: '0.62rem' }}>
              <span className="badge-dot" />
              {isActive ? 'ACTIVE' : isPast ? 'DONE' : 'WAITING'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function BatchProcessor() {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStage, setActiveStage] = useState(-1);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [rowCount, setRowCount] = useState(null);
  const [error, setError] = useState('');
  const [elapsedSecs, setElapsedSecs] = useState(0);

  const fileInputRef  = useRef(null);
  const timerRef      = useRef(null);
  const stageTimerRef = useRef(null);

  const acceptFile = useCallback((f) => {
    if (!f) return;
    const ext = f.name.split('.').pop().toLowerCase();
    if (!['csv', 'xls', 'xlsx'].includes(ext)) {
      setError('Invalid file format. Please upload a .csv or .xlsx file.');
      return;
    }
    setFile(f);
    setDownloadUrl(null);
    setError('');
    setActiveStage(-1);
    setElapsedSecs(0);
  }, []);

  const handleInputChange = (e) => {
    if (e.target.files?.[0]) acceptFile(e.target.files[0]);
  };

  const handleDragOver  = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop      = (e) => {
    e.preventDefault();
    setIsDragging(false);
    acceptFile(e.dataTransfer.files?.[0]);
  };

  const startStageTicker = () => {
    let stage = 0;
    setActiveStage(0);
    stageTimerRef.current = setInterval(() => {
      stage += 1;
      if (stage < PIPELINE_STAGES.length) {
        setActiveStage(stage);
      }
    }, 4000);
  };

  const stopStageTicker = () => {
    clearInterval(stageTimerRef.current);
    clearInterval(timerRef.current);
  };

  const handleProcess = async () => {
    if (!file || isProcessing) return;

    setIsProcessing(true);
    setDownloadUrl(null);
    setError('');
    setRowCount(null);
    setElapsedSecs(0);

    const start = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedSecs(Math.floor((Date.now() - start) / 1000));
    }, 1000);

    startStageTicker();

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/api/process_evaluator_dataset`, {
        method: 'POST',
        body: formData,
      });

      stopStageTicker();

      if (!response.ok) {
        let detail = 'Batch execution error. Please check backend console.';
        try {
          const errData = await response.json();
          detail = errData.detail || detail;
        } catch (_) {}
        throw new Error(detail);
      }

      const rowCountHeader = response.headers.get('X-Row-Count');
      if (rowCountHeader) setRowCount(parseInt(rowCountHeader, 10));

      setActiveStage(PIPELINE_STAGES.length);

      const blob = await response.blob();
      const url  = window.URL.createObjectURL(blob);
      setDownloadUrl(url);

    } catch (err) {
      stopStageTicker();
      setActiveStage(-1);
      setError(err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    stopStageTicker();
    setFile(null);
    setDownloadUrl(null);
    setError('');
    setActiveStage(-1);
    setElapsedSecs(0);
    setIsProcessing(false);
    setRowCount(null);
  };

  const isDone = !isProcessing && downloadUrl;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* Header Banner */}
      <div className="park-card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '20px', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', padding: '6px', borderRadius: 'var(--radius-md)', display: 'flex' }}>
                <Zap size={18} color="var(--accent-cyan)" />
              </div>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 800, letterSpacing: '-0.3px', color: 'var(--text-primary)' }}>
                Evaluator Batch Processor
              </h2>
              <span className="park-badge park-badge-cyan">
                <span className="badge-dot" />
                Autonomous Engine
              </span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', maxWidth: '700px', lineHeight: 1.6 }}>
              Upload any evaluation CSV or Excel file containing manufacturer part numbers. The engine autonomously navigates manufacturer websites, extracts specification triplets with Gemini Flash, and formats results into the complete <strong>252-Column Unilog Master Schema</strong>.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', background: 'var(--bg-subtle)', padding: '12px 16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
            {[
              ['Required Header', 'Mfg_Part_Num'],
              ['Optional Header', 'Part_Manuf'],
              ['Delivery Output', '252-Column .xlsx'],
            ].map(([label, val]) => (
              <div key={label} style={{ display: 'flex', gap: '12px', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{label}:</span>
                <code style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>{val}</code>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: '20px', alignItems: 'start' }}>

        {/* Left Column: Upload & Pipeline Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {!file && !isProcessing && (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${isDragging ? 'var(--accent-cyan)' : 'var(--border-default)'}`,
                borderRadius: 'var(--radius-lg)',
                padding: '48px 24px',
                textAlign: 'center',
                cursor: 'pointer',
                background: isDragging ? 'rgba(0, 242, 254, 0.04)' : 'var(--bg-surface)',
                transition: 'all 0.2s ease',
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xls,.xlsx"
                onChange={handleInputChange}
                style={{ display: 'none' }}
              />
              <div style={{
                width: '54px', height: '54px', borderRadius: 'var(--radius-md)',
                background: isDragging ? 'rgba(0, 242, 254, 0.15)' : 'var(--bg-subtle)',
                border: `1px solid ${isDragging ? 'rgba(0, 242, 254, 0.3)' : 'var(--border-default)'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                margin: '0 auto 14px',
              }}>
                <Upload size={24} color={isDragging ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
              </div>
              <p style={{ fontSize: '0.98rem', fontWeight: 700, color: isDragging ? 'var(--accent-cyan)' : 'var(--text-primary)', marginBottom: '4px' }}>
                {isDragging ? 'Drop evaluator dataset here' : 'Click or Drag & Drop Evaluator CSV/Excel'}
              </p>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Supports standard <code style={{ color: 'var(--text-secondary)' }}>.csv</code>, <code style={{ color: 'var(--text-secondary)' }}>.xls</code>, and <code style={{ color: 'var(--text-secondary)' }}>.xlsx</code> files
              </p>
            </div>
          )}

          {file && (
            <FileChip
              file={file}
              onRemove={isProcessing ? undefined : handleReset}
            />
          )}

          {error && (
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: '12px',
              padding: '12px 16px', borderRadius: 'var(--radius-md)',
              background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.3)',
            }}>
              <AlertTriangle size={18} color="var(--accent-rose)" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--accent-rose)' }}>Pipeline Error</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '2px' }}>{error}</div>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              onClick={handleProcess}
              disabled={!file || isProcessing}
              className="park-btn park-btn-accent"
              style={{ flex: 1, padding: '10px 20px' }}
            >
              {isProcessing ? (
                <><Loader2 size={16} className="animate-spin" /> Running Pipeline ({elapsedSecs}s)...</>
              ) : (
                <><Zap size={16} /> Run Autonomous Batch Pipeline</>
              )}
            </button>

            {(file || downloadUrl || error) && !isProcessing && (
              <button
                onClick={handleReset}
                className="park-btn park-btn-secondary"
                style={{ padding: '10px 16px' }}
              >
                <RotateCcw size={15} /> Reset
              </button>
            )}
          </div>

          {/* Success Download Card */}
          {isDone && (
            <div className="park-card" style={{ padding: '20px', border: '1px solid rgba(16,185,129,0.35)', background: 'rgba(16, 185, 129, 0.04)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                <div style={{ background: 'rgba(16, 185, 129, 0.15)', padding: '8px', borderRadius: 'var(--radius-sm)' }}>
                  <CheckCircle size={20} color="var(--accent-emerald)" />
                </div>
                <div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
                    252-Column Unilog Workbook Generated!
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Completed in {elapsedSecs}s · Full attribute taxonomy normalized
                  </div>
                </div>
              </div>

              <a
                href={downloadUrl}
                download="Parametric_AI_Delivery.xlsx"
                className="park-btn park-btn-primary"
                style={{
                  width: '100%',
                  background: 'var(--accent-emerald)',
                  color: '#000',
                  textDecoration: 'none',
                  padding: '10px 16px',
                  fontWeight: 800,
                }}
              >
                <FileDown size={18} />
                Download 252-Column Excel (.xlsx)
              </a>
            </div>
          )}
        </div>

        {/* Right Column: Pipeline Stage Timeline */}
        <div className="park-card" style={{ padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Brain size={16} color="var(--accent-cyan)" />
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                Pipeline Execution Steps
              </span>
            </div>
            {isProcessing && (
              <span style={{ fontSize: '0.72rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                {elapsedSecs}s
              </span>
            )}
          </div>

          <StageTimeline activeStage={activeStage} done={isDone} />

          {!isProcessing && !isDone && (
            <div style={{
              marginTop: '14px', padding: '10px 12px', borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-subtle)', border: '1px solid var(--border-default)',
              display: 'flex', gap: '8px', alignItems: 'flex-start',
            }}>
              <Info size={14} color="var(--accent-amber)" style={{ flexShrink: 0, marginTop: '1px' }} />
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                Rows are processed through live web discovery and Gemini Flash attribute extraction.
              </p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
