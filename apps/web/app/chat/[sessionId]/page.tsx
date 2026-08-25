import ChatSessionClient from "./ChatSessionClient";

export default async function ChatPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <ChatSessionClient sessionId={sessionId} />;
}
