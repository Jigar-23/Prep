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
  parent_topic_id?: string | null;
  display_order?: number;
  learning_objectives: string[];
  difficulty: string;
  estimated_minutes: number;
  version: number;
  content_hash: string;
  updated_at: string;
  practice_counts: {
    mcq: number;
    mains: number;
  };
  subtopics?: {
    id: string;
    topic_id: string;
    name: string;
    display_order: number;
  }[];
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

export type ClassificationBlock = {
  title: string;
  items: string[];
};

export type CurrentAffairsLink = {
  issue: string;
  explanation: string;
  static_linkage: string;
  upsc_relevance: string;
};

export type MainsAnswerStructure = {
  intro: string[];
  body: string[];
  conclusion: string[];
};

export type NotesPayload = {
  topic_id: string;
  version: number;
  content_hash: string;
  source: "database" | "ai" | "demo" | "cache";
  thirty_second_revision: string[];
  core_facts: string[];
  classification: ClassificationBlock[];
  case_laws: string[];
  current_affairs: CurrentAffairsLink[];
  prelim_traps: string[];
  mains_answer_structure: MainsAnswerStructure;
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
  source?: "database" | "ai" | "demo" | "cache" | null;
};

export type RevisionProgressPayload = {
  card_id: string;
  ease_factor: number;
  interval_days: number;
  next_review: string;
  correct_count: number;
  incorrect_count: number;
  last_result?: string | null;
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
  progress: RevisionProgressPayload;
};

export type RevisionSummaryPayload = {
  cards_added: number;
  due_today: number;
  next_review_dates: string[];
  schedule_days: number[];
};

export type ModelAnswerPayload = {
  intro: string[];
  body: string[];
  conclusion: string[];
  must_have_points: string[];
  good_to_have_points: string[];
  extra_edge_points: string[];
  articles_and_facts: string[];
  examples: string[];
  value_addition: string[];
  core_concepts: string[];
  full_answer: string[];
};

export type NormalizationPayload = {
  cleaned_answer: string;
  sentence_list: string[];
};

