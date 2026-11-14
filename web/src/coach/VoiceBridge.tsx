import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useEffect } from "react";

export type Conv = ReturnType<typeof useConversation>;

interface Props {
  onConv: (c: Conv) => void;
  onState: (s: { speaking: boolean; muted: boolean }) => void;
  onTranscript?: (text: string, final: boolean) => void;
}

function Hook({ onConv, onState, onTranscript }: Props) {
  const conv = useConversation({
    onMessage: (m) => {
      if ((m.role === "user" || m.source === "user") && m.message.trim()) onTranscript?.(m.message.trim(), true);
    },
    // Older SDK builds expose user ASR packets through the raw event callback. Keep a
    // tentative transcript visible when that arrives, then let onMessage replace it.
    onIncomingEvent: (event: unknown) => {
      if (!event || typeof event !== "object") return;
      const e = event as { type?: string; user_transcription_event?: { user_transcript?: string }; user_transcript?: string };
      if (e.type !== "user_transcript") return;
      const text = e.user_transcription_event?.user_transcript || e.user_transcript || "";
      if (text.trim()) onTranscript?.(text.trim(), false);
    },
  });
  useEffect(() => {
    onConv(conv);
  });
  const { isSpeaking, isMuted } = conv;
  useEffect(() => onState({ speaking: isSpeaking, muted: isMuted }), [isSpeaking, isMuted, onState]);
  return null;
}

/** The live voice SDK, loaded only when someone first taps the microphone. */
export default function VoiceBridge(p: Props) {
  return (
    <ConversationProvider>
      <Hook {...p} />
    </ConversationProvider>
  );
}
