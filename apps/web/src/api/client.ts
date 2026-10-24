import { Job, SystemInfo, SystemStatus, Asset, UploadResponse, InspectionResult } from '../types';

export const api = {
  async getSystemInfo(): Promise<SystemInfo> {
    const res = await fetch('/api/v1/system/info');
    if (!res.ok) throw new Error('Failed to fetch system info');
    return res.json();
  },

  async getSystemStatus(): Promise<SystemStatus> {
    const res = await fetch('/api/v1/system/status');
    if (!res.ok) throw new Error('Failed to fetch system status');
    return res.json();
  },

  async listJobs(): Promise<Job[]> {
    const res = await fetch('/api/v1/jobs');
    if (!res.ok) throw new Error('Failed to fetch jobs');
    const data = await res.json();
    return data.items || [];
  },

  async createJob(payload: {
    source: { type: string; url?: string; uploadId?: string };
    output: { mode: string; container: string; quality?: string };
    rightsConfirmed: boolean;
  }): Promise<{ jobId: string; status: string; statusUrl: string }> {
    const idempotencyKey = crypto.randomUUID();
    const res = await fetch('/api/v1/jobs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to submit job');
    }
    return res.json();
  },

  async cancelJob(jobId: string): Promise<void> {
    const res = await fetch(`/api/v1/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to cancel job');
  },

  async uploadFile(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch('/api/v1/uploads', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      let message = `Upload failed with HTTP ${res.status}`;
      try {
        const err = await res.json();
        message = err.detail || err.title || message;
      } catch {
        const text = await res.text().catch(() => '');
        if (text) message = text.slice(0, 150);
      }
      throw new Error(message);
    }
    return res.json();
  },

  async inspectSource(url: string): Promise<InspectionResult> {
    const res = await fetch('/api/v1/sources/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, rightsConfirmed: true }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to inspect source URL');
    }
    return res.json();
  },

  async listAssets(): Promise<Asset[]> {
    const res = await fetch('/api/v1/assets');
    if (!res.ok) throw new Error('Failed to fetch assets');
    const data = await res.json();
    return data.items || [];
  },

  async deleteAsset(assetId: string): Promise<void> {
    const res = await fetch(`/api/v1/assets/${assetId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete asset');
  },
};
