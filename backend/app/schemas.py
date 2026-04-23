from __future__ import annotations

# MASTER PROMPT UPDATE: Rich notes payloads and premium MCQ test contracts for the study layer.

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class EnvelopeMeta(BaseModel):
    request_id: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    error_type: str | None = None
    reason: str | None = None
    suggestions: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: ErrorPayload


class UserPublic(BaseModel):
    id: str
    name: str
    email: str
    created_at: str


class AuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class SignupRequest(AuthRequest):
    name: str = Field(min_length=2, max_length=120)


class AuthData(BaseModel):
    user: UserPublic
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    ok: Literal[True] = True
    data: AuthData
    meta: EnvelopeMeta


class HealthData(BaseModel):
    status: Literal["ok"]
    storage_mode: Literal["local", "turso"]
    ai_mode: Literal["gemini", "demo"]
    ai_reason: Literal["missing_key", "invalid_key"] | None = None
    ocr_fallback: Literal["local_vision"] | None = None


class HealthResponse(BaseModel):
    ok: Literal[True] = True
    data: HealthData
    meta: EnvelopeMeta


class ExamItem(BaseModel):
    id: str
    code: str
    name: str
    description: str
    version: int
    content_hash: str
    updated_at: str


class SubjectItem(BaseModel):
    id: str
    exam_id: str
    code: str
    name: str
    description: str
    display_order: int
    version: int
    content_hash: str
    updated_at: str


class ExternalNotePayload(BaseModel):
    source: str
    title: str
    url: str
    recommended: bool = False
    why: str


class SubtopicItem(BaseModel):
    id: str
    topic_id: str
    name: str
    external_notes: list[ExternalNotePayload] = Field(default_factory=list)
    display_order: int


class TopicItem(BaseModel):
    class PracticeCounts(BaseModel):
        mcq: int
        mains: int

    id: str
    exam_id: str
    subject_id: str
    code: str
    name: str
    description: str
    parent_topic_id: str | None = None
    display_order: int = 0
    learning_objectives: list[str]
    difficulty: str
    estimated_minutes: int
    version: int
    content_hash: str
    updated_at: str
    practice_counts: PracticeCounts
    subtopics: list[SubtopicItem] = Field(default_factory=list)


class SubjectTree(SubjectItem):
    topics: list[TopicItem]


class ExamTree(ExamItem):
    subjects: list[SubjectTree]


class CatalogData(BaseModel):
    exams: list[ExamTree]


class CatalogResponse(BaseModel):
    ok: Literal[True] = True
    data: CatalogData
    meta: EnvelopeMeta


class StructuredTopicNotesPayload(BaseModel):
    core_idea: str
    framework: list[str]
    key_anchors: list[str]
    answer_direction: list[str]
    linkages: list[str]


class SubjectTopicPreviewPayload(BaseModel):
    topic_id: str
    topic_name: str
    description: str
    note_ready: bool
    note_preview: str
    mcq_count: int
    practice_count: int
    pyq_count: int
    progress_average_score: float | None = None
    progress_trend: float | None = None


class ContinueTargetPayload(BaseModel):
    subject_id: str
    topic_id: str
    subject_name: str
    topic_name: str
    href: str
    reason: str


class StudyActionPayload(BaseModel):
    type: str
    label: str
    href: str
    description: str | None = None
    cta_label: str = "Open"


class TodayPlanPayload(BaseModel):
    title: str
    duration_minutes: int
    steps: list[str] = Field(default_factory=list)
    cta_label: str
    href: str


class DashboardSummaryPayload(BaseModel):
    average_score: float
    due_revisions: int
    improvement_trend: float
    total_attempts: int
    streak: int
    last_score: float | None = None
    weakest_area: str | None = None
    most_repeated_mistake: str | None = None
    strongest_topic: str | None = None
    weak_topics: list[str] = Field(default_factory=list)
    recommended_action: StudyActionPayload | None = None
    today_plan: TodayPlanPayload | None = None


class DashboardSubjectPayload(BaseModel):
    id: str
    exam_id: str
    code: str
    name: str
    description: str
    topic_count: int
    href: str
    progress_average_score: float | None = None
    progress_trend: float | None = None
    due_revisions: int = 0


class DashboardExamPayload(BaseModel):
    id: str
    code: str
    name: str
    description: str


class StudyDashboardData(BaseModel):
    selected_exam_id: str
    selected_exam_code: str
    exams: list[DashboardExamPayload]
    summary: DashboardSummaryPayload
    continue_target: ContinueTargetPayload | None = None
    subjects: list[DashboardSubjectPayload]


