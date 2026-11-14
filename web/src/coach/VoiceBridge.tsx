import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useEffect } from "react";

export type Conv = ReturnType<typeof useConversation>;

interface Props {
  onConv: (c: Conv) => void;
  onState: (s: { speaking: boolean; muted: boolean }) => void;
}

function Hook({ onConv, onState }: Props) {
  const conv = useConversation();
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
