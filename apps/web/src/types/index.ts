export type JobStatus =
  | 'pending'
  | 'queued'
  | 'inspecting'
  | 'processing'
  | 'finalizing'
  | 'completed'
  | 'cancel_requested'
  | 'cancelled'
  | 'failed'
  | 'expired';

export type JobType =
  | 'remote_acquisition'
  | 'file_conversion'
  | 'metadata_inspection'
  | 'synthetic_test';

export interface JobProgress {
  phase: string | null;
  percent: number | null;
  bytesProcessed: number | null;
  totalBytes: number | null;
  speedBytesPerSecond: number | null;
  etaSeconds: number | null;
  updatedAt: string | null;
}

export interface Job {
  id: string;
  jobType: JobType;
  status: JobStatus;
  progress: JobProgress;
  sourceType: string;
  sourceHost: string | null;
  sourceUrlRedacted: string | null;
  requestedContainer: string | null;
  requestedMode: string | null;
  requestedQuality: string | null;
  attemptCount: number;
  maxAttempts: number;
  lastErrorCode: string | null;
  lastErrorSafeMessage: string | null;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  expiresAt: string | null;
}

export interface SystemStatus {
  status: string;
  queueDepth: number;
  activeJobs: number;
  databaseConnected: boolean;
  redisConnected: boolean;
  workerCount: number;
  diskFreeBytes: number;
  diskTotalBytes: number;
}

export interface SystemInfo {
  version: string;
  environment: string;
  capabilities: {
    youtubeDownloadEnabled: boolean;
    localUploadEnabled: boolean;
    maxUploadBytes: number;
    maxOutputBytes: number;
  };
}

export interface Asset {
  id: string;
  jobId: string | null;
  title: string | null;
  originalFilenameSafe: string;
  container: string;
  videoCodec: string | null;
  audioCodec: string | null;
  durationSeconds: number | null;
  sizeBytes: number;
  sha256: string | null;
  createdAt: string;
  expiresAt: string | null;
  downloadUrl: string;
}

export interface UploadResponse {
  uploadId: string;
  originalFilename: string;
  sizeBytes: number;
  format: string | null;
  durationSeconds: number | null;
}

export interface InspectionResult {
  source: string;
  sourceUrlRedacted: string;
  metadata: {
    title: string;
    durationSeconds: number | null;
    thumbnailUrl: string | null;
    creatorLabel: string | null;
  };
  capabilities: {
    videoContainers: string[];
    audioContainers: string[];
    qualityPresets: string[];
    subtitles: boolean;
    playlist: boolean;
  };
  policy: {
    decision: 'allowed' | 'denied';
    reasonCode: string;
    message: string | null;
  };
}
