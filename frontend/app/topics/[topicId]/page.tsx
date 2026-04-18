import { redirect } from "next/navigation";

export default async function LegacyTopicRedirectPage({ params }: { params: Promise<{ topicId: string }> }) {
  const { topicId } = await params;
  redirect(`/topic/${topicId}`);
}
