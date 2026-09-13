export type Citation = {
  source_id: string;
  chunk_id: string;
  title: string;
  publisher: string;
  page: number | null;
  excerpt: string;
  url: string | null;
};

export type Health = {
  status: "ready" | "index_missing" | "index_mismatch";
  generation_provider: string;
  embedding_provider: string;
  tts_provider: string;
  model_ready: boolean;
  embedding_ready: boolean;
  speech_ready: boolean;
  vrm_ready: boolean;
  demo_ready: boolean;
  index: Record<string, string>;
};

export type FinalPayload = {
  answer: string;
  refused: boolean;
  reason: string | null;
  citations: Citation[];
  speech_token: string | null;
};
