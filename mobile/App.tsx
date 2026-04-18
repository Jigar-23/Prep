import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { StatusBar } from "expo-status-bar";

import { api } from "./src/api";
import { clearSession, loadDraft, loadSession, saveDraft, saveSession } from "./src/storage";
import {
  DailyQuestionPayload,
  EvaluateUPSCData,
  Exam,
  FlashcardPayload,
  NotesPayload,
  RevisionSummaryPayload,
  ReviewCardPayload,
  SessionState,
} from "./src/types";

type RouteState =
  | { name: "dashboard" }
  | { name: "topic"; topicId: string; seededQuestion?: string }
  | { name: "review" };

type TopicMode = "overview" | "writing" | "evaluation" | "improvement";

function flattenTopics(exams: Exam[]) {
  const entries: Array<{ exam: Exam; subject: Exam["subjects"][number]; topic: Exam["subjects"][number]["topics"][number] }> = [];

  for (const exam of exams) {
    for (const subject of exam.subjects) {
      for (const topic of subject.topics) {
        entries.push({ exam, subject, topic });
      }
    }
  }

  return entries;
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatTrend(value: number) {
  return `${value >= 0 ? "+" : ""}${Math.round(value)}%`;
}

function examReadiness(scoreBand: EvaluateUPSCData["evaluation"]["score_band"]) {
  if (scoreBand === "Topper-level" || scoreBand === "Good") {
    return "Ready";
  }
  if (scoreBand === "Average") {
    return "Borderline";
  }
  return "Not Ready";
}

function hardenFeedbackLine(line: string) {
  return line
    .replace(/you could improve/gi, "Missing")
    .replace(/consider adding/gi, "Missing")
    .replace(/try to/gi, "Not addressed")
    .replace(/needs?/gi, "Weak");
}

function biggestMistake(evaluation: EvaluateUPSCData["evaluation"]) {
  return (
    evaluation.penalty_reasons[0] ||
    evaluation.mistakes[0] ||
    evaluation.top_improvements[0] ||
    "Not addressed: core demand of the question."
  );
}

function decisiveVerdict(evaluation: EvaluateUPSCData["evaluation"]) {
  const issue = hardenFeedbackLine(biggestMistake(evaluation).toLowerCase());
  if (evaluation.score_band === "Poor") {
    return `Weak answer. ${issue}`;
  }
  if (evaluation.score_band === "Average") {
    return `Average answer. ${issue}`;
  }
  if (evaluation.score_band === "Good") {
    return `Good answer. ${issue}`;
  }
  return `Ready answer. ${issue}`;
}

function ActionButton({
  label,
  onPress,
  variant,
  disabled,
}: {
  label: string;
  onPress: () => void;
  variant: "primary" | "secondary";
  disabled?: boolean;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[styles.button, variant === "primary" ? styles.primaryButton : styles.secondaryButton, disabled ? styles.buttonDisabled : null]}
    >
      <Text style={variant === "primary" ? styles.primaryButtonText : styles.secondaryButtonText}>{label}</Text>
    </Pressable>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metricCard}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

function StepPill({
  index,
  label,
  active,
  enabled,
  onPress,
}: {
  index: number;
  label: string;
  active: boolean;
  enabled: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable disabled={!enabled} onPress={onPress} style={[styles.stepPill, active ? styles.stepPillActive : null, !enabled ? styles.stepPillDisabled : null]}>
      <View style={[styles.stepIndex, active ? styles.stepIndexActive : null]}>
        <Text style={[styles.stepIndexText, active ? styles.stepIndexTextActive : null]}>{index}</Text>
      </View>
      <Text style={[styles.stepLabel, active ? styles.stepLabelActive : null]}>{label}</Text>
    </Pressable>
  );
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: (session: SessionState) => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const auth = mode === "login" ? await api.login(email, password) : await api.signup(name, email, password);
      const session = { token: auth.access_token, user: auth.user };
      await saveSession(session);
      onAuthenticated(session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not authenticate.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.authScroll}>
      <View style={styles.brandPanel}>
        <Text style={styles.eyebrow}>Perp UPSC</Text>
        <Text style={styles.title}>AI-first UPSC prep loop</Text>
        <Text style={styles.bulletItem}>• Write once, get structured evaluation</Text>
        <Text style={styles.bulletItem}>• Fix gaps with notes + flashcards</Text>
        <Text style={styles.bulletItem}>• Close weak topics in daily review</Text>
      </View>

      <View style={styles.card}>
        <View style={styles.segmentRow}>
          <Pressable onPress={() => setMode("login")} style={[styles.segmentButton, mode === "login" && styles.segmentActive]}>
            <Text style={[styles.segmentLabel, mode === "login" && styles.segmentLabelActive]}>Login</Text>
          </Pressable>
          <Pressable onPress={() => setMode("signup")} style={[styles.segmentButton, mode === "signup" && styles.segmentActive]}>
            <Text style={[styles.segmentLabel, mode === "signup" && styles.segmentLabelActive]}>Signup</Text>
          </Pressable>
        </View>

        {mode === "signup" ? (
          <TextInput placeholder="Full name" placeholderTextColor="#64748B" style={styles.input} value={name} onChangeText={setName} />
        ) : null}
        <TextInput
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="Email"
          placeholderTextColor="#64748B"
          style={styles.input}
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          placeholder="Password"
          placeholderTextColor="#64748B"
          secureTextEntry
          style={styles.input}
          value={password}
          onChangeText={setPassword}
        />
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
        <ActionButton label={busy ? "Working..." : mode === "login" ? "Login" : "Create account"} onPress={() => void submit()} variant="primary" />
      </View>
    </ScrollView>
  );
}