class StudyDashboardResponse(BaseModel):
    ok: Literal[True] = True
    data: StudyDashboardData
    meta: EnvelopeMeta


class SubjectProgressPayload(BaseModel):
    average_score: float
    trend_delta: float
    total_attempts: int
    due_revisions: int
    weak_topics: list[str] = Field(default_factory=list)


class StudySubjectData(BaseModel):
    exam: ExamItem
    subject: SubjectItem
    syllabus: list[TopicItem]
    notes_topics: list[SubjectTopicPreviewPayload]
    question_topics: list[SubjectTopicPreviewPayload]
    mcq_topics: list[SubjectTopicPreviewPayload]
    progress: SubjectProgressPayload


class StudySubjectResponse(BaseModel):
    ok: Literal[True] = True
    data: StudySubjectData
    meta: EnvelopeMeta


class StudyQuestionOptionPayload(BaseModel):
    id: str
    text: str


class StudyQuestionPayload(BaseModel):
    id: str
    topic_id: str
    type: Literal["mcq", "mains"]
    kind: Literal["mcq", "practice", "pyq"]
    prompt: str
    options: list[StudyQuestionOptionPayload] | None = None
    difficulty: str
    explanation_hint: str
    recommended_word_limit: int | None = None


class FlashcardPreviewPayload(BaseModel):
    generated_count: int
    due_count: int
    next_review: str | None = None


class StudyTopicData(BaseModel):
    exam: ExamItem
    subject: SubjectItem
    topic: TopicItem
    notes: StructuredTopicNotesPayload | None = None
    notes_status: Literal["ready", "coming_soon"]
    practice_mode: Literal["answer_writing", "mcq_only"]
    practice_questions: list[StudyQuestionPayload]
    pyqs: list[StudyQuestionPayload]
    mcqs: list[StudyQuestionPayload]
    flashcards: FlashcardPreviewPayload
    progress: PerformanceRowPayload | None = None
    chapter_progress: dict[str, Any] | None = None
    weak_subtopics: list[dict[str, Any]] = Field(default_factory=list)
    completed_subtopics: list[str] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    trusted_notes: list[ExternalNotePayload] = Field(default_factory=list)
    next_best_action: StudyActionPayload | None = None


class StudyTopicResponse(BaseModel):
    ok: Literal[True] = True
    data: StudyTopicData
    meta: EnvelopeMeta


class RichNotesSectionPayload(BaseModel):
    heading: str
    paragraphs: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class CurrentAffairsConnectionPayload(BaseModel):
    headline: str
    takeaway: str
    exam_use: str


class RevisionTableRowPayload(BaseModel):
    anchor: str
    why_it_matters: str
    exam_use: str


class MainsWritingBlueprintPayload(BaseModel):
    intro: list[str] = Field(default_factory=list)
    body: list[str] = Field(default_factory=list)
    conclusion: list[str] = Field(default_factory=list)
    value_add: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class WritingBriefPayload(BaseModel):
    directive: str
    keywords: list[str] = Field(default_factory=list)
    structure_hint: list[str] = Field(default_factory=list)


class SubtopicNotesPayload(BaseModel):
    subtopic_id: str
    topic_id: str
    title: str
    summary: str
    estimated_read_minutes: int
    why_this_matters: list[str] = Field(default_factory=list)
    concept_sections: list[RichNotesSectionPayload] = Field(default_factory=list)
    upsc_exam_angle: list[str] = Field(default_factory=list)
    pyq_linkage: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    current_affairs_connections: list[CurrentAffairsConnectionPayload] = Field(default_factory=list)
    mind_map_summary: list[str] = Field(default_factory=list)
    mains_writing: MainsWritingBlueprintPayload
    quick_revision_table: list[RevisionTableRowPayload] = Field(default_factory=list)
    active_recall: list[str] = Field(default_factory=list)
    mcq_bridges: list[str] = Field(default_factory=list)
    external_notes: list[ExternalNotePayload] = Field(default_factory=list)
    writing_brief: WritingBriefPayload
    next_best_action: StudyActionPayload | None = None
    content_hash: str
    updated_at: str


class SubtopicNotesResponse(BaseModel):
    ok: Literal[True] = True
    data: SubtopicNotesPayload
    meta: EnvelopeMeta


class StudyMCQTestQuestionPayload(BaseModel):
    id: str
    topic_id: str
    topic_name: str
    prompt: str
    options: list[StudyQuestionOptionPayload]
    difficulty: str
    explanation_hint: str


class StudyMCQTestContextPayload(BaseModel):
    id: str
    code: str
    name: str


