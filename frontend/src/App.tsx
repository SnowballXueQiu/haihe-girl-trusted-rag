import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  CircleAlert,
  LoaderCircle,
  RotateCcw,
  Send,
  ShieldCheck,
  Square,
  Volume2,
} from "lucide-react";
import { AvatarStage } from "./components/AvatarStage";
import { CitationPanel } from "./components/CitationPanel";
import { useSpeechPlayer } from "./hooks/useSpeechPlayer";
import type { Citation, FinalPayload, Health } from "./types";

const presets = [
  "泥人张彩塑属于哪类国家级非物质文化遗产？",
  "风筝魏有哪些独特的技艺特点？",
  "为什么衣身只保留海棠与水纹暗纹？",
  "你的黑蓝渐变头发和海河有什么关系？",
  "五大道海棠为什么会出现在你的设计里？",
  "现在海河游船票多少钱？",
];

type Stage = "idle" | "retrieving" | "generating" | "verified" | "refused" | "error";
type SpeechState = "idle" | "loading" | "ready" | "playing" | "error";

export default function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(
    "我是海河少女。问我一段天津文化，我只讲有出处的答案。",
  );
  const [citations, setCitations] = useState<Citation[]>([]);
  const [stage, setStage] = useState<Stage>("idle");
  const [statusLabel, setStatusLabel] = useState("可信模式");
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queryPending, setQueryPending] = useState(false);
  const [speechState, setSpeechState] = useState<SpeechState>("idle");
  const [speechBlob, setSpeechBlob] = useState<Blob | null>(null);
  const [speechToken, setSpeechToken] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const activeControllerRef = useRef<AbortController | null>(null);
  const hasInteractedRef = useRef(false);
  const { level, playing, play, prepare, stop } = useSpeechPlayer();
  const busy = queryPending;
  const systemWorking = busy || speechState === "loading";

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/health", { signal: controller.signal })
      .then((response) => response.json())
      .then((data: Health) => {
        setHealth(data);
        if (hasInteractedRef.current) return;
        setStatusLabel(
          data.demo_ready
            ? "系统就绪"
            : data.status === "index_mismatch"
              ? "索引待重建"
              : data.status === "index_missing"
                ? "知识库待建立"
                : "文字问答就绪",
        );
      })
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        setHealth(null);
        if (!hasInteractedRef.current) setStatusLabel("后端状态不可用");
      });
    return () => controller.abort();
  }, []);

  useEffect(
    () => () => {
      requestIdRef.current += 1;
      activeControllerRef.current?.abort();
    },
    [],
  );

  const statusTone = useMemo(() => {
    if (stage === "error" || stage === "refused") return "warning";
    if (stage === "verified") return "success";
    return "active";
  }, [stage]);

  const isCurrentRequest = (requestId: number, signal?: AbortSignal) =>
    requestIdRef.current === requestId && !signal?.aborted;

  const beginPlayback = async (blob: Blob, requestId: number) => {
    if (!isCurrentRequest(requestId)) return;
    setSpeechState("playing");
    setError(null);
    setStatusLabel("正在播报已核验回答");

    try {
      const result = await play(blob);
      if (!isCurrentRequest(requestId)) return;
      setSpeechState("ready");
      setStatusLabel(
        result === "ended" ? "回答与语音已就绪" : "回答已核验 · 播报已停止",
      );
    } catch {
      if (!isCurrentRequest(requestId)) return;
      setSpeechState("error");
      setError("语音播放失败，请重试。文字回答与引用仍然有效。");
      setStatusLabel("回答已核验 · 语音播放失败");
    }
  };

  const requestSpeech = async (
    token: string,
    requestId: number,
    controller: AbortController,
  ) => {
    if (!isCurrentRequest(requestId, controller.signal)) return;
    setSpeechState("loading");
    setError(null);
    setStatusLabel("回答已核验，正在生成角色语音");

    try {
      const response = await fetch("/api/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speech_token: token }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail ?? "语音服务暂不可用");
      }
      const blob = await response.blob();
      if (!blob.size) throw new Error("语音服务返回了空音频");
      if (!isCurrentRequest(requestId, controller.signal)) return;

      setSpeechBlob(blob);
      setSpeechState("ready");
      void beginPlayback(blob, requestId);
    } catch (cause) {
      if (
        controller.signal.aborted ||
        (cause instanceof DOMException && cause.name === "AbortError") ||
        !isCurrentRequest(requestId)
      ) {
        return;
      }
      const message = cause instanceof Error ? cause.message : "语音服务暂不可用";
      setSpeechState("error");
      setError(
        message.includes("DASHSCOPE_API_KEY")
          ? "语音服务尚未配置。文字回答与引用仍然有效。"
          : `${message}。文字回答与引用仍然有效。`,
      );
      setStatusLabel("回答已核验 · 语音暂不可用");
    }
  };

  const ask = async (nextQuestion: string) => {
    const prompt = nextQuestion.trim();
    if (!prompt) return;
    if (prompt.length > 500) {
      setError("问题不能超过 500 个字符。");
      return;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    activeControllerRef.current?.abort();
    const controller = new AbortController();
    activeControllerRef.current = controller;
    hasInteractedRef.current = true;
    stop();
    prepare();
    setQuestion(prompt);
    setAnswer("");
    setCitations([]);
    setError(null);
    setQueryPending(true);
    setSpeechState("idle");
    setSpeechBlob(null);
    setSpeechToken(null);
    setStage("retrieving");
    setStatusLabel("正在检索可信资料");

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: prompt, session_id: "competition-demo" }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) throw new Error("无法连接可信问答服务");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalPayload: FinalPayload | null = null;

      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          if (!isCurrentRequest(requestId, controller.signal)) return;
          const event = block.match(/^event: (.+)$/m)?.[1];
          const raw = block.match(/^data: (.+)$/m)?.[1];
          if (!event || !raw) continue;
          const data = JSON.parse(raw);
          if (event === "status") {
            setStage(data.stage as Stage);
            setStatusLabel(data.label);
          } else if (event === "evidence") {
            setCitations(data.citations);
          } else if (event === "token") {
            setAnswer((current) => current + data.text);
          } else if (event === "final") {
            finalPayload = data as FinalPayload;
            setAnswer(data.answer);
            setCitations(data.citations);
            setStage(data.refused ? "refused" : "verified");
            setStatusLabel(data.refused ? "证据不足，已拒绝回答" : "证据与引用校验通过");
          } else if (event === "error") {
            throw new Error(data.message);
          }
        }
        if (done) break;
      }

      if (!finalPayload) throw new Error("服务未返回完整的校验结果");
      if (!finalPayload.refused && finalPayload.speech_token) {
        setSpeechToken(finalPayload.speech_token);
        void requestSpeech(finalPayload.speech_token, requestId, controller);
      }
    } catch (cause) {
      if (
        controller.signal.aborted ||
        (cause instanceof DOMException && cause.name === "AbortError") ||
        !isCurrentRequest(requestId)
      ) {
        return;
      }
      const message = cause instanceof Error ? cause.message : "实时服务暂不可用";
      setError(message);
      setStage("error");
      setStatusLabel("服务暂不可用");
    } finally {
      if (isCurrentRequest(requestId)) setQueryPending(false);
    }
  };

  const stopSpeech = () => {
    stop();
    if (stage === "verified") {
      setSpeechState(speechBlob ? "ready" : "idle");
      setStatusLabel("回答已核验 · 播报已停止");
    }
  };

  const retrySpeech = () => {
    const requestId = requestIdRef.current;
    prepare();
    if (speechBlob) {
      void beginPlayback(speechBlob, requestId);
      return;
    }
    if (!speechToken) return;
    const currentController = activeControllerRef.current;
    const controller =
      currentController && !currentController.signal.aborted
        ? currentController
        : new AbortController();
    activeControllerRef.current = controller;
    void requestSpeech(speechToken, requestId, controller);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void ask(question);
  };

  return (
    <main className="app-shell">
      <div className="paper-grain" aria-hidden="true" />
      <header className="site-header">
        <div className="identity">
          <div className="seal" aria-hidden="true">津</div>
          <div>
            <h1>海河少女</h1>
            <p>天津文化数字向导</p>
          </div>
        </div>
        <div className={`trust-status ${statusTone}`}>
          {systemWorking ? <LoaderCircle className="spin" size={16} /> : <ShieldCheck size={16} />}
          <span>{statusLabel}</span>
        </div>
      </header>

      <section className="guide-layout">
        <aside className="guide-stage">
          <div className="stage-title">
            <span>文化向导</span>
            <h2>海河少女</h2>
          </div>
          <div className="stage-frame">
            <div className="stage-backdrop" aria-hidden="true" />
            <AvatarStage speakingLevel={level} vrmExpected={Boolean(health?.vrm_ready)} />
            <div className="water-mark" aria-hidden="true">海河</div>
          </div>
        </aside>

        <section className="conversation-wing">
          <div className="conversation-heading">
            <span>可信文化问答</span>
            <h2>向海河，问天津。</h2>
          </div>

          <div className={`answer-panel ${stage === "refused" ? "is-refusal" : ""}`}>
            <div className="answer-label">
              <span>海河少女 · 答</span>
              {playing && <span className="voice-wave"><i /><i /><i /><i /></span>}
            </div>
            <p>{answer || "正在从资料中寻找可以被证实的答案……"}</p>
            {error && <div className="error-note"><CircleAlert size={15} />{error}</div>}
            <div className="answer-footer">
              <span>
                {stage === "verified"
                  ? "回答已通过证据校验"
                  : stage === "refused"
                    ? "没有证据，不作回答"
                    : busy
                      ? "正在核对证据"
                      : "回答需经证据校验"}
              </span>
              {playing ? (
                <button type="button" className="sound-control" onClick={stopSpeech}><Square size={13} />停止</button>
              ) : speechState === "loading" ? (
                <button type="button" className="sound-control" disabled><LoaderCircle className="spin" size={13} />生成语音</button>
              ) : speechBlob ? (
                <button type="button" className="sound-control" onClick={retrySpeech}>
                  {speechState === "error" ? <RotateCcw size={13} /> : <Volume2 size={13} />}
                  {speechState === "error" ? "重试" : "重播"}
                </button>
              ) : speechState === "error" && speechToken ? (
                <button type="button" className="sound-control" onClick={retrySpeech}><RotateCcw size={13} />重试</button>
              ) : (
                <span className="sound-control passive"><Volume2 size={13} />语音随回答生成</span>
              )}
            </div>
          </div>

          <div className="preset-grid" aria-label="推荐问题">
            {presets.map((item) => (
              <button type="button" key={item} disabled={busy} onClick={() => void ask(item)}>
                {item}
              </button>
            ))}
          </div>

          <form className="question-form" onSubmit={submit}>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="例如：你的服饰为什么采用深青与柔粉？"
              aria-label="输入天津文化问题"
              disabled={busy}
              maxLength={500}
            />
            <button type="submit" disabled={busy || !question.trim()} aria-label="发送问题">
              {busy ? <LoaderCircle className="spin" size={20} /> : <Send size={20} />}
            </button>
          </form>
        </section>
      </section>

      <CitationPanel citations={citations} />
    </main>
  );
}
