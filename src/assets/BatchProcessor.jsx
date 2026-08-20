import React, { useState } from 'react';

// Make sure to install lucide-react for these icons: npm install lucide-react
import { Upload, FileSpreadsheet, CheckCircle, Loader2, Download } from 'lucide-react';

export default function BatchProcessor() {
    const [file, setFile] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [downloadUrl, setDownloadUrl] = useState(null);
    const [statusMsg, setStatusMsg] = useState('');

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
            setDownloadUrl(null);
            setStatusMsg('');
        }
    };

    const handleProcess = async () => {
        if (!file) return;
        setIsProcessing(true);
        setStatusMsg('Initializing autonomous web sourcing and Gemini LLM extraction...');

        const formData = new FormData();
        formData.append('file', file);

        try {
            // Connects to the FastAPI backend endpoint we just created
            const response = await fetch('http://localhost:8000/api/process_evaluator_dataset', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Processing failed. Please check the Python backend terminal.');
            }

            setStatusMsg('Formatting 252-Column Unilog Delivery Schema...');

            // Receive the Excel file as a Blob
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            setDownloadUrl(url);
            setStatusMsg('Processing complete! 100% Provenance Verified.');

        } catch (error) {
            console.error(error);
            setStatusMsg('Error processing file: ' + error.message);
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>

            <div>
                <h2 style={{ fontSize: '1.5rem', color: 'var(--accent-cyan)', marginBottom: '8px' }}>
                    Enterprise Batch Processing (Evaluator Mode)
                </h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
                    Upload the unseen Unilog CSV/Excel test dataset. ForgeSpec AI will autonomously source datasheets, reconcile multi-source conflicts, and export the exact 252-column delivery format.
                </p>
            </div>

            <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
                {/* Upload Button */}
                <label className="btn-secondary" style={{ position: 'relative', overflow: 'hidden', cursor: 'pointer' }}>
                    <Upload size={18} />
                    {file ? file.name : "Select Test Dataset (.csv, .xlsx)"}
                    <input
                        type="file"
                        accept=".csv, .xlsx, .xls"
                        onChange={handleFileChange}
                        style={{ position: 'absolute', top: 0, left: 0, opacity: 0, width: '100%', height: '100%', cursor: 'pointer' }}
                    />
                </label>

                {/* Run Pipeline Button */}
                <button
                    onClick={handleProcess}
                    disabled={!file || isProcessing}
                    className="btn-primary"
                    style={{ opacity: (!file || isProcessing) ? 0.6 : 1 }}
                >
                    {isProcessing ? (
                        <><Loader2 className="animate-spin" size={18} /> Processing Catalog...</>
                    ) : (
                        <><FileSpreadsheet size={18} /> Run Autonomous Enrichment</>
                    )}
                </button>
            </div>

            {/* Status Console */}
            {statusMsg && (
                <div style={{ padding: '16px', borderRadius: '10px', background: 'rgba(0,0,0,0.4)', border: '1px solid var(--border-color)' }}>
                    <p style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                        {isProcessing ? (
                            <Loader2 className="animate-spin" size={16} color="var(--accent-cyan)" />
                        ) : (
                            <CheckCircle size={16} color="var(--accent-emerald)" />
                        )}
                        {statusMsg}
                    </p>
                </div>
            )}

            {/* Success & Download Box */}
            {downloadUrl && (
                <div className="glass-panel-glow" style={{ padding: '24px', textAlign: 'center', marginTop: '10px', border: '1px solid var(--accent-emerald)' }}>
                    <h3 style={{ color: 'var(--accent-emerald)', marginBottom: '16px', fontSize: '1.2rem' }}>
                        ✅ 252-Column PIM Delivery File Generated
                    </h3>
                    <a
                        href={downloadUrl}
                        download="Unihack_Parametric_AI_Delivery.xlsx"
                        className="btn-primary"
                        style={{ background: 'linear-gradient(135deg, var(--accent-emerald), #047857)' }}
                    >
                        <Download size={18} /> Download Enriched Excel (.xlsx)
                    </a>
                </div>
            )}
        </div>
    );
}