class StudyMCQTestData(BaseModel):
    scope: Literal["topic", "subject"]
    scope_id: str
    title: str
    subtitle: str
    exam: DashboardExamPayload
    subject: StudyMCQTestContextPayload
    duration_minutes: int
    total_questions: int
    questions: list[StudyMCQTestQuestionPayload]


class StudyMCQTestResponse(BaseModel):
    ok: Literal[True] = True
    data: StudyMCQTestData
    meta: EnvelopeMeta


class PracticeTopicPayload(BaseModel):
    topic_id: str
    topic_name: str
    subject_name: str
    href: str
    reason: str
    average_score: float | None = None


class StudyPracticeData(BaseModel):
    exam: DashboardExamPayload
    daily_question: DailyQuestionPayload | None = None
    weak_topics: list[PracticeTopicPayload]
    moderate_topics: list[PracticeTopicPayload]
    mixed_mcqs: list[StudyQuestionPayload]


class StudyPracticeResponse(BaseModel):
    ok: Literal[True] = True
    data: StudyPracticeData
    meta: EnvelopeMeta


class RevisionTopicPayload(BaseModel):
    topic_id: str
    topic_name: str
    subject_name: str
    href: str
    average_score: float | None = None
    trend_delta: float | None = None


class StudyRevisionData(BaseModel):
    exam: DashboardExamPayload
    summary: DashboardSummaryPayload
    review_cards: list[ReviewCardPayload]
    weak_topics: list[RevisionTopicPayload]


class StudyRevisionResponse(BaseModel):
    ok: Literal[True] = True
    data: StudyRevisionData
    meta: EnvelopeMeta


