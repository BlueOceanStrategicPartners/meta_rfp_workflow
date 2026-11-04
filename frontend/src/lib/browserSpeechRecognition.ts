export type BrowserSpeechResult = {
  isFinal: boolean;
  0: { transcript: string };
};

export type BrowserSpeechEvent = {
  resultIndex: number;
  results: BrowserSpeechResult[];
};

export type BrowserSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((ev: BrowserSpeechEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((ev: { error: string }) => void) | null;
  onstart: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

export type BrowserSpeechRecognitionCtor = new () => BrowserSpeechRecognition;

export function getBrowserSpeechRecognitionCtor(): BrowserSpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: BrowserSpeechRecognitionCtor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function browserSpeechRecognitionSupported(): boolean {
  return getBrowserSpeechRecognitionCtor() !== null;
}