function DashboardScreen({
  exams,
  reviewCards,
  dailyQuestion,
  onRefresh,
  onOpenTopic,
  onOpenReview,
  onLogout,
}: {
  exams: Exam[];
  reviewCards: ReviewCardPayload[];
  dailyQuestion: DailyQuestionPayload | null;
  onRefresh: () => Promise<void>;
  onOpenTopic: (topicId: string, seededQuestion?: string) => void;
  onOpenReview: () => void;
  onLogout: () => void;
}) {
  const exam = exams.find((item) => item.code === "UPSC") ?? exams[0];

  return (
    <ScrollView contentContainerStyle={styles.screenContent}>
      <View style={styles.heroCard}>
        <Text style={styles.eyebrow}>{exam?.name ?? "UPSC"}</Text>
        <Text style={styles.sectionTitle}>{exam?.description ?? "UPSC study workspace"}</Text>
        <Text style={styles.subtleText}>Select topic → Evaluate → Improve → Revise</Text>
        <View style={styles.metricRow}>
          <MetricCard label="Subjects" value={String(exam?.subjects.length ?? 0)} />
          <MetricCard label="Topics" value={String(flattenTopics(exams).length)} />
          <MetricCard label="Due today" value={String(reviewCards.length)} />
        </View>
        <View style={styles.actionRow}>
          <ActionButton label="Refresh" onPress={() => void onRefresh()} variant="secondary" />
          <ActionButton label="Daily Review" onPress={onOpenReview} variant="primary" />
          <ActionButton label="Logout" onPress={onLogout} variant="secondary" />
        </View>
      </View>

      {dailyQuestion ? (
        <View style={styles.card}>
          <Text style={styles.eyebrow}>Today's question</Text>
          <Text style={styles.cardTitle}>{dailyQuestion.topic_name}</Text>
          <Text style={styles.bodyText}>{dailyQuestion.question}</Text>
          <Text style={styles.subtleText}>{dailyQuestion.reason}</Text>
          <View style={styles.metricRow}>
            <MetricCard label="Avg score" value={`${dailyQuestion.average_score.toFixed(1)}/10`} />
            <MetricCard label="Trend" value={formatTrend(dailyQuestion.progress_trend)} />
            <MetricCard label="Streak" value={`🔥 ${dailyQuestion.streak}`} />
          </View>
          <View style={styles.actionRow}>
            <ActionButton
              label="Start Today's Question"
              onPress={() => onOpenTopic(dailyQuestion.topic_id, dailyQuestion.question)}
              variant="primary"
            />
          </View>
        </View>
      ) : null}

      {reviewCards.length > 0 ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Revision priorities</Text>
          {reviewCards.slice(0, 4).map((card) => (
            <Pressable key={card.id} onPress={() => onOpenTopic(card.topic_id)} style={styles.listRow}>
              <View style={styles.listCopy}>
                <Text style={styles.listTitle}>{card.topic_name}</Text>
                <Text style={styles.bodyText}>{card.card_type} card due in the review queue.</Text>
              </View>
              <Text style={styles.badge}>{card.difficulty}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      {exam?.subjects.map((subject) => (
        <View key={subject.id} style={styles.card}>
          <Text style={styles.eyebrow}>{subject.code}</Text>
          <Text style={styles.cardTitle}>{subject.name}</Text>
          <Text style={styles.bodyText}>{subject.description}</Text>
          {subject.topics.map((topic) => (
            <Pressable key={topic.id} onPress={() => onOpenTopic(topic.id)} style={styles.topicTile}>
              <View style={styles.listCopy}>
                <Text style={styles.listTitle}>{topic.name}</Text>
                <Text style={styles.bodyText}>{topic.description}</Text>
                <Text style={styles.subtleText}>{topic.learning_objectives.slice(0, 3).join(" • ")}</Text>
              </View>
              <Text style={styles.badge}>{topic.difficulty}</Text>
            </Pressable>
          ))}
        </View>
      ))}
    </ScrollView>
  );
}

function TopicScreen({
  exams,
  topicId,
  initialQuestion,
  token,
  onBack,
  onReviewQueueChanged,
}: {
  exams: Exam[];
  topicId: string;
  initialQuestion?: string;
  token: string;
  onBack: () => void;
  onReviewQueueChanged: () => Promise<void>;
}) {
  const context = flattenTopics(exams).find((entry) => entry.topic.id === topicId);
  const [mode, setMode] = useState<TopicMode>("overview");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [ocrText, setOcrText] = useState("");
  const [notes, setNotes] = useState<NotesPayload | null>(null);
  const [flashcards, setFlashcards] = useState<FlashcardPayload[]>([]);
  const [revision, setRevision] = useState<RevisionSummaryPayload | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluateUPSCData | null>(null);
  const [imageBase64, setImageBase64] = useState<string | undefined>(undefined);
  const [imageMimeType, setImageMimeType] = useState<string | undefined>(undefined);
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [busy, setBusy] = useState<"notes" | "flashcards" | "evaluate" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draftLabel, setDraftLabel] = useState("Autosave ready");
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (initialQuestion) {
      return;
    }
    let mounted = true;
    void loadDraft(topicId).then((draft) => {
      if (!mounted || !draft) {
        return;
      }
      setQuestion(draft.question ?? "");
      setAnswer(draft.answer ?? "");
      setOcrText(draft.ocrText ?? "");
      if (draft.question || draft.answer || draft.ocrText) {
        setDraftLabel("Draft restored");
      }
    });
    return () => {
      mounted = false;
    };
  }, [initialQuestion, topicId]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      void saveDraft(topicId, { question, answer, ocrText });
      setDraftLabel(question || answer || ocrText ? "Draft saved locally" : "Autosave ready");
    }, 350);
    return () => clearTimeout(timeout);
  }, [answer, ocrText, question, topicId]);

  useEffect(() => {
    if (!initialQuestion) {
      return;
    }
    setQuestion(initialQuestion);
    setMode("writing");
    setDraftLabel("Today's question loaded");
  }, [initialQuestion]);

  if (!context) {
    return (
      <View style={styles.centered}>
        <Text style={styles.sectionTitle}>Topic not found</Text>
      </View>
    );
  }

  const suggestedQuestions = [
    `Explain the significance of ${context.topic.name} in UPSC preparation.`,
    `Discuss the main dimensions, constitutional aspects, and challenges related to ${context.topic.name}.`,
    `How would you structure a high-scoring UPSC mains answer on ${context.topic.name}?`,
  ];

  const focusPoints = context.topic.learning_objectives.slice(0, 4);
  const wordCount = answer.trim().split(/\s+/).filter(Boolean).length;

  const pickImage = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setError("Photo library permission is required to upload handwritten answer sheets.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      base64: true,
      quality: 0.8,
    });

    if (!result.canceled) {
      const asset = result.assets[0];
      setImageBase64(asset.base64 ?? undefined);
      setImageMimeType(asset.mimeType ?? "image/jpeg");
      setImageUri(asset.uri);
    }
  };

  const loadNotes = async () => {
    setBusy("notes");
    setError(null);
    try {
      const response = await api.generateNotes(token, topicId);
      setNotes(response.notes);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not generate notes.");
    } finally {
      setBusy(null);
    }
  };

  const loadFlashcards = async () => {
    setBusy("flashcards");
    setError(null);
    try {
      const response = await api.generateFlashcards(token, topicId);
      setFlashcards(response.flashcards);
      setRevision(response.revision);
      await onReviewQueueChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not generate flashcards.");
    } finally {
      setBusy(null);
    }
  };

  const evaluate = async () => {
    if (!question.trim()) {
      setError("Add the question before evaluation.");
      return;
    }

    if (!answer.trim() && !ocrText.trim() && !imageBase64) {
      setError("Add a typed answer, OCR text, or handwritten image.");
      return;
    }

    setBusy("evaluate");
    setError(null);
    try {
      const response = await api.evaluate(token, {
        topic_id: topicId,
        question,
        student_answer: answer.trim() || undefined,
        ocr_text: ocrText.trim() || undefined,
        handwritten_image_base64: imageBase64,
        handwritten_image_mime_type: imageMimeType,
        max_marks: 10,
        include_learning_assets: false,
      });
      setEvaluation(response);
      setMode("evaluation");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not evaluate the answer.");
    } finally {
      setBusy(null);
    }
  };

  const stepItems: Array<{ key: TopicMode; label: string; enabled: boolean }> = [
    { key: "overview", label: "Overview", enabled: true },
    { key: "writing", label: "Writing", enabled: true },
    { key: "evaluation", label: "Evaluation", enabled: Boolean(evaluation) },
    { key: "improvement", label: "Improve", enabled: Boolean(evaluation) },
  ];

  return (
    <ScrollView contentContainerStyle={styles.screenContent}>
      <View style={styles.heroCard}>
        <Text style={styles.eyebrow}>{context.subject.name}</Text>
        <Text style={styles.sectionTitle}>{context.topic.name}</Text>
        <Text style={styles.subtleText}>{context.topic.description}</Text>
        <View style={styles.actionRow}>
          <ActionButton label="Back" onPress={onBack} variant="secondary" />
          <ActionButton label="Review" onPress={() => setMode("improvement")} variant="secondary" disabled={!evaluation} />
        </View>
      </View>

      <View style={styles.stepRow}>
        {stepItems.map((item, index) => (
          <StepPill key={item.key} active={mode === item.key} enabled={item.enabled} index={index + 1} label={item.label} onPress={() => item.enabled && setMode(item.key)} />
        ))}
      </View>

      {error ? <Text style={styles.inlineError}>{error}</Text> : null}

      {mode === "overview" ? (
        <View style={styles.card}>
          <Text style={styles.eyebrow}>Step 1</Text>
          <Text style={styles.cardTitle}>Topic overview</Text>
          <Text style={styles.subtleText}>Focus points before writing:</Text>
          {focusPoints.map((item) => (
            <Text key={item} style={styles.bulletItem}>
              • {item}
            </Text>
          ))}
          <View style={styles.actionRow}>
            <ActionButton label="Start Answer Writing" onPress={() => setMode("writing")} variant="primary" />
          </View>
        </View>
      ) : null}

      {mode === "writing" ? (
        <View style={styles.card}>
          <Text style={styles.eyebrow}>Step 2</Text>
          <Text style={styles.cardTitle}>Answer writing</Text>
          <Text style={styles.subtleText}>
            {wordCount} words • {draftLabel}
          </Text>
          <TextInput
            multiline
            placeholder="Paste or write the UPSC question"
            placeholderTextColor="#64748B"
            style={styles.textArea}
            value={question}
            onChangeText={setQuestion}
          />
          <View style={styles.suggestionWrap}>
            {suggestedQuestions.map((item) => (
              <Pressable key={item} onPress={() => setQuestion(item)} style={styles.suggestionChip}>
                <Text style={styles.suggestionLabel}>{item}</Text>
              </Pressable>
            ))}
          </View>
          <TextInput
            multiline
            placeholder="Write your mains answer"
            placeholderTextColor="#64748B"
            style={styles.largeTextArea}
            value={answer}
            onChangeText={setAnswer}
          />
          <TextInput
            multiline
            placeholder="Paste OCR text if available"
            placeholderTextColor="#64748B"
            style={styles.textArea}
            value={ocrText}
            onChangeText={setOcrText}
          />
          {imageUri ? <Image source={{ uri: imageUri }} style={styles.previewImage} /> : null}
          <View style={styles.actionRow}>
            <ActionButton label="Upload Sheet" onPress={() => void pickImage()} variant="secondary" />
            <ActionButton label={busy === "evaluate" ? "Evaluating..." : "Evaluate"} onPress={() => void evaluate()} variant="primary" disabled={busy === "evaluate"} />
          </View>
        </View>
      ) : null}

      {mode === "evaluation" && evaluation ? (
        <View style={styles.card}>
          <Text style={styles.eyebrow}>Step 3</Text>
          <View style={styles.scoreHero}>
            <Text style={styles.scoreValue}>{evaluation.evaluation.scaled_score.toFixed(1)}</Text>
            <Text style={styles.scoreMax}>/10</Text>
          </View>
          <Text style={styles.badge}>{evaluation.evaluation.score_band}</Text>
          <Text style={styles.cardTitle}>Examiner Verdict</Text>
          <Text style={styles.bodyText}>{decisiveVerdict(evaluation.evaluation)}</Text>
          <Text style={styles.bodyText}>
            Percentile {evaluation.evaluation.percentile}% • {evaluation.evaluation.performance_band}
          </Text>
          <Text style={styles.subtleText}>
            Impression {formatPercent(evaluation.evaluation.impression_score)} • Trend {formatTrend(evaluation.evaluation.progress_delta)} •
            {" "}🔥 {evaluation.evaluation.streak} day streak
          </Text>
          <View style={styles.detailsCard}>
            <Text style={styles.cardSubtitle}>Biggest Mistake</Text>
            <Text style={styles.bulletItem}>• {hardenFeedbackLine(biggestMistake(evaluation.evaluation))}</Text>
            {evaluation.evaluation.consistent_weakness ? (
              <Text style={styles.bulletItem}>• You are consistently weak in: {evaluation.evaluation.consistent_weakness}</Text>
            ) : null}
            {evaluation.evaluation.pressure_message ? (
              <Text style={styles.bulletItem}>• {hardenFeedbackLine(evaluation.evaluation.pressure_message)}</Text>
            ) : null}
            <Text style={styles.cardSubtitle}>Exam Readiness</Text>
            <Text style={styles.bulletItem}>• {examReadiness(evaluation.evaluation.score_band)}</Text>
          </View>
          <View style={styles.metricRow}>
            <MetricCard label="Coverage" value={formatPercent(evaluation.evaluation.coverage_score)} />
            <MetricCard label="Relevance" value={formatPercent(evaluation.evaluation.relevance_score)} />
            <MetricCard label="Structure" value={formatPercent(evaluation.evaluation.structure_score)} />
          </View>
          <View style={styles.detailsCard}>
            <Text style={styles.cardSubtitle}>Top 3 Fixes</Text>
            {evaluation.evaluation.top_improvements.slice(0, 3).map((item) => (
              <Text key={item} style={styles.bulletItem}>
                • {hardenFeedbackLine(item)}
              </Text>
            ))}
            <Text style={styles.cardSubtitle}>If You Fix ONE Thing</Text>
            <Text style={styles.bulletItem}>• {hardenFeedbackLine(evaluation.evaluation.top_improvements[0] ?? evaluation.evaluation.next_action)}</Text>
            <Text style={styles.cardSubtitle}>Answer Direction</Text>
            {evaluation.evaluation.ideal_answer_directions.slice(0, 2).map((item) => (
              <Text key={item} style={styles.bulletItem}>
                • {hardenFeedbackLine(item)}
              </Text>
            ))}
          </View>
          <View style={styles.actionRow}>
            <ActionButton label="Refine Answer" onPress={() => setMode("writing")} variant="secondary" />
            <ActionButton label="Open Improvement" onPress={() => setMode("improvement")} variant="primary" />
          </View>
          <Pressable onPress={() => setShowDetails((current) => !current)} style={styles.secondaryButton}>
            <Text style={styles.secondaryButtonText}>{showDetails ? "Hide detailed signals" : "Show detailed signals"}</Text>
          </Pressable>
          {showDetails ? (
            <View style={styles.detailsCard}>
              <Text style={styles.bodyText}>
                Relevance {evaluation.analysis.relevance} • Depth {evaluation.analysis.depth} • Structure {evaluation.analysis.structure}
              </Text>
              <Text style={styles.bodyText}>
                Efficiency {formatPercent(evaluation.evaluation.efficiency_score)} • Bluff ratio {formatPercent(evaluation.evaluation.bluff_ratio)} • Variance{" "}
                {evaluation.evaluation.examiner_variance >= 0 ? "+" : ""}
                {evaluation.evaluation.examiner_variance.toFixed(2)}
              </Text>
              {evaluation.evaluation.mistakes.length > 0 ? (
                <>
                  <Text style={styles.cardSubtitle}>Main gaps</Text>
                  {evaluation.evaluation.mistakes.slice(0, 5).map((item) => (
                    <Text key={item} style={styles.bulletItem}>
                      • {item}
                    </Text>
                  ))}
                </>
              ) : null}
              {evaluation.evaluation.missing_concepts.length > 0 ? (
                <>
                  <Text style={styles.cardSubtitle}>Missing concepts</Text>
                  {evaluation.evaluation.missing_concepts.slice(0, 6).map((item) => (
                    <Text key={item} style={styles.bulletItem}>
                      • {item}
                    </Text>
                  ))}
                </>
              ) : null}
            </View>
          ) : null}
        </View>
      ) : null}

      {mode === "improvement" && evaluation ? (
        <>
          <View style={styles.card}>
            <Text style={styles.eyebrow}>Step 4</Text>
            <Text style={styles.cardTitle}>Improvement tools</Text>
            <Text style={styles.subtleText}>Use only post-evaluation tools.</Text>
            <View style={styles.actionRow}>
              <ActionButton label={busy === "notes" ? "Loading Notes..." : notes ? "Refresh Notes" : "Generate Notes"} onPress={() => void loadNotes()} variant="secondary" disabled={busy !== null} />
              <ActionButton
                label={busy === "flashcards" ? "Loading Cards..." : flashcards.length ? "Refresh Flashcards" : "Generate Flashcards"}
                onPress={() => void loadFlashcards()}
                variant="primary"
                disabled={busy !== null}
              />
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Notes engine</Text>
            {notes ? (
              <>
                {notes.thirty_second_revision.map((item) => (
                  <Text key={item} style={styles.bulletItem}>
                    • {item}
                  </Text>
                ))}
                <Text style={styles.cardSubtitle}>Core facts</Text>
                {notes.core_facts.slice(0, 5).map((item) => (
                  <Text key={item} style={styles.bulletItem}>
                    • {item}
                  </Text>
                ))}
              </>
            ) : (
              <Text style={styles.bodyText}>Generate notes to build a crisp topic sheet for revision.</Text>
            )}
          </View>

          <View style={styles.card}>
            <Text style={styles.eyebrow}>Step 5</Text>
            <Text style={styles.cardTitle}>Revision queue</Text>
            {revision ? (
              <Text style={styles.bodyText}>
                {revision.cards_added} cards seeded • {revision.due_today} due today
              </Text>
            ) : (
              <Text style={styles.bodyText}>Generate flashcards to seed spaced repetition.</Text>
            )}
            {flashcards.length > 0
              ? flashcards.slice(0, 6).map((card) => (
                  <View key={card.id} style={styles.flashcard}>
                    <Text style={styles.badge}>{card.card_type}</Text>
                    <Text style={styles.listTitle}>{card.front}</Text>
                    <Text style={styles.bodyText}>{card.back}</Text>
                  </View>
                ))
              : null}
          </View>
        </>
      ) : null}
    </ScrollView>
  );
}