class OCRPreviewRequest(BaseModel):
    answer_text: str | None = Field(default=None, max_length=15000)
    handwritten_image_base64: str | None = None
    handwritten_image_mime_type: str | None = None

    @field_validator("handwritten_image_mime_type")
    @classmethod
    def validate_preview_image_mime(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"}:
            raise ValueError("Unsupported image MIME type.")
        return value

    @model_validator(mode="after")
    def validate_preview_input(self) -> "OCRPreviewRequest":
        if not self.answer_text and not self.handwritten_image_base64:
            raise ValueError("Provide answer_text or handwritten_image_base64.")
        return self


class OCRPreviewData(BaseModel):
    extracted_text: str
    cleaned_text: str


class OCRPreviewResponse(BaseModel):
    ok: Literal[True] = True
    data: OCRPreviewData
    meta: EnvelopeMeta


class StudyMCQAttemptRequest(BaseModel):
    exam_id: str
    subject_id: str
    topic_id: str
    question_id: str
    selected_option: str


class StudyMCQAttemptData(BaseModel):
    attempt: dict[str, Any]
    evaluation: dict[str, Any]
    performance: dict[str, Any]


class StudyMCQAttemptResponse(BaseModel):
    ok: Literal[True] = True
    data: StudyMCQAttemptData
    meta: EnvelopeMeta


class AIQuestionOptionPayload(BaseModel):
    id: str
    text: str


class AIGeneratedQuestionPayload(BaseModel):
    type: Literal["mcq", "mains"]
    prompt: str
    options: list[AIQuestionOptionPayload] | None = None
    correct_option_id: str | None = None
    explanation: str
    explanation_hint: str
    difficulty: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIGeneratedNoteSectionPayload(BaseModel):
    heading: str
    body: list[str]


class AIGeneratedDiagramPayload(BaseModel):
    title: str
    steps: list[str]


class AIGeneratedNotesBundle(BaseModel):
    summary: list[str]
    detailed: list[AIGeneratedNoteSectionPayload]
    examples: list[str]
    traps: list[str]
    diagrams: list[AIGeneratedDiagramPayload]


class AIGenerationBundle(BaseModel):
    notes: AIGeneratedNotesBundle
    questions: list[AIGeneratedQuestionPayload]


class AIEvaluationRubricPayload(BaseModel):
    accuracy: float
    structure: float
    depth: float


class AIEvaluationBundle(BaseModel):
    score: float = Field(ge=0, le=10)
    max_score: float = Field(default=10, ge=0)
    verdict: str
    rubric: AIEvaluationRubricPayload
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    extracted_text: str | None = None
    reasoning_summary: str


class ClassificationBlock(BaseModel):
    title: str
    items: list[str]


class CurrentAffairsLink(BaseModel):
    issue: str
    explanation: str
    static_linkage: str
    upsc_relevance: str


class MainsAnswerStructure(BaseModel):
    intro: list[str]
    body: list[str]
    conclusion: list[str]


class NotesPayload(BaseModel):
    topic_id: str
    version: int
    content_hash: str
    source: Literal["database", "ai", "demo", "cache"]
    thirty_second_revision: list[str]
    core_facts: list[str]
    classification: list[ClassificationBlock]
    case_laws: list[str]
    current_affairs: list[CurrentAffairsLink]
    prelim_traps: list[str]
    mains_answer_structure: MainsAnswerStructure
    value_addition: list[str]
    pyq: list[str]
    updated_at: str


class FlashcardPayload(BaseModel):
    id: str
    topic_id: str
    card_type: Literal["FACTUAL", "CONCEPTUAL", "TRAP", "MAINS"]
    front: str
    back: str
    explanation: str
    difficulty: Literal["easy", "medium", "hard"]
    source: Literal["database", "ai", "demo", "cache"] | None = None


class RevisionProgressPayload(BaseModel):
    card_id: str
    ease_factor: float
    interval_days: float
    next_review: str
    correct_count: int
    incorrect_count: int
    last_result: str | None = None


class ReviewCardPayload(BaseModel):
    id: str
    topic_id: str
    topic_name: str
    card_type: str
    front: str
    back: str
    explanation: str
    difficulty: str
    progress: RevisionProgressPayload


class RevisionSummaryPayload(BaseModel):
    cards_added: int
    due_today: int
    next_review_dates: list[str]
    schedule_days: list[int]


class GeneratedFlashcardPayload(BaseModel):
    card_type: Literal["FACTUAL", "CONCEPTUAL", "TRAP", "MAINS"]
    front: str
    back: str
    explanation: str
    difficulty: Literal["easy", "medium", "hard"]


class GeneratedNotesPayload(BaseModel):
    thirty_second_revision: list[str]
    core_facts: list[str]
    classification: list[ClassificationBlock]
    case_laws: list[str]
    current_affairs: list[CurrentAffairsLink]
    prelim_traps: list[str]
    mains_answer_structure: MainsAnswerStructure
    value_addition: list[str]
    pyq: list[str]


class LearningBundleLLMPayload(BaseModel):
    notes: GeneratedNotesPayload
    flashcards: list[GeneratedFlashcardPayload]


class ModelAnswerPayload(BaseModel):
    intro: list[str]
    body: list[str]
    conclusion: list[str]
    must_have_points: list[str]
    good_to_have_points: list[str]
    extra_edge_points: list[str]
    articles_and_facts: list[str]
    examples: list[str]
    value_addition: list[str]
    core_concepts: list[str] = Field(default_factory=list)
    full_answer: list[str]


class NormalizationPayload(BaseModel):
    cleaned_answer: str
    sentence_list: list[str]


class ExtractedTextPayload(BaseModel):
    extracted_text: str


class ConceptExtractionPayload(BaseModel):
    concepts: list[str]


class EvaluationGuidancePayload(BaseModel):
    top_improvements: list[str] = Field(min_length=3, max_length=3)
    strengths: list[str] = Field(min_length=2, max_length=3)
    ideal_answer_directions: list[str] = Field(min_length=3, max_length=3)


class ContentEvaluatorPayload(BaseModel):
    relevance: Literal["FULL", "PARTIAL", "OFF_TOPIC"]
    domain: Literal["CORRECT", "WRONG"]
    must_have_points: list[str]
    good_to_have_points: list[str]
    extra_edge_points: list[str]
    missing_points: list[str]
    incorrect_points: list[str]
    alternative_valid: bool


class ReasoningEvaluatorPayload(BaseModel):
    depth: Literal["SURFACE", "MODERATE", "DEEP"]
    thinking: Literal["DESCRIPTIVE", "ANALYTICAL", "CRITICAL"]
    balanced_argument: bool
    real_world_relevance: Literal["LOW", "MEDIUM", "HIGH"]
    logical_flow: Literal["WEAK", "ADEQUATE", "STRONG"]
    interlinking_topics: bool


class DirectiveEvaluatorPayload(BaseModel):
    directive: Literal["FULL", "PARTIAL", "NONE"]
    structure: Literal["STRONG", "ADEQUATE", "WEAK"]
    fulfilled_demands: list[str]
    missed_demands: list[str]


class ValueAdditionsPayload(BaseModel):
    examples: list[str]
    data_points: list[str]
    reports: list[str]
    schemes: list[str]
    case_studies: list[str]


class BluffFlagsPayload(BaseModel):
    filler_phrases: list[str]
    vague_sentences: list[str]
    repetitions: list[str]
    low_value_lines: list[str]


class ConceptUniverseItemPayload(BaseModel):
    concept: str
    importance: Literal["core", "secondary"] = "secondary"


class ConceptScorePayload(BaseModel):
    concept: str
    importance: Literal["core", "secondary"]
    coverage_score: Literal[0, 1, 2]


class CoreSummaryPayload(BaseModel):
    core_total: int = Field(ge=0)
    core_covered: int = Field(ge=0)
    core_well_covered: int = Field(ge=0)


class DimensionCountsPayload(BaseModel):
    causes: int = Field(ge=0)
    impacts: int = Field(ge=0)
    challenges: int = Field(ge=0)
    way_forward: int = Field(ge=0)
    examples: int = Field(ge=0)


class StructureSignalsPayload(BaseModel):
    introduction: Literal["present", "weak", "missing"]
    body: Literal["structured", "semi", "unstructured"]
    conclusion: Literal["present", "weak", "missing"]


class ValueAdditionCountsPayload(BaseModel):
    data_or_report: int = Field(ge=0)
    example: int = Field(ge=0)
    generic: int = Field(ge=0)


class PenaltyFlagPayload(BaseModel):
    flag: Literal[
        "missing_conclusion",
        "poor_structure",
        "weak_core_coverage",
        "excessive_vagueness",
        "contradiction_present",
        "factual_error_present",
    ]
    severity: Literal["low", "medium", "high"]


class UnifiedEvaluationSignalsPayload(BaseModel):
    directive: str
    required_components: list[str]
    concept_scores: list[ConceptScorePayload]
    extra_valid_concepts: list[str]
    core_summary: CoreSummaryPayload
    dimension_counts: DimensionCountsPayload
    dimension_balance: Literal["poor", "average", "good"]
    structure: StructureSignalsPayload
    core_coverage_ratio: float = Field(ge=0, le=1)
    core_depth_ratio: float = Field(ge=0, le=1)
    clarity_score: int = Field(ge=0, le=5)
    value_additions: ValueAdditionCountsPayload
    vague_ratio: float = Field(ge=0, le=1)
    directive_coverage_ratio: float = Field(ge=0, le=1)
    factual_error_present: bool
    penalty_flags: list[PenaltyFlagPayload]
    contradiction_present: bool
    partial_concepts_count: int = Field(ge=0)
    answer_length_category: Literal["short", "optimal", "long"]
    fundamental_weakness: bool
    confidence: Literal["low", "medium", "high"]


class LLMAnalysisPayload(BaseModel):
    relevance: Literal["FULL", "PARTIAL", "OFF_TOPIC"]
    domain: Literal["CORRECT", "WRONG"]
    must_have_points: list[str]
    good_to_have_points: list[str]
    extra_edge_points: list[str]
    missing_points: list[str]
    incorrect_points: list[str]
    depth: Literal["SURFACE", "MODERATE", "DEEP"]
    thinking: Literal["DESCRIPTIVE", "ANALYTICAL", "CRITICAL"]
    directive: Literal["FULL", "PARTIAL", "NONE"]
    structure: Literal["STRONG", "ADEQUATE", "WEAK"]
    vagueness: Literal["LOW", "MODERATE", "HIGH"]
    alternative_valid: bool


class SimilarityPayload(BaseModel):
    similarity_score: float
    coverage_score: float
    must_have_points_present: list[str]
    good_to_have_points_present: list[str]
    extra_edge_points_present: list[str]
    covered_concepts: list[str]
    missing_concepts: list[str]
    key_concept_hits: list[str]


class DepthSignalsPayload(BaseModel):
    cause_effect: bool
    multi_dimension: bool
    examples: bool
    interlinking: bool
    depth_from_signals: Literal["SURFACE", "MODERATE", "DEEP"]


class MaturityPayload(BaseModel):
    level: Literal["LOW", "MEDIUM", "HIGH"]
    bonus: float


class FeaturePayload(BaseModel):
    fact_density: float
    factual_statements: int
    factual_anchor_sentences: int
    total_sentences: int
    word_count: int
    average_sentence_length: float
    long_sentence_ratio: float
    transition_markers: int
    reasoning_signals: int
    multidimensional_terms: list[str]
    balance_detected: bool
    examples_detected: list[str]
    bluff_phrases_detected: list[str]
    structure_intro_present: bool
    structure_conclusion_present: bool
    vague_sentences: int
    bluff_ratio: float
    vagueness_from_signals: Literal["LOW", "MODERATE", "HIGH"]
    depth_signals: DepthSignalsPayload
    maturity: MaturityPayload
    interlinking_examples: list[str]
    real_world_references: list[str]


class CalibrationWeightsPayload(BaseModel):
    must_weight: float
    good_weight: float
    similarity_weight: float
    coverage_weight: float
    depth_weight: float
    directive_weight: float
    extra_weight: float
    fact_weight: float
    maturity_weight: float
    impression_weight: float


class ScoringBreakdownPayload(BaseModel):
    content_score: float
    depth_score: float
    similarity_component: float
    directive_score: float
    impression_score: float
    relevance_score: float
    structure_score: float
    efficiency_score: float
    base_formula_score: float
    ensemble_score: float
    raw_score: float
    final_score: int
    scaled_score: float
    examiner_variance: float
    max_score_cap: int
    applied_caps: list[str]
    applied_penalties: list[str]
    confidence: float
    weights: CalibrationWeightsPayload


class EvaluationPayload(BaseModel):
    score: int
    scaled_score: float
    percentile: float
    performance_band: str
    score_band: Literal["Poor", "Average", "Good", "Topper-level"]
    verdict: str
    mistakes: list[str]
    ideal_answer: ModelAnswerPayload
    confidence: float
    maturity: Literal["LOW", "MEDIUM", "HIGH"]
    bluff_ratio: float
    coverage_score: float
    similarity_score: float
    relevance_score: float
    structure_score: float
    efficiency_score: float
    impression_score: float
    examiner_variance: float
    alternative_valid: bool
    applied_caps: list[str]
    applied_penalties: list[str]
    penalty_reasons: list[str]
    missing_concepts: list[str]
    answer_gap_summary: str
    top_improvements: list[str]
    strengths: list[str]
    ideal_answer_directions: list[str]
    progress_delta: float
    next_action: str
    streak: int
    weakest_dimension: str | None = None
    consistent_weakness: str | None = None
    repeated_mistake: str | None = None
    repeated_mistake_count: int | None = None
    pressure_message: str | None = None


class EvaluateUPSCRequest(BaseModel):
    topic_id: str
    question: str = Field(min_length=10, max_length=1200)
    subtopic_id: str | None = None
    student_answer: str | None = Field(default=None, max_length=15000)
    ocr_text: str | None = Field(default=None, max_length=15000)
    handwritten_image_base64: str | None = None
    handwritten_image_mime_type: str | None = None
    max_marks: int = Field(default=10, ge=5, le=20)
    include_learning_assets: bool = True

    @field_validator("handwritten_image_mime_type")
    @classmethod
    def validate_image_mime(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"}:
            raise ValueError("Unsupported image MIME type.")
        return value

    @model_validator(mode="after")
    def validate_input(self) -> "EvaluateUPSCRequest":
        if not any([self.student_answer, self.ocr_text, self.handwritten_image_base64]):
            raise ValueError("Provide student_answer, ocr_text, or handwritten_image_base64.")
        return self


class GenerateNotesRequest(BaseModel):
    topic_id: str


class GenerateFlashcardsRequest(BaseModel):
    topic_id: str


class UpdateProgressRequest(BaseModel):
    card_id: str
    correct: bool


class EvaluateUPSCData(BaseModel):
    evaluation: EvaluationPayload
    analysis: LLMAnalysisPayload
    notes: NotesPayload
    flashcards: list[FlashcardPayload]
    revision: RevisionSummaryPayload
    normalized_answer: NormalizationPayload
    similarity: SimilarityPayload
    features: FeaturePayload
    scoring: ScoringBreakdownPayload


class DailyQuestionPayload(BaseModel):
    topic_id: str
    topic_name: str
    subtopic_id: str | None = None
    subtopic_name: str | None = None
    subject_name: str
    subject_code: str
    question: str
    reason: str
    average_score: float
    progress_trend: float
    streak: int


class DailyQuestionData(BaseModel):
    daily_question: DailyQuestionPayload


class EvaluateUPSCResponse(BaseModel):
    ok: Literal[True] = True
    data: EvaluateUPSCData
    meta: EnvelopeMeta


class DailyQuestionResponse(BaseModel):
    ok: Literal[True] = True
    data: DailyQuestionData
    meta: EnvelopeMeta


class NotesResponseData(BaseModel):
    notes: NotesPayload


class NotesResponse(BaseModel):
    ok: Literal[True] = True
    data: NotesResponseData
    meta: EnvelopeMeta


class FlashcardsResponseData(BaseModel):
    flashcards: list[FlashcardPayload]
    revision: RevisionSummaryPayload


class FlashcardsResponse(BaseModel):
    ok: Literal[True] = True
    data: FlashcardsResponseData
    meta: EnvelopeMeta


class ReviewCardsData(BaseModel):
    cards: list[ReviewCardPayload]
    due_today: int


class ReviewCardsResponse(BaseModel):
    ok: Literal[True] = True
    data: ReviewCardsData
    meta: EnvelopeMeta


class UpdateProgressData(BaseModel):
    progress: RevisionProgressPayload
    revision: RevisionSummaryPayload


class UpdateProgressResponse(BaseModel):
    ok: Literal[True] = True
    data: UpdateProgressData
    meta: EnvelopeMeta


class PerformanceSummaryPayload(BaseModel):
    overall_accuracy: float
    average_score: float
    total_attempts: int
    due_revisions: int
    improvement_trend: float


class PerformanceRowPayload(BaseModel):
    id: str
    user_id: str
    scope_type: str
    exam_id: str | None = None
    subject_id: str | None = None
    topic_id: str | None = None
    accuracy: float
    average_score: float
    trend_delta: float
    total_attempts: int
    correct_attempts: int
    revisions_due: int
    revisions_completed: int
    next_review_at: str | None = None
    last_activity_at: str | None = None
    updated_at: str


class RevisionQueueRowPayload(BaseModel):
    exam_id: str
    subject_id: str
    topic_id: str
    stage: str
    due_at: str
    status: str


class PerformanceData(BaseModel):
    summary: PerformanceSummaryPayload
    exam_breakdown: list[PerformanceRowPayload]
    subject_breakdown: list[PerformanceRowPayload]
    topic_breakdown: list[PerformanceRowPayload]
    revision_queue: list[RevisionQueueRowPayload]


class PerformanceResponse(BaseModel):
    ok: Literal[True] = True
    data: PerformanceData
    meta: EnvelopeMeta


# --- Focused two-feature contracts: MCQ practice + handwritten answer evaluation ---


class TopicNormalizationPayload(BaseModel):
    subject: str
    core_topic: str
    subtopics: list[str] = Field(default_factory=list)


class MCQQuestionPayload(BaseModel):
    id: str
    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: Literal["A", "B", "C", "D"]
    explanation: str
    source_tag: str
    subtopic: str


class MCQPublicQuestionPayload(BaseModel):
    id: str
    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    source_tag: str
    subtopic: str


class MCQStartRequest(BaseModel):
    topic_text: str = Field(min_length=3, max_length=300)
    question_count: int = Field(default=10, ge=5, le=30)


class MCQStartData(BaseModel):
    session_id: str
    timer_seconds_per_question: int = 36
    normalization: TopicNormalizationPayload
    questions: list[MCQPublicQuestionPayload]


class MCQStartResponse(BaseModel):
    ok: Literal[True] = True
    data: MCQStartData
    meta: EnvelopeMeta


class MCQSubmitAnswerPayload(BaseModel):
    question_id: str
    selected_option: Literal["A", "B", "C", "D"] | None = None


class MCQSubmitRequest(BaseModel):
    session_id: str
    answers: list[MCQSubmitAnswerPayload]


class MCQResultQuestionPayload(BaseModel):
    id: str
    question: str
    selected_option: Literal["A", "B", "C", "D"] | None = None
    correct_option: Literal["A", "B", "C", "D"]
    status: Literal["correct", "wrong", "skipped"]
    source_tag: str
    subtopic: str
    explanation: str


class MCQSubmitData(BaseModel):
    session_id: str
    score: int
    total_questions: int
    accuracy_pct: float
    attempt_pct: float
    weak_topics: list[str]
    retry_question_ids: list[str]
    questions: list[MCQResultQuestionPayload]


class MCQSubmitResponse(BaseModel):
    ok: Literal[True] = True
    data: MCQSubmitData
    meta: EnvelopeMeta


class MCQHistoryItemPayload(BaseModel):
    session_id: str
    raw_topic: str
    subject: str
    core_topic: str
    question_count: int
    status: str
    score: int | None = None
    accuracy_pct: float | None = None
    attempt_pct: float | None = None
    weak_topics: list[str] = Field(default_factory=list)
    created_at: str
    submitted_at: str | None = None


class MCQHistoryData(BaseModel):
    count: int
    items: list[MCQHistoryItemPayload] = Field(default_factory=list)


class MCQHistoryResponse(BaseModel):
    ok: Literal[True] = True
    data: MCQHistoryData
    meta: EnvelopeMeta


class PYQImportQuestionPayload(BaseModel):
    question: str = Field(min_length=12, max_length=1200)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: int | Literal["A", "B", "C", "D"]
    explanation: str = Field(min_length=8, max_length=2000)
    source_tag: str = Field(min_length=12, max_length=200)


class PYQImportRequest(BaseModel):
    topic_text: str = Field(min_length=3, max_length=300)
    questions: list[PYQImportQuestionPayload] = Field(min_length=1, max_length=1000)


class PYQImportIssuePayload(BaseModel):
    row_index: int
    reason: str
    question: str | None = None


class PYQImportData(BaseModel):
    topic_normalization: TopicNormalizationPayload
    received_count: int
    inserted_count: int
    skipped_count: int
    issues: list[PYQImportIssuePayload] = Field(default_factory=list)


class PYQImportResponse(BaseModel):
    ok: Literal[True] = True
    data: PYQImportData
    meta: EnvelopeMeta


class PYQSyncRequest(BaseModel):
    source: Literal["upscpredict"] = "upscpredict"


class PYQSyncPageStatPayload(BaseModel):
    path: str
    from_cache: bool = False
    fetched_questions: int
    inserted: int
    skipped: int


class PYQSyncIssuePayload(BaseModel):
    page: str
    reason: str
    detail: str | None = None


class PYQSyncData(BaseModel):
    source: str
    paths_scanned: int
    inserted_count: int
    skipped_count: int
    inventory: dict[str, int]
    pages: list[PYQSyncPageStatPayload]
    issues: list[PYQSyncIssuePayload] = Field(default_factory=list)


class PYQSyncResponse(BaseModel):
    ok: Literal[True] = True
    data: PYQSyncData
    meta: EnvelopeMeta


class EvaluationOCRPreviewRequest(BaseModel):
    student_answer: str | None = Field(default=None, max_length=15000)
    ocr_text: str | None = Field(default=None, max_length=15000)
    handwritten_image_base64: str | None = None
    handwritten_image_mime_type: str | None = None

    @field_validator("handwritten_image_mime_type")
    @classmethod
    def validate_eval_preview_mime(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"}:
            raise ValueError("Unsupported image MIME type.")
        return value

    @model_validator(mode="after")
    def validate_eval_preview_input(self) -> "EvaluationOCRPreviewRequest":
        if not any([self.student_answer, self.ocr_text, self.handwritten_image_base64]):
            raise ValueError("Provide student_answer, ocr_text, or handwritten_image_base64.")
        return self


class EvaluationOCRPreviewData(BaseModel):
    extracted_text: str
    cleaned_text: str
    merged_text: str


class EvaluationOCRPreviewResponse(BaseModel):
    ok: Literal[True] = True
    data: EvaluationOCRPreviewData
    meta: EnvelopeMeta


class EvaluateStrictRequest(BaseModel):
    question: str = Field(min_length=10, max_length=1200)
    student_answer: str | None = Field(default=None, max_length=15000)
    ocr_text: str | None = Field(default=None, max_length=15000)
    handwritten_image_base64: str | None = None
    handwritten_image_mime_type: str | None = None
    concept_universe: list[str | ConceptUniverseItemPayload] = Field(default_factory=list)
    max_marks: int = Field(default=10, ge=1, le=20)

    @field_validator("handwritten_image_mime_type")
    @classmethod
    def validate_eval_mime(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"}:
            raise ValueError("Unsupported image MIME type.")
        return value

    @model_validator(mode="after")
    def validate_eval_input(self) -> "EvaluateStrictRequest":
        if not any([self.student_answer, self.ocr_text, self.handwritten_image_base64]):
            raise ValueError("Provide student_answer, ocr_text, or handwritten_image_base64.")
        return self


class EvaluationSubscoresPayload(BaseModel):
    content_accuracy: float
    structure: float
    depth: float
    keywords: float
    conclusion: float


class EvaluationHistoryItemPayload(BaseModel):
    id: str
    question_text: str
    input_mode: str
    score: float
    subscores: EvaluationSubscoresPayload
    strengths: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    created_at: str


class EvaluationHistoryData(BaseModel):
    count: int
    items: list[EvaluationHistoryItemPayload] = Field(default_factory=list)


class EvaluationHistoryResponse(BaseModel):
    ok: Literal[True] = True
    data: EvaluationHistoryData
    meta: EnvelopeMeta


class EvaluateStrictData(BaseModel):
    evaluation: dict[str, Any]
    analysis: dict[str, Any]
    cleaned_answer: str
    score: float
    improvements: list[str]
    model_answer: dict[str, Any]
    subscores: EvaluationSubscoresPayload


class EvaluateStrictResponse(BaseModel):
    ok: Literal[True] = True
    data: EvaluateStrictData
    meta: EnvelopeMeta
