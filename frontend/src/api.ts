/**
 * BoltzStudio API Client
 */

const API_BASE = '/api'

export interface SequenceInput {
  id: string
  sequence: string
  type: 'protein' | 'dna' | 'rna'
}

export interface LigandInput {
  id: string
  smiles?: string
  ccd?: string
}

export interface PredictionRequest {
  sequences: SequenceInput[]
  ligands?: LigandInput[]
  name?: string
  recycling_steps?: number
  sampling_steps?: number
  diffusion_samples?: number
}

export interface JobStatus {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress?: number
  result?: PredictionResult
  error?: string
}

export interface PredictionResult {
  structure_pdb: string
  structure_cif: string
  confidence: {
    confidence_score: number
    ptm: number
    iptm: number
    complex_plddt: number
    complex_iplddt: number
    complex_pde: number
  }
  plddt_per_residue: number[]
  work_dir: string
}

export interface RandomMutateResponse {
  original_sequence: string
  mutated_sequence: string
  mutations: string[]
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Request failed: ${response.status}`)
    }

    return response.json()
  }

  async predict(request: PredictionRequest): Promise<JobStatus> {
    return this.request<JobStatus>('/predict', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getJobStatus(jobId: string): Promise<JobStatus> {
    return this.request<JobStatus>(`/job/${jobId}`)
  }

  async getStructure(jobId: string, format: 'pdb' | 'cif' = 'pdb'): Promise<{ structure: string }> {
    return this.request<{ structure: string }>(`/job/${jobId}/structure?format=${format}`)
  }

  async randomMutate(
    sequence: string,
    numMutations: number = 1,
    positions?: number[]
  ): Promise<RandomMutateResponse> {
    const params = new URLSearchParams({
      sequence,
      num_mutations: numMutations.toString(),
    })
    if (positions) {
      params.set('positions', positions.join(','))
    }
    return this.request<RandomMutateResponse>(`/design/random-mutate?${params}`, {
      method: 'POST',
    })
  }

  async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/health')
  }
}

export const api = new ApiClient()