export type LLMAnalysisPayload = {
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

export type SimilarityPayload = {
  similarity_score: number;
  coverage_score: number;
  must_have_points_present: string[];
  good_to_have_points_present: string[];
  extra_edge_points_present: string[];
  covered_concepts: string[];
  missing_concepts: string[];
  key_concept_hits: string[];
};

export type DepthSignalsPayload = {
  cause_effect: boolean;
  multi_dimension: boolean;
  examples: boolean;
  interlinking: boolean;
  depth_from_signals: "SURFACE" | "MODERATE" | "DEEP";
};

export type MaturityPayload = {
  level: "LOW" | "MEDIUM" | "HIGH";
  bonus: number;
};

export type FeaturePayload = {
  fact_density: number;
  factual_statements: number;
  factual_anchor_sentences: number;
  total_sentences: number;
  word_count: number;
  average_sentence_length: number;
  long_sentence_ratio: number;
  transition_markers: number;
  reasoning_signals: number;
  multidimensional_terms: string[];
  balance_detected: boolean;
  examples_detected: string[];
  bluff_phrases_detected: string[];
  structure_intro_present: boolean;
  structure_conclusion_present: boolean;
  vague_sentences: number;
  bluff_ratio: number;
  vagueness_from_signals: "LOW" | "MODERATE" | "HIGH";
  depth_signals: DepthSignalsPayload;
  maturity: MaturityPayload;
  interlinking_examples: string[];
  real_world_references: string[];
};

export type CalibrationWeightsPayload = {
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

export type ScoringBreakdownPayload = {
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
  weights: CalibrationWeightsPayload;
};

export type EvaluationPayload = {
  score: number;
  scaled_score: number;
  percentile: number;
  performance_band: string;
  score_band: "Poor" | "Average" | "Good" | "Topper-level";
  verdict: string;
  mistakes: string[];
  ideal_answer: ModelAnswerPayload;
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
};

export type EvaluateRequest = {
  topic_id: string;
  subtopic_id?: string;
  question: string;
  student_answer?: string;
  ocr_text?: string;
  handwritten_image_base64?: string;
  handwritten_image_mime_type?: string;
  max_marks?: number;
  include_learning_assets?: boolean;
};

export type EvaluateUPSCData = {
  evaluation: EvaluationPayload;
  analysis: LLMAnalysisPayload;
  notes: NotesPayload;
  flashcards: FlashcardPayload[];
  revision: RevisionSummaryPayload;
  normalized_answer: NormalizationPayload;
  similarity: SimilarityPayload;
  features: FeaturePayload;
  scoring: ScoringBreakdownPayload;
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

export type ReviewCardsData = {
  cards: ReviewCardPayload[];
  due_today: number;
};

export type UpdateProgressData = {
  progress: RevisionProgressPayload;
  revision: RevisionSummaryPayload;
};

export type StructuredTopicNotesPayload = {
  core_idea: string;
  framework: string[];
  key_anchors: string[];
  answer_direction: string[];
  linkages: string[];
};

export type ContinueTargetPayload = {
  subject_id: string;
  topic_id: string;
  subject_name: string;
  topic_name: string;
  href: string;
  reason: string;
};

export type DashboardExamPayload = {
  id: string;
  code: string;
  name: string;
  description: string;
};

export type DashboardSummaryPayload = {
  average_score: number;
  due_revisions: number;
  improvement_trend: number;
  total_attempts: number;
  streak: number;
  last_score?: number | null;
  weakest_area?: string | null;
  most_repeated_mistake?: string | null;
  recommended_action?: {
    type: "retry_subtopic";
    topic_id: string;
    subtopic_id: string;
    label: string;
    href: string;
  } | null;
};

export type DashboardSubjectPayload = {
  id: string;
  exam_id: string;
  code: string;
  name: string;
  description: string;
  topic_count: number;
  href: string;
  progress_average_score?: number | null;
  progress_trend?: number | null;
  due_revisions: number;
};

export type StudyDashboardData = {
  selected_exam_id: string;
  selected_exam_code: string;
  exams: DashboardExamPayload[];
  summary: DashboardSummaryPayload;
  continue_target?: ContinueTargetPayload | null;
  subjects: DashboardSubjectPayload[];
};

export type SubjectTopicPreviewPayload = {
  topic_id: string;
  topic_name: string;
  description: string;
  note_ready: boolean;
  note_preview: string;
  mcq_count: number;
  practice_count: number;
  pyq_count: number;
  progress_average_score?: number | null;
  progress_trend?: number | null;
};

export type SubjectProgressPayload = {
  average_score: number;
  trend_delta: number;
  total_attempts: number;
  due_revisions: number;
  weak_topics: string[];
};

export type StudySubjectData = {
  exam: DashboardExamPayload & {
    version: number;
    content_hash: string;
    updated_at: string;
  };
  subject: Subject;
  syllabus: Topic[];
  notes_topics: SubjectTopicPreviewPayload[];
  question_topics: SubjectTopicPreviewPayload[];
  mcq_topics: SubjectTopicPreviewPayload[];
  progress: SubjectProgressPayload;
};

export type StudyQuestionOptionPayload = {
  id: string;
  text: string;
};

export type StudyQuestionPayload = {
  id: string;
  topic_id: string;
  type: "mcq" | "mains";
  kind: "mcq" | "practice" | "pyq";
  prompt: string;
  options?: StudyQuestionOptionPayload[] | null;
  difficulty: string;
  explanation_hint: string;
  recommended_word_limit?: number | null;
};

export type FlashcardPreviewPayload = {
  generated_count: number;
  due_count: number;
  next_review?: string | null;
};

export type StudyTopicData = {
  exam: DashboardExamPayload & {
    version: number;
    content_hash: string;
    updated_at: string;
  };
  subject: Subject;
  topic: Topic;
  notes?: StructuredTopicNotesPayload | null;
  notes_status: "ready" | "coming_soon";
  practice_mode: "answer_writing" | "mcq_only";
  practice_questions: StudyQuestionPayload[];
  pyqs: StudyQuestionPayload[];
  mcqs: StudyQuestionPayload[];
  flashcards: FlashcardPreviewPayload;
  progress?: {
    average_score: number;
    trend_delta: number;
    total_attempts: number;
    due_revisions: number;
    last_activity_at?: string | null;
  } | null;
  chapter_progress?: {
    total_subtopics: number;
    completed_count: number;
    weak_count: number;
    continue_subtopic_id?: string | null;
  } | null;
  weak_subtopics?: { id: string; title: string; status: string }[];
  completed_subtopics?: string[];
  sections?: { name: string; items: { id: string; title: string; status: string }[] }[];
};

export type SubtopicNotesPayload = {
  subtopic_id: string;
  topic_id: string;
  quick_recall: string[];
  structured_answer_framework: Record<string, unknown>;
  ready_answer_150: string;
  key_facts_examples: string[];
  value_addition: string[];
  diagram_flow: string[];
  content_hash: string;
  updated_at: string;
};

export type PracticeTopicPayload = {
  topic_id: string;
  topic_name: string;
  subject_name: string;
  href: string;
  reason: string;
  average_score?: number | null;
};

export type StudyPracticeData = {
  exam: DashboardExamPayload;
  daily_question?: DailyQuestionPayload | null;
  weak_topics: PracticeTopicPayload[];
  moderate_topics: PracticeTopicPayload[];
  mixed_mcqs: StudyQuestionPayload[];
};

export type RevisionTopicPayload = {
  topic_id: string;
  topic_name: string;
  subject_name: string;
  href: string;
  average_score?: number | null;
  trend_delta?: number | null;
};

export type StudyRevisionData = {
  exam: DashboardExamPayload;
  summary: DashboardSummaryPayload;
  review_cards: ReviewCardPayload[];
  weak_topics: RevisionTopicPayload[];
};

export type OCRPreviewData = {
  extracted_text: string;
  cleaned_text: string;
};

export type StudyMCQAttemptData = {
  attempt: {
    id: string;
    question_id: string;
    score: number;
    submitted_at: string;
  };
  evaluation: {
    id: string;
    mode: string;
    score: number;
    max_score: number;
    verdict: string;
    strengths: string[];
    improvements: string[];
    rubric: Record<string, number>;
    extracted_text?: string | null;
    reasoning_summary: string;
  };
  performance: {
    overall_accuracy: number;
    topic_accuracy: number;
    subject_accuracy: number;
    exam_accuracy: number;
  };
};