function ReviewScreen({
  cards,
  onBack,
  onRefresh,
  onMark,
}: {
  cards: ReviewCardPayload[];
  onBack: () => void;
  onRefresh: () => Promise<void>;
  onMark: (cardId: string, correct: boolean) => Promise<void>;
}) {
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});

  return (
    <ScrollView contentContainerStyle={styles.screenContent}>
      <View style={styles.heroCard}>
        <Text style={styles.eyebrow}>Daily review</Text>
        <Text style={styles.sectionTitle}>{cards.length} card(s) due now</Text>
        <Text style={styles.bodyText}>Reveal, recall, then mark each card correct or wrong so the interval engine can reschedule it.</Text>
        <View style={styles.actionRow}>
          <ActionButton label="Back" onPress={onBack} variant="secondary" />
          <ActionButton label="Refresh" onPress={() => void onRefresh()} variant="secondary" />
        </View>
      </View>

      {cards.length > 0 ? (
        cards.map((card) => {
          const open = Boolean(revealed[card.id]);
          return (
            <View key={card.id} style={styles.card}>
              <Text style={styles.badge}>{card.card_type}</Text>
              <Text style={styles.listTitle}>{card.front}</Text>
              <Text style={styles.bodyText}>{card.topic_name}</Text>
              {open ? (
                <>
                  <Text style={styles.cardSubtitle}>Answer</Text>
                  <Text style={styles.bodyText}>{card.back}</Text>
                  <Text style={styles.cardSubtitle}>Explanation</Text>
                  <Text style={styles.bodyText}>{card.explanation}</Text>
                </>
              ) : (
                <Text style={styles.subtleText}>Recall first, then reveal the answer.</Text>
              )}
              <View style={styles.actionRow}>
                <ActionButton label={open ? "Hide" : "Reveal"} onPress={() => setRevealed((current) => ({ ...current, [card.id]: !open }))} variant="secondary" />
                <ActionButton label="Correct" onPress={() => void onMark(card.id, true)} variant="primary" disabled={!open} />
                <ActionButton label="Wrong" onPress={() => void onMark(card.id, false)} variant="secondary" disabled={!open} />
              </View>
            </View>
          );
        })
      ) : (
        <View style={styles.card}>
          <Text style={styles.bodyText}>No cards are due yet. Generate flashcards from a topic to seed the queue.</Text>
        </View>
      )}
    </ScrollView>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState<SessionState | null>(null);
  const [route, setRoute] = useState<RouteState>({ name: "dashboard" });
  const [catalog, setCatalog] = useState<Exam[]>([]);
  const [reviewCards, setReviewCards] = useState<ReviewCardPayload[]>([]);
  const [dailyQuestion, setDailyQuestion] = useState<DailyQuestionPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const bootstrap = async () => {
    const saved = await loadSession();
    setSession(saved);
    setReady(true);
  };

  const refreshWorkspace = async (token = session?.token) => {
    if (!token) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [catalogData, reviewData, dailyData] = await Promise.all([
        api.catalog(token),
        api.reviewCards(token, 30),
        api.dailyQuestion(token),
      ]);
      setCatalog(catalogData.exams);
      setReviewCards(reviewData.cards);
      setDailyQuestion(dailyData.daily_question);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the mobile workspace.");
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    await clearSession();
    setSession(null);
    setCatalog([]);
    setReviewCards([]);
    setDailyQuestion(null);
    setRoute({ name: "dashboard" });
  };

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (session?.token) {
      void refreshWorkspace(session.token);
    }
  }, [session?.token]);

  const handleMark = async (cardId: string, correct: boolean) => {
    if (!session) {
      return;
    }

    setLoading(true);
    try {
      await api.updateProgress(session.token, cardId, correct);
      await refreshWorkspace(session.token);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update revision progress.");
    } finally {
      setLoading(false);
    }
  };

  const content = useMemo(() => {
    if (!ready) {
      return (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color="#2563EB" />
        </View>
      );
    }

    if (!session) {
      return <AuthScreen onAuthenticated={setSession} />;
    }

    if (route.name === "topic") {
      return (
        <TopicScreen
          exams={catalog}
          initialQuestion={route.seededQuestion}
          onBack={() => setRoute({ name: "dashboard" })}
          onReviewQueueChanged={() => refreshWorkspace(session.token)}
          token={session.token}
          topicId={route.topicId}
        />
      );
    }

    if (route.name === "review") {
      return (
        <ReviewScreen
          cards={reviewCards}
          onBack={() => setRoute({ name: "dashboard" })}
          onMark={handleMark}
          onRefresh={() => refreshWorkspace(session.token)}
        />
      );
    }

    return (
      <DashboardScreen
        dailyQuestion={dailyQuestion}
        exams={catalog}
        onLogout={() => void logout()}
        onOpenReview={() => setRoute({ name: "review" })}
        onOpenTopic={(selectedTopicId, seededQuestion) => setRoute({ name: "topic", topicId: selectedTopicId, seededQuestion })}
        onRefresh={() => refreshWorkspace(session.token)}
        reviewCards={reviewCards}
      />
    );
  }, [catalog, dailyQuestion, handleMark, ready, reviewCards, route, session]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.flex}>
        {loading && ready && session ? (
          <View style={styles.loadingBanner}>
            <ActivityIndicator color="#FFFFFF" size="small" />
            <Text style={styles.loadingText}>Syncing workspace...</Text>
          </View>
        ) : null}
        {error ? <Text style={styles.globalError}>{error}</Text> : null}
        {content}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },
  flex: {
    flex: 1,
  },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  authScroll: {
    padding: 20,
    gap: 20,
    justifyContent: "center",
  },
  screenContent: {
    padding: 20,
    gap: 18,
  },
  brandPanel: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 24,
    gap: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  heroCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 20,
    gap: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 18,
    gap: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  title: {
    fontSize: 30,
    fontWeight: "700",
    color: "#0F172A",
    lineHeight: 36,
  },
  sectionTitle: {
    fontSize: 24,
    fontWeight: "700",
    color: "#0F172A",
    lineHeight: 30,
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#0F172A",
  },
  cardSubtitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
    marginTop: 6,
  },
  eyebrow: {
    textTransform: "uppercase",
    letterSpacing: 1.5,
    fontSize: 11,
    color: "#2563EB",
    fontWeight: "700",
  },
  bodyText: {
    color: "#64748B",
    fontSize: 15,
    lineHeight: 22,
  },
  subtleText: {
    color: "#64748B",
    fontSize: 13,
    lineHeight: 18,
  },
  input: {
    backgroundColor: "#FFFFFF",
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    color: "#0F172A",
  },
  textArea: {
    minHeight: 110,
    backgroundColor: "#FFFFFF",
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    color: "#0F172A",
    textAlignVertical: "top",
  },
  largeTextArea: {
    minHeight: 240,
    backgroundColor: "#FFFFFF",
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    color: "#0F172A",
    textAlignVertical: "top",
    fontSize: 16,
    lineHeight: 24,
  },
  actionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  button: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 12,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  primaryButton: {
    backgroundColor: "#2563EB",
  },
  secondaryButton: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  secondaryButtonText: {
    color: "#0F172A",
    fontWeight: "700",
  },
  metricRow: {
    flexDirection: "row",
    gap: 10,
    flexWrap: "wrap",
  },
  metricCard: {
    minWidth: 104,
    backgroundColor: "#F8FAFC",
    borderRadius: 14,
    padding: 14,
    gap: 4,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  metricLabel: {
    color: "#64748B",
    fontSize: 12,
  },
  metricValue: {
    color: "#0F172A",
    fontSize: 20,
    fontWeight: "700",
  },
  listRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    alignItems: "center",
    paddingVertical: 10,
  },
  topicTile: {
    backgroundColor: "#F8FAFC",
    borderRadius: 14,
    padding: 14,
    gap: 6,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  listCopy: {
    flex: 1,
    gap: 4,
  },
  listTitle: {
    color: "#0F172A",
    fontSize: 16,
    fontWeight: "700",
  },
  badge: {
    color: "#2563EB",
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  segmentRow: {
    flexDirection: "row",
    gap: 10,
    backgroundColor: "#F1F5F9",
    borderRadius: 14,
    padding: 6,
  },
  segmentButton: {
    flex: 1,
    borderRadius: 12,
    paddingVertical: 10,
    alignItems: "center",
  },
  segmentActive: {
    backgroundColor: "#FFFFFF",
  },
  segmentLabel: {
    color: "#64748B",
    fontWeight: "700",
  },
  segmentLabelActive: {
    color: "#2563EB",
  },
  errorText: {
    color: "#B91C1C",
  },
  inlineError: {
    color: "#B91C1C",
    backgroundColor: "rgba(239, 68, 68, 0.08)",
    borderWidth: 1,
    borderColor: "rgba(239, 68, 68, 0.18)",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  globalError: {
    color: "#B91C1C",
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  loadingBanner: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    backgroundColor: "#2563EB",
  },
  loadingText: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  suggestionWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  suggestionChip: {
    backgroundColor: "#F8FAFC",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    maxWidth: 280,
  },
  suggestionLabel: {
    color: "#0F172A",
    fontSize: 13,
  },
  previewImage: {
    width: "100%",
    height: 180,
    borderRadius: 16,
  },
  bulletItem: {
    color: "#64748B",
    fontSize: 15,
    lineHeight: 22,
  },
  flashcard: {
    backgroundColor: "#F8FAFC",
    borderRadius: 14,
    padding: 14,
    gap: 6,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  stepRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  stepPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  stepPillActive: {
    backgroundColor: "rgba(37, 99, 235, 0.08)",
    borderColor: "rgba(37, 99, 235, 0.24)",
  },
  stepPillDisabled: {
    opacity: 0.45,
  },
  stepIndex: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    justifyContent: "center",
  },
  stepIndexActive: {
    backgroundColor: "#2563EB",
  },
  stepIndexText: {
    color: "#64748B",
    fontSize: 12,
    fontWeight: "700",
  },
  stepIndexTextActive: {
    color: "#FFFFFF",
  },
  stepLabel: {
    color: "#64748B",
    fontSize: 13,
    fontWeight: "600",
  },
  stepLabelActive: {
    color: "#2563EB",
  },
  scoreHero: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "flex-end",
    gap: 8,
  },
  scoreValue: {
    color: "#0F172A",
    fontSize: 54,
    fontWeight: "700",
    lineHeight: 58,
  },
  scoreMax: {
    color: "#64748B",
    fontSize: 22,
    marginBottom: 6,
  },
  detailsCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: 14,
    padding: 14,
    gap: 8,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
});
