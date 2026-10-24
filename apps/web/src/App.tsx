import React, { useState, useEffect } from 'react';
import { api } from './api/client';
import { Job, SystemInfo, SystemStatus, Asset, InspectionResult, UploadResponse, JobStatus } from './types';
import {
  Activity,
  CheckCircle2,
  Clock,
  HardDrive,
  Layers,
  Play,
  RefreshCw,
  Server,
  StopCircle,
  XCircle,
  Database,
  Cpu,
  Upload,
  Download,
  Trash2,
  FileVideo,
  Search,
  ExternalLink,
  ShieldCheck,
  ShieldAlert
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'enqueue' | 'library'>('enqueue');
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Enqueue mode: 'url', 'upload', 'synthetic'
  const [sourceMode, setSourceMode] = useState<'url' | 'upload' | 'synthetic'>('url');

  // URL state & inspection
  const [sourceUrl, setSourceUrl] = useState<string>('');
  const [inspecting, setInspecting] = useState<boolean>(false);
  const [inspectionResult, setInspectionResult] = useState<InspectionResult | null>(null);

  // File Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadedMeta, setUploadedMeta] = useState<UploadResponse | null>(null);

  // Common output configuration
  const [outputMode, setOutputMode] = useState<string>('video');
  const [container, setContainer] = useState<string>('mp4');
  const [rightsConfirmed, setRightsConfirmed] = useState<boolean>(true);

  const fetchData = async () => {
    try {
      const [info, status, jobsList, assetsList] = await Promise.all([
        api.getSystemInfo().catch(() => null),
        api.getSystemStatus().catch(() => null),
        api.listJobs().catch(() => []),
        api.listAssets().catch(() => []),
      ]);
      if (info) setSystemInfo(info);
      if (status) setSystemStatus(status);
      setJobs(jobsList);
      setAssets(assetsList);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Error fetching system data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleInspectUrl = async () => {
    if (!sourceUrl.trim()) return;
    setInspecting(true);
    setError(null);
    try {
      const result = await api.inspectSource(sourceUrl);
      setInspectionResult(result);
    } catch (err: any) {
      setError(err.message || 'Inspection failed');
      setInspectionResult(null);
    } finally {
      setInspecting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadFile(file);
    setUploading(true);
    setError(null);
    try {
      const res = await api.uploadFile(file);
      setUploadedMeta(res);
    } catch (err: any) {
      setError(err.message || 'Upload failed');
      setUploadFile(null);
      setUploadedMeta(null);
    } finally {
      setUploading(false);
    }
  };

  const handleCreateJob = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      let payload: any;
      if (sourceMode === 'synthetic') {
        payload = {
          source: { type: 'synthetic', url: 'test://synthetic-job' },
          output: { mode: outputMode, container },
          rightsConfirmed: true,
        };
      } else if (sourceMode === 'upload') {
        if (!uploadedMeta) {
          throw new Error('Please select and upload a valid media file first.');
        }
        payload = {
          source: { type: 'upload', uploadId: uploadedMeta.uploadId },
          output: { mode: outputMode, container },
          rightsConfirmed: true,
        };
      } else {
        if (!sourceUrl.trim()) {
          throw new Error('Please enter a valid media source URL.');
        }
        payload = {
          source: { type: 'url', url: sourceUrl },
          output: { mode: outputMode, container },
          rightsConfirmed,
        };
      }

      await api.createJob(payload);
      if (sourceMode === 'url') {
        setSourceUrl('');
        setInspectionResult(null);
      } else if (sourceMode === 'upload') {
        setUploadFile(null);
        setUploadedMeta(null);
      }
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to dispatch job');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    try {
      await api.cancelJob(jobId);
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to cancel job');
    }
  };

  const handleDeleteAsset = async (assetId: string) => {
    if (!confirm('Are you sure you want to permanently delete this media file?')) return;
    try {
      await api.deleteAsset(assetId);
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to delete asset');
    }
  };

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDuration = (seconds?: number | null) => {
    if (!seconds) return '-';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const getStatusBadge = (status: JobStatus) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" /> Completed
          </span>
        );
      case 'processing':
      case 'inspecting':
      case 'finalizing':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> {status}
          </span>
        );
      case 'queued':
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="w-3.5 h-3.5" /> {status}
          </span>
        );
      case 'cancelled':
      case 'cancel_requested':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
            <StopCircle className="w-3.5 h-3.5" /> {status}
          </span>
        );
      case 'failed':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <XCircle className="w-3.5 h-3.5" /> {status}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-indigo-600 p-2 rounded-lg text-white">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white">Local Media Downloader</h1>
              <p className="text-xs text-slate-400">Self-Hosted Acquisition & Conversion Pipeline</p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <nav className="flex gap-1 bg-slate-950/60 p-1 rounded-lg border border-slate-800">
              <button
                onClick={() => setActiveTab('enqueue')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                  activeTab === 'enqueue'
                    ? 'bg-indigo-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Enqueue Media
              </button>
              <button
                onClick={() => setActiveTab('library')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center gap-1.5 ${
                  activeTab === 'library'
                    ? 'bg-indigo-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Media Library
                {assets.length > 0 && (
                  <span className="bg-indigo-900 text-indigo-300 px-1.5 py-0.2 rounded-full text-[10px]">
                    {assets.length}
                  </span>
                )}
              </button>
            </nav>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-xs">
                <span className={`w-2.5 h-2.5 rounded-full ${systemStatus?.databaseConnected && systemStatus?.redisConnected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                <span className="text-slate-300 font-medium">
                  {systemStatus?.databaseConnected && systemStatus?.redisConnected ? 'Operational' : 'Degraded'}
                </span>
              </div>
              <button
                onClick={fetchData}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
                title="Refresh"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 space-y-8 w-full">
        {error && (
          <div className="p-4 rounded-lg bg-rose-950/50 border border-rose-800 text-rose-300 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-rose-400 hover:text-white">&times;</button>
          </div>
        )}

        {/* System Vitals Overview */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl flex items-center gap-4">
            <div className="p-3 bg-indigo-500/10 text-indigo-400 rounded-lg">
              <Database className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">PostgreSQL</p>
              <p className="text-sm font-semibold text-slate-200">
                {systemStatus?.databaseConnected ? 'Connected (Healthy)' : 'Offline'}
              </p>
            </div>
          </div>

          <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl flex items-center gap-4">
            <div className="p-3 bg-red-500/10 text-red-400 rounded-lg">
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Redis Queue</p>
              <p className="text-sm font-semibold text-slate-200">
                {systemStatus?.redisConnected ? `Queue Depth: ${systemStatus.queueDepth}` : 'Offline'}
              </p>
            </div>
          </div>

          <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl flex items-center gap-4">
            <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-lg">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Workers</p>
              <p className="text-sm font-semibold text-slate-200">
                {systemStatus ? `${systemStatus.workerCount} online (${systemStatus.activeJobs} busy)` : '-'}
              </p>
            </div>
          </div>

          <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl flex items-center gap-4">
            <div className="p-3 bg-amber-500/10 text-amber-400 rounded-lg">
              <HardDrive className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Free Storage</p>
              <p className="text-sm font-semibold text-slate-200">
                {systemStatus ? formatBytes(systemStatus.diskFreeBytes) : '-'}
              </p>
            </div>
          </div>
        </section>

        {activeTab === 'enqueue' ? (
          <>
            {/* Job Enqueue Section */}
            <section className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
              <div className="flex gap-4 border-b border-slate-800 pb-3 mb-5">
                <button
                  type="button"
                  onClick={() => setSourceMode('url')}
                  className={`text-sm font-medium pb-2 border-b-2 transition flex items-center gap-1.5 ${
                    sourceMode === 'url'
                      ? 'border-indigo-500 text-indigo-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <ExternalLink className="w-4 h-4" />
                  Remote URL (Phase 3)
                </button>
                <button
                  type="button"
                  onClick={() => setSourceMode('upload')}
                  className={`text-sm font-medium pb-2 border-b-2 transition flex items-center gap-1.5 ${
                    sourceMode === 'upload'
                      ? 'border-indigo-500 text-indigo-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Upload className="w-4 h-4" />
                  Upload Local File (Phase 2)
                </button>
                <button
                  type="button"
                  onClick={() => setSourceMode('synthetic')}
                  className={`text-sm font-medium pb-2 border-b-2 transition flex items-center gap-1.5 ${
                    sourceMode === 'synthetic'
                      ? 'border-indigo-500 text-indigo-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Activity className="w-4 h-4" />
                  Synthetic Test (Phase 1)
                </button>
              </div>

              <form onSubmit={handleCreateJob} className="space-y-5">
                {sourceMode === 'url' && (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <label className="text-xs text-slate-300 font-medium">Source Media URL</label>
                      <div className="flex gap-2">
                        <input
                          type="url"
                          placeholder="https://source.example/media/sample.mp4 or YouTube URL"
                          value={sourceUrl}
                          onChange={(e) => setSourceUrl(e.target.value)}
                          required
                          className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                        />
                        <button
                          type="button"
                          onClick={handleInspectUrl}
                          disabled={inspecting || !sourceUrl.trim()}
                          className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 px-4 py-2 rounded-lg text-xs font-medium transition flex items-center gap-1.5"
                        >
                          {inspecting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                          Inspect
                        </button>
                      </div>
                    </div>

                    {/* Inspection Result Preview */}
                    {inspectionResult && (
                      <div className={`p-4 rounded-xl border ${inspectionResult.policy.decision === 'allowed' ? 'bg-slate-900/60 border-slate-700' : 'bg-rose-950/20 border-rose-800/60'}`}>
                        <div className="flex items-start justify-between">
                          <div>
                            <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-400">
                              Source: {inspectionResult.source}
                            </span>
                            <h3 className="text-sm font-bold text-white mt-0.5">
                              {inspectionResult.metadata.title}
                            </h3>
                            {inspectionResult.metadata.creatorLabel && (
                              <p className="text-xs text-slate-400">Creator: {inspectionResult.metadata.creatorLabel}</p>
                            )}
                            {inspectionResult.metadata.durationSeconds && (
                              <p className="text-xs text-slate-400">Duration: {formatDuration(inspectionResult.metadata.durationSeconds)}</p>
                            )}
                          </div>

                          <div>
                            {inspectionResult.policy.decision === 'allowed' ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                <ShieldCheck className="w-3.5 h-3.5" /> Policy: Allowed
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                <ShieldAlert className="w-3.5 h-3.5" /> {inspectionResult.policy.reasonCode}
                              </span>
                            )}
                          </div>
                        </div>

                        {inspectionResult.policy.message && (
                          <p className="text-xs text-slate-400 mt-2 border-t border-slate-800/80 pt-2">
                            {inspectionResult.policy.message}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {sourceMode === 'upload' && (
                  <div className="space-y-4">
                    <label className="text-xs text-slate-300 font-medium">Select Local Media File</label>
                    <div className="border-2 border-dashed border-slate-700 hover:border-slate-500 rounded-xl p-6 text-center bg-slate-950/40">
                      <input
                        type="file"
                        id="media-file-input"
                        onChange={handleFileUpload}
                        accept="video/*,audio/*"
                        className="hidden"
                      />
                      <label htmlFor="media-file-input" className="cursor-pointer flex flex-col items-center">
                        <Upload className="w-8 h-8 text-indigo-400 mb-2" />
                        <span className="text-sm font-medium text-slate-200">
                          {uploadFile ? uploadFile.name : 'Click to select media file'}
                        </span>
                        <span className="text-xs text-slate-500 mt-1">
                          Max upload size: {systemInfo ? formatBytes(systemInfo.capabilities.maxUploadBytes) : '2 GB'}
                        </span>
                      </label>
                    </div>

                    {uploading && (
                      <div className="flex items-center gap-2 text-xs text-indigo-400">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Streaming upload to staging and running ffprobe validation...</span>
                      </div>
                    )}

                    {uploadedMeta && (
                      <div className="p-3 bg-emerald-950/20 border border-emerald-800/40 rounded-lg flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2 text-emerald-300 font-medium">
                          <CheckCircle2 className="w-4 h-4" />
                          <span>Uploaded: {uploadedMeta.originalFilename} ({formatBytes(uploadedMeta.sizeBytes)})</span>
                        </div>
                        <span className="text-emerald-400 uppercase font-semibold text-[10px]">
                          Format: {uploadedMeta.format || 'Media'}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {sourceMode === 'synthetic' && (
                  <p className="text-xs text-slate-400">
                    Synthetic jobs execute full asynchronous worker lifecycles (`pending` &rarr; `queued` &rarr; `processing` &rarr; `finalizing` &rarr; `completed`), validating database updates, state transitions, and RQ dispatch without external network calls.
                  </p>
                )}

                {/* Conversion Output Targets */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div>
                    <label className="text-xs text-slate-300 font-medium">Target Mode</label>
                    <select
                      value={outputMode}
                      onChange={(e) => {
                        const m = e.target.value;
                        setOutputMode(m);
                        setContainer(m === 'audio' ? 'mp3' : 'mp4');
                      }}
                      className="w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="video">Video</option>
                      <option value="audio">Audio</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs text-slate-300 font-medium">Target Container</label>
                    <select
                      value={container}
                      onChange={(e) => setContainer(e.target.value)}
                      className="w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                    >
                      {outputMode === 'video' ? (
                        <>
                          <option value="mp4">MP4 (H.264 / AAC)</option>
                          <option value="webm">WebM (VP9 / Opus)</option>
                        </>
                      ) : (
                        <>
                          <option value="mp3">MP3 (High Quality)</option>
                          <option value="m4a">M4A (AAC)</option>
                        </>
                      )}
                    </select>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={rightsConfirmed}
                      onChange={(e) => setRightsConfirmed(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-0"
                    />
                    Confirm rights and source authorization policy
                  </label>

                  <button
                    type="submit"
                    disabled={submitting || (sourceMode === 'upload' && !uploadedMeta)}
                    className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium px-5 py-2 rounded-lg text-sm transition flex items-center gap-2"
                  >
                    {submitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    Dispatch Job
                  </button>
                </div>
              </form>
            </section>

            {/* Job Queue & History Table */}
            <section className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
              <div className="p-4 sm:px-6 border-b border-slate-800 flex items-center justify-between">
                <h2 className="text-base font-semibold text-white flex items-center gap-2">
                  <Server className="w-4 h-4 text-indigo-400" />
                  Execution Queue & History
                </h2>
                <span className="text-xs text-slate-400">{jobs.length} total records</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                      <th className="py-3 px-4 font-medium">Job ID</th>
                      <th className="py-3 px-4 font-medium">Type</th>
                      <th className="py-3 px-4 font-medium">Status</th>
                      <th className="py-3 px-4 font-medium">Progress / Phase</th>
                      <th className="py-3 px-4 font-medium">Output</th>
                      <th className="py-3 px-4 font-medium">Created At</th>
                      <th className="py-3 px-4 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    {jobs.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-slate-500">
                          {loading ? (
                            <div className="flex items-center justify-center gap-2">
                              <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" />
                              <span>Loading queue...</span>
                            </div>
                          ) : (
                            'No jobs recorded yet. Enqueue a job above to test the queue.'
                          )}
                        </td>
                      </tr>
                    ) : (
                      jobs.map((job) => (
                        <tr key={job.id} className="hover:bg-slate-900/30 transition">
                          <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                            {job.id.slice(0, 8)}...
                          </td>
                          <td className="py-3 px-4 font-medium capitalize text-slate-200">
                            {job.jobType.replace('_', ' ')}
                          </td>
                          <td className="py-3 px-4">{getStatusBadge(job.status)}</td>
                          <td className="py-3 px-4">
                            <div className="w-32">
                              <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                                <span>{job.progress?.phase || '-'}</span>
                                <span>{job.progress?.percent !== null ? `${job.progress.percent}%` : ''}</span>
                              </div>
                              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                <div
                                  className="bg-indigo-500 h-1.5 rounded-full transition-all duration-300"
                                  style={{ width: `${job.progress?.percent || 0}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4 uppercase text-slate-400">
                            {job.requestedContainer || '-'}
                          </td>
                          <td className="py-3 px-4 text-slate-400">
                            {new Date(job.createdAt).toLocaleTimeString()}
                          </td>
                          <td className="py-3 px-4 text-right">
                            {['pending', 'queued', 'processing', 'inspecting'].includes(job.status) && (
                              <button
                                onClick={() => handleCancelJob(job.id)}
                                className="text-rose-400 hover:text-rose-300 text-xs font-medium"
                              >
                                Cancel
                              </button>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : (
          /* Media Library Section */
          <section className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
            <div className="p-4 sm:px-6 border-b border-slate-800 flex items-center justify-between">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <FileVideo className="w-4 h-4 text-indigo-400" />
                Completed Media Library (Phase 2 & 3 Output)
              </h2>
              <span className="text-xs text-slate-400">{assets.length} stored files</span>
            </div>

            {assets.length === 0 ? (
              <div className="py-16 text-center text-slate-500 text-sm">
                No completed media files yet. Upload a local file or run an acquisition job to populate the library.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-6">
                {assets.map((asset) => (
                  <div key={asset.id} className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-slate-700 transition">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          {asset.container}
                        </span>
                        <span className="text-[11px] text-slate-500">
                          {formatBytes(asset.sizeBytes)}
                        </span>
                      </div>

                      <h3 className="font-semibold text-sm text-slate-100 truncate" title={asset.originalFilenameSafe}>
                        {asset.title || asset.originalFilenameSafe}
                      </h3>

                      <div className="mt-2 text-[11px] text-slate-400 space-y-1">
                        {asset.videoCodec && <p>Video Codec: {asset.videoCodec}</p>}
                        {asset.audioCodec && <p>Audio Codec: {asset.audioCodec}</p>}
                        {asset.durationSeconds && <p>Duration: {formatDuration(asset.durationSeconds)}</p>}
                        <p className="text-slate-500">Created: {new Date(asset.createdAt).toLocaleDateString()}</p>
                      </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-900 flex items-center justify-between">
                      <a
                        href={asset.downloadUrl}
                        download={asset.originalFilenameSafe}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300"
                      >
                        <Download className="w-3.5 h-3.5" /> Download
                      </a>
                      <button
                        onClick={() => handleDeleteAsset(asset.id)}
                        className="p-1 text-slate-500 hover:text-rose-400 transition"
                        title="Delete file"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-4 px-6 text-center text-xs text-slate-600">
        Local Media Downloader &bull; Version {systemInfo?.version || '0.1.0'} &bull; Phases 0, 1, 2, 3 Implemented
      </footer>
    </div>
  );
}
