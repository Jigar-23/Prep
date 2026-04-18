import { Exam, Subject, Topic } from "@/lib/types";

export function findExam(catalog: Exam[], examId: string): Exam | undefined {
  return catalog.find((exam) => exam.id === examId);
}

export function findSubject(catalog: Exam[], examId: string, subjectId: string): Subject | undefined {
  return findExam(catalog, examId)?.subjects.find((subject) => subject.id === subjectId);
}

export function findTopic(catalog: Exam[], topicId: string): Topic | undefined {
  for (const exam of catalog) {
    for (const subject of exam.subjects) {
      const topic = subject.topics.find((item) => item.id === topicId);
      if (topic) {
        return topic;
      }
    }
  }
  return undefined;
}

export function buildNameMaps(catalog: Exam[]) {
  const examNames = new Map<string, string>();
  const subjectNames = new Map<string, string>();
  const topicNames = new Map<string, string>();

  for (const exam of catalog) {
    examNames.set(exam.id, exam.name);
    for (const subject of exam.subjects) {
      subjectNames.set(subject.id, subject.name);
      for (const topic of subject.topics) {
        topicNames.set(topic.id, topic.name);
      }
    }
  }

  return { examNames, subjectNames, topicNames };
}
