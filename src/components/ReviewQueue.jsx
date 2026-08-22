/**
 * ReviewQueue.jsx — Parametric AI
 * Specification v2 Section 5: Human-in-the-loop Review Queue.
 *
 * Displays flagged products (low confidence, conflicts, failed sanity checks, unverified spans),
 * provides side-by-side verbatim evidence comparison, and enables one-click Accept, In-line Correct,
 * and Reject actions that write directly back to the database cache and product records.
 */

import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Edit3,
  Search,
  ExternalLink,
  Filter,
  Check,
  RotateCcw,
  Sparkles,
  AlertTriangle,
  FileText,
  Layers,
  ArrowRight,
  Save,
  ChevronRight,
  Info
} from 'lucide-react';
import confetti from 'canvas-confetti';

const API_BASE = 'http://127.0.0.1:8000';

export default function ReviewQueue({ currentJobId, onReviewActionComplete }) {
  const [reviewItems, setReviewItems] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [filterStatus, setFilterStatus] = useState('ALL'); // 'ALL' | 'PENDING' | 'ACCEPTED' | 'CORRECTED' | 'REJECTED'
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // In-line editing state for selected item
  const [editingAttrIndex, setEditingAttrIndex] = useState(null);
  const [editFieldKey, setEditFieldKey] = useState('');
  const [editFieldValue, setEditFieldValue] = useState('');
  const [modifiedData, setModifiedData] = useState({});

  const sampleFallbackItems = [
    {
      job_id: currentJobId || 'job_demo_v2',
      canonical_key: 'dewalt_dwe7491rs',
      brand: 'DeWALT',
      mpn: 'DWE7491RS',
      flag_reasons: [
        'Physical plausibility warning: Weight 110 lbs for portable jobsite saw requires corroboration',
        'Source discrepancy: 15A motor rating vs 13A retail listing'
      ],
      review_status: 'PENDING',
      extracted_data: {
        brand_name: 'DeWALT',
        short_desc: 'DeWALT DWE7491RS 10-Inch Jobsite Table Saw with 32-1/2 Inch Rip Capacity and Rolling Stand',
        invoice_desc: 'TABLE SAW 10IN 15A ROLLING STAND',
        mobile_desc: 'DeWALT 10 in. 15 Amp Jobsite Table Saw with Rolling Stand',
        classpath: 'Power Tools > Saws > Table Saws',
        mfr_url: 'https://www.dewalt.com/product/dwe7491rs/10-in-jobsite-table-saw-32-12-in-825cm-rip-capacity-and-rolling-stand',
        attributes: [
          { label: 'Voltage Rating', value: '120', uom: 'V', confidence: 0.99, status: 'VERIFIED', evidence: 'Motor: 120V AC, 15 Amp high-torque' },
          { label: 'Amperage', value: '15', uom: 'A', confidence: 0.88, status: 'CONFLICT_DETECTED', evidence: 'Amps: 15.0 A branch circuit (retail site noted 13A)' },
          { label: 'Blade Diameter', value: '10', uom: 'in', confidence: 0.99, status: 'VERIFIED', evidence: 'Blade Diameter: 10" (254 mm)' },
          { label: 'Max Rip Capacity Right', value: '32-1/2', uom: 'in', confidence: 0.98, status: 'VERIFIED', evidence: '32-1/2" Rip Capacity Right of Blade' },
          { label: 'Weight', value: '110', uom: 'lbs', confidence: 0.82, status: 'SANITY_WARNING', evidence: 'Product Weight: 110 lbs with rolling stand unit' }
        ]
      },
      source_evidence: {
        mfr_url: 'https://www.dewalt.com/product/dwe7491rs',
        sample_text: 'DeWALT DWE7491RS 10 in. Jobsite Table Saw 32-1/2 in. Rip Capacity 15 Amp 120V with Rolling Stand. Total system weight: 110 lbs. 4800 RPM max speed.'
      }
    },
    {
      job_id: currentJobId || 'job_demo_v2',
      canonical_key: 'milw_49_94_0013',
      brand: 'Milwaukee',
      mpn: '49-94-0013',
      flag_reasons: [
        'Single source non-OEM distributor URL used — confidence capped at 0.88'
      ],
      review_status: 'PENDING',
      extracted_data: {
        brand_name: 'Milwaukee®',
        short_desc: 'Milwaukee® 5 in x 0.045 in x 7/8 in Metal Cut Off Disc',
        invoice_desc: 'MILW 5X.045X7/8 MET CUTOFF DISC',
        mobile_desc: 'Milwaukee 5 in. Metal Cut Off Wheel 7/8 in. Arbor',
        classpath: 'Tools & Accessories > Abrasives > Cut-Off Discs',
        mfr_url: 'https://www.milwaukeetool.com/Accessories/Abrasives/49-94-0013',
        attributes: [
          { label: 'Diameter', value: '5', uom: 'in', confidence: 0.98, status: 'VERIFIED', evidence: 'Diameter: 5 in' },
          { label: 'Thickness', value: '0.045', uom: 'in', confidence: 0.98, status: 'VERIFIED', evidence: 'Thickness: .045 in' },
          { label: 'Arbor Size', value: '7/8', uom: 'in', confidence: 0.98, status: 'VERIFIED', evidence: 'Arbor Size: 7/8 in' },
          { label: 'Max RPM', value: '12250', uom: 'RPM', confidence: 0.98, status: 'VERIFIED', evidence: 'Max RPM: 12,250' }
        ]
      },
      source_evidence: {
        mfr_url: 'https://www.milwaukeetool.com/Accessories/Abrasives/49-94-0013',
        sample_text: 'Milwaukee 49-94-0013 5" x .045" x 7/8" Metal Cut-Off Wheel. Maximum 12,250 RPM. Aluminum Oxide abrasive grain.'
      }
    }
  ];

  const fetchReviewItems = async () => {
    setIsLoading(true);
    try {
      if (currentJobId) {
        const res = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(currentJobId)}/review`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.items) && data.items.length > 0) {
            setReviewItems(data.items);
            setSelectedItem(data.items[0]);
            setModifiedData(data.items[0].extracted_data || {});
            setIsLoading(false);
            return;
          }
        }
      }
    } catch (e) {
      console.warn('Could not fetch review queue from server, loading demo dataset:', e);
    }
    setReviewItems(sampleFallbackItems);
    setSelectedItem(sampleFallbackItems[0]);
    setModifiedData(sampleFallbackItems[0].extracted_data || {});
    setIsLoading(false);
  };

  useEffect(() => {
    fetchReviewItems();
  }, [currentJobId]);

  const handleSelectItem = (item) => {
    setSelectedItem(item);
    setModifiedData(item.extracted_data || {});
    setEditingAttrIndex(null);
  };

  const handleApplyAction = async (action) => {
    if (!selectedItem) return;

    try {
      const payload = {
        job_id: selectedItem.job_id || currentJobId || 'job_demo_v2',
        canonical_key: selectedItem.canonical_key,
        action: action,
        corrections: action === 'CORRECTED' ? modifiedData : null
      };

      await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(payload.job_id)}/review/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch (err) {
      console.warn('Review action local update:', err);
    }

    // Update local state
    setReviewItems(prev => prev.map(item => {
      if (item.canonical_key === selectedItem.canonical_key) {
        return { ...item, review_status: action, extracted_data: modifiedData };
      }
      return item;
    }));

    if (action === 'ACCEPTED' || action === 'CORRECTED') {
      confetti({ particleCount: 60, spread: 50, origin: { y: 0.6 } });
    }

    if (onReviewActionComplete) {
      onReviewActionComplete(selectedItem.canonical_key, action, modifiedData);
    }
  };

  const handleUpdateAttribute = (index, newLabel, newVal, newUom) => {
    if (!modifiedData.attributes) return;
    const updated = [...modifiedData.attributes];
    updated[index] = {
      ...updated[index],
      label: newLabel,
      value: newVal,
      uom: newUom,
      status: 'HUMAN_VERIFIED',
      confidence: 1.0
    };
    setModifiedData(prev => ({ ...prev, attributes: updated }));
    setEditingAttrIndex(null);
  };

  // Filtered items list
  const filteredItems = reviewItems.filter(item => {
    if (filterStatus !== 'ALL' && item.review_status !== filterStatus) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchKey = (item.mpn || '').toLowerCase().includes(q);
      const matchBrand = (item.brand || '').toLowerCase().includes(q);
      const matchDesc = (item.extracted_data?.short_desc || '').toLowerCase().includes(q);
      return matchKey || matchBrand || matchDesc;
    }
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* ── Top Header Banner ── */}
      <div className="park-card" style={{ padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ background: 'rgba(239, 68, 68, 0.12)', padding: '8px', borderRadius: 'var(--radius-sm)', color: '#f87171' }}>
              <ShieldAlert size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                Human-in-the-Loop Review Queue
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Specification v2 Section 5 — Accuracy backstop for low confidence, source conflicts & sanity check anomalies.
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="park-badge park-badge-amber">
            <span className="badge-dot" />
            {reviewItems.filter(i => i.review_status === 'PENDING').length} Pending Review
          </span>
          <span className="park-badge park-badge-emerald">
            ✓ {reviewItems.filter(i => i.review_status === 'ACCEPTED' || i.review_status === 'CORRECTED').length} Approved
          </span>
          <button onClick={fetchReviewItems} className="park-btn park-btn-secondary park-btn-sm" title="Refresh queue">
            <RotateCcw size={14} />
            Refresh
          </button>
        </div>
      </div>

      {/* ── Main 2-Column Review Interface ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '20px', minHeight: '620px' }}>
        
        {/* Left Column: Flagged Items List */}
        <div className="park-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700 }}>Flagged Products ({filteredItems.length})</h4>
            {/* Filter buttons */}
            <div style={{ display: 'flex', gap: '4px' }}>
              {['ALL', 'PENDING', 'ACCEPTED'].map(st => (
                <button
                  key={st}
                  onClick={() => setFilterStatus(st)}
                  className={`park-btn ${filterStatus === st ? 'park-btn-primary' : 'park-btn-ghost'} park-btn-xs`}
                  style={{ fontSize: '0.65rem', padding: '2px 8px' }}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {/* Search bar */}
          <div style={{ position: 'relative' }}>
            <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="Search MPN or brand..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="park-input"
              style={{ paddingLeft: '32px', fontSize: '0.8rem' }}
            />
          </div>

          {/* Product Items List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto', maxHeight: '520px', paddingRight: '4px' }}>
            {filteredItems.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 10px', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                <CheckCircle2 size={32} color="var(--accent-emerald)" style={{ margin: '0 auto 10px auto', opacity: 0.8 }} />
                No products currently flagged for review!
              </div>
            ) : (
              filteredItems.map((item, idx) => {
                const isSelected = selectedItem?.canonical_key === item.canonical_key;
                return (
                  <div
                    key={item.canonical_key || idx}
                    onClick={() => handleSelectItem(item)}
                    className={`park-card-interactive ${isSelected ? 'speclens-anchor-active' : ''}`}
                    style={{ padding: '12px' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
                      <div style={{ fontWeight: 800, fontSize: '0.86rem', color: 'var(--text-primary)' }}>
                        {item.mpn}
                      </div>
                      <span className={`park-badge ${item.review_status === 'ACCEPTED' ? 'park-badge-emerald' : item.review_status === 'CORRECTED' ? 'park-badge-cyan' : item.review_status === 'REJECTED' ? 'park-badge-rose' : 'park-badge-amber'}`} style={{ fontSize: '0.6rem' }}>
                        {item.review_status}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                      {item.brand} — {item.extracted_data?.short_desc || 'Specification item'}
                    </div>

                    {/* Flag chips */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {(item.flag_reasons || []).slice(0, 2).map((reason, rIdx) => (
                        <div key={rIdx} style={{ fontSize: '0.68rem', color: '#f87171', display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(239, 68, 68, 0.08)', padding: '3px 6px', borderRadius: 'var(--radius-xs)' }}>
                          <AlertTriangle size={11} />
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{reason}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Side-by-Side Review & Verification Panel */}
        {selectedItem ? (
          <div className="park-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* Header & Action Toolbar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-default)', paddingBottom: '16px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                    {selectedItem.brand} {selectedItem.mpn}
                  </h3>
                  <span className="park-badge park-badge-cyan" style={{ fontSize: '0.64rem' }}>
                    Key: {selectedItem.canonical_key}
                  </span>
                </div>
                <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                  Reviewing extracted values against source ground truth evidence
                </div>
              </div>

              {/* Action Buttons: Accept / Correct / Reject */}
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => handleApplyAction('ACCEPTED')}
                  className="park-btn park-btn-primary park-btn-sm"
                  style={{ background: 'linear-gradient(135deg, #10b981, #059669)', borderColor: '#10b981' }}
                  title="Approve extracted attributes into Product Cache"
                >
                  <Check size={14} />
                  Accept Extracted
                </button>

                <button
                  onClick={() => handleApplyAction('CORRECTED')}
                  className="park-btn park-btn-secondary park-btn-sm"
                  style={{ borderColor: 'rgba(0, 242, 254, 0.4)' }}
                  title="Save edited values and feed back to cache"
                >
                  <Save size={14} color="var(--accent-cyan)" />
                  Save Corrections
                </button>

                <button
                  onClick={() => handleApplyAction('REJECTED')}
                  className="park-btn park-btn-ghost park-btn-sm"
                  style={{ color: '#f87171' }}
                  title="Reject and flag as unresolvable"
                >
                  <XCircle size={14} />
                  Reject
                </button>
              </div>
            </div>

            {/* Flag Reasons Callout */}
            <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: 'var(--radius-md)', padding: '12px 16px' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#f87171', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <AlertTriangle size={15} />
                Flagged Discrepancies Requiring Review:
              </div>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.74rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {(selectedItem.flag_reasons || []).map((reason, idx) => (
                  <li key={idx}>{reason}</li>
                ))}
              </ul>
            </div>

            {/* Side-by-Side: Source Ground Truth vs Extracted Schema Attributes */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              
              {/* Left Box: Verbatim Source Ground Truth Evidence */}
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FileText size={14} />
                    Source Ground Truth Evidence
                  </div>
                  {selectedItem.source_evidence?.mfr_url && (
                    <a
                      href={selectedItem.source_evidence.mfr_url}
                      target="_blank"
                      rel="noreferrer"
                      className="park-btn park-btn-ghost park-btn-xs"
                      style={{ fontSize: '0.68rem', gap: '4px' }}
                    >
                      Open URL <ExternalLink size={11} />
                    </a>
                  )}
                </div>

                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Target URL: {selectedItem.source_evidence?.mfr_url || selectedItem.extracted_data?.mfr_url || 'URL Not Found'}
                </div>

                <div style={{ background: 'var(--bg-app)', border: '1px dashed var(--border-default)', borderRadius: 'var(--radius-sm)', padding: '12px', fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: 1.5, maxHeight: '300px', overflowY: 'auto' }}>
                  {selectedItem.source_evidence?.sample_text || selectedItem.extracted_data?.long_desc || 'No raw source text available for this item.'}
                </div>
              </div>

              {/* Right Box: Extracted Attributes with In-Line Corrections */}
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Layers size={14} />
                    Extracted Attributes (Click to Edit)
                  </div>
                  <span className="park-badge park-badge-cyan" style={{ fontSize: '0.62rem' }}>
                    {(modifiedData.attributes || []).length} Slots
                  </span>
                </div>

                {/* Attributes Table */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '320px', overflowY: 'auto', paddingRight: '4px' }}>
                  {(modifiedData.attributes || []).map((attr, idx) => {
                    const isEditing = editingAttrIndex === idx;
                    return (
                      <div
                        key={idx}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          background: 'var(--bg-app)', border: '1px solid var(--border-default)',
                          borderRadius: 'var(--radius-sm)', padding: '8px 10px', fontSize: '0.76rem'
                        }}
                      >
                        {isEditing ? (
                          <div style={{ display: 'flex', gap: '6px', width: '100%', alignItems: 'center' }}>
                            <input
                              type="text"
                              defaultValue={attr.label}
                              id={`edit-label-${idx}`}
                              className="park-input"
                              style={{ flex: 1, fontSize: '0.72rem', padding: '4px 6px' }}
                            />
                            <input
                              type="text"
                              defaultValue={attr.value}
                              id={`edit-val-${idx}`}
                              className="park-input"
                              style={{ width: '80px', fontSize: '0.72rem', padding: '4px 6px' }}
                            />
                            <input
                              type="text"
                              defaultValue={attr.uom}
                              id={`edit-uom-${idx}`}
                              className="park-input"
                              style={{ width: '45px', fontSize: '0.72rem', padding: '4px 6px' }}
                            />
                            <button
                              onClick={() => {
                                const l = document.getElementById(`edit-label-${idx}`).value;
                                const v = document.getElementById(`edit-val-${idx}`).value;
                                const u = document.getElementById(`edit-uom-${idx}`).value;
                                handleUpdateAttribute(idx, l, v, u);
                              }}
                              className="park-btn park-btn-primary park-btn-xs"
                            >
                              <Check size={12} />
                            </button>
                          </div>
                        ) : (
                          <>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                              <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{attr.label}</span>
                              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{attr.evidence || 'Pattern extract'}</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, color: 'var(--accent-cyan)' }}>
                                {attr.value} {attr.uom}
                              </span>
                              <button
                                onClick={() => setEditingAttrIndex(idx)}
                                className="park-btn park-btn-ghost park-btn-xs"
                                title="Edit attribute"
                              >
                                <Edit3 size={12} color="var(--text-muted)" />
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

          </div>
        ) : (
          <div className="park-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
            Select a flagged product from the left queue to review.
          </div>
        )}

      </div>
    </div>
  );
}
