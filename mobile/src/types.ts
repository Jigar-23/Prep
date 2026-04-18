export type User = {
  id: string;
  name: string;
  email: string;
  created_at: string;
};

export type AuthData = {
  user: User;
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};

export type Topic = {
  id: string;
  exam_id: string;
  subject_id: string;
  code: string;
  name: string;
  description: string;
  learning_objectives: string[];
  difficulty: string;
  estimated_minutes: number;
  version: number;
  content_hash: string;
  updated_at: string;
};

export type Subject = {
  id: string;
  exam_id: string;
  code: string;
  name: string;
  description: string;
  display_order: number;
  version: number;
  content_hash: string;
  updated_at: string;
  topics: Topic[];
};

export type Exam = {
  id: string;
  code: string;
  name: string;
  description: string;
  version: number;
  content_hash: string;
  updated_at: string;
  subjects: Subject[];
};

export type NotesPayload = {
  topic_id: string;
  version: number;
  content_hash: string;
  source: "database" | "ai" | "demo" | "cache";
  thirty_second_revision: string[];
  core_facts: string[];
  classification: { title: string; items: string[] }[];
  case_laws: string[];
  current_affairs: {
    issue: string;
    explanation: string;
    static_linkage: string;
    upsc_relevance: string;
  }[];
  prelim_traps: string[];
  mains_answer_structure: {
    intro: string[];
    body: string[];
    conclusion: string[];
  };
  value_addition: string[];
  pyq: string[];
  updated_at: string;
};

export type FlashcardPayload = {
  id: string;
  topic_id: string;
  card_type: "FACTUAL" | "CONCEPTUAL" | "TRAP" | "MAINS";
  front: string;
  back: string;
  explanation: string;
  difficulty: "easy" | "medium" | "hard";
};

export type RevisionSummaryPayload = {
  cards_added: number;
  due_today: number;
  next_review_dates: string[];
  schedule_days: number[];
};

export type ReviewCardPayload = {
  id: string;
  topic_id: string;
  topic_name: string;
  card_type: string;
  front: string;
  back: string;
  explanation: string;
  difficulty: string;
  progress: {
    card_id: string;
    ease_factor: number;
    interval_days: number;
    next_review: string;
    correct_count: number;
    incorrect_count: number;
    last_result?: string | null;
  };
};

export type ReviewCardsData = {
  cards: ReviewCardPayload[];
  due_today: number;
};

export type EvaluateUPSCData = {
  evaluation: {
    score: number;
    scaled_score: number;
    percentile: number;
    performance_band: string;
    score_band: "Poor" | "Average" | "Good" | "Topper-level";
    verdict: string;
    mistakes: string[];
    confidence: number;
    maturity: "LOW" | "MEDIUM" | "HIGH";
    bluff_ratio: number;
    coverage_score: number;
    similarity_score: number;
    relevance_score: number;
    structure_score: number;
    efficiency_score: number;
    impression_score: number;
    examiner_variance: number;
    alternative_valid: boolean;
    applied_caps: string[];
    applied_penalties: string[];
    penalty_reasons: string[];
    missing_concepts: string[];
    answer_gap_summary: string;
    top_improvements: string[];
    strengths: string[];
    ideal_answer_directions: string[];
    progress_delta: number;
    next_action: string;
    streak: number;
    weakest_dimension?: string | null;
    consistent_weakness?: string | null;
    repeated_mistake?: string | null;
    repeated_mistake_count?: number | null;
    pressure_message?: string | null;
    ideal_answer: {
      intro: string[];
      body: string[];
      conclusion: string[];
      full_answer: string[];
      must_have_points: string[];
      good_to_have_points: string[];
      extra_edge_points: string[];
      articles_and_facts: string[];
      examples: string[];
      value_addition: string[];
      core_concepts: string[];
    };
  };
  analysis: {
    relevance: "FULL" | "PARTIAL" | "OFF_TOPIC";
    domain: "CORRECT" | "WRONG";
    must_have_points: string[];
    good_to_have_points: string[];
    extra_edge_points: string[];
    missing_points: string[];
    incorrect_points: string[];
    depth: "SURFACE" | "MODERATE" | "DEEP";
    thinking: "DESCRIPTIVE" | "ANALYTICAL" | "CRITICAL";
    directive: "FULL" | "PARTIAL" | "NONE";
    structure: "STRONG" | "ADEQUATE" | "WEAK";
    vagueness: "LOW" | "MODERATE" | "HIGH";
    alternative_valid: boolean;
  };
  notes: NotesPayload;
  flashcards: FlashcardPayload[];
  revision: RevisionSummaryPayload;
  similarity: {
    similarity_score: number;
    coverage_score: number;
    must_have_points_present: string[];
    good_to_have_points_present: string[];
    extra_edge_points_present: string[];
    covered_concepts: string[];
    missing_concepts: string[];
    key_concept_hits: string[];
  };
  features: {
    fact_density: number;
    factual_statements: number;
    factual_anchor_sentences: number;
    total_sentences: number;
    word_count: number;
    average_sentence_length: number;
    long_sentence_ratio: number;
    transition_markers: number;
    reasoning_signals: number;
    examples_detected: string[];
    multidimensional_terms: string[];
    balance_detected: boolean;
    bluff_phrases_detected: string[];
    structure_intro_present: boolean;
    structure_conclusion_present: boolean;
    vague_sentences: number;
    bluff_ratio: number;
    vagueness_from_signals: "LOW" | "MODERATE" | "HIGH";
    depth_signals: {
      cause_effect: boolean;
      multi_dimension: boolean;
      examples: boolean;
      interlinking: boolean;
      depth_from_signals: "SURFACE" | "MODERATE" | "DEEP";
    };
    maturity: {
      level: "LOW" | "MEDIUM" | "HIGH";
      bonus: number;
    };
    interlinking_examples: string[];
    real_world_references: string[];
  };
  scoring: {
    content_score: number;
    depth_score: number;
    similarity_component: number;
    directive_score: number;
    impression_score: number;
    relevance_score: number;
    structure_score: number;
    efficiency_score: number;
    base_formula_score: number;
    ensemble_score: number;
    raw_score: number;
    final_score: number;
    scaled_score: number;
    examiner_variance: number;
    max_score_cap: number;
    applied_caps: string[];
    applied_penalties: string[];
    confidence: number;
    weights: {
      must_weight: number;
      good_weight: number;
      similarity_weight: number;
      coverage_weight: number;
      depth_weight: number;
      directive_weight: number;
      extra_weight: number;
      fact_weight: number;
      maturity_weight: number;
      impression_weight: number;
    };
  };
};

export type DailyQuestionPayload = {
  topic_id: string;
  topic_name: string;
  subtopic_id?: string | null;
  subtopic_name?: string | null;
  subject_name: string;
  subject_code: string;
  question: string;
  reason: string;
  average_score: number;
  progress_trend: number;
  streak: number;
};

export type SessionState = {
  token: string;
  user: User;
};
