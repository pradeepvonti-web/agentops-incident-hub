import { useEffect, useRef, useState } from "react";

type Msg = { who: string; initials: string; agent?: boolean; text: string; chips?: string[] };

const OPENING: Msg[] = [
  { who: "Restora", initials: "RS", text: "Declared by Alex Moreau. Paging Payments primary. Scribe is taking notes." },
  { who: "Sam Lee", initials: "SL", text: "Checkout failing in all regions. Payments on-call is joining." },
  {
    who: "Agent",
    initials: "◆",
    agent: true,
    text: "Connection pool on payments 4.12.0 exhausted 3 min after the 17:50 deploy. Rolling back is the likely fix. What should I do?",
    chips: ["Roll back", "Draft update", "Show evidence"]
  }
];

const REPLIES: Record<string, Msg[]> = {
  "Roll back": [
    { who: "Priya Raman", initials: "PR", text: "Rolling back now. Status → Fixing." },
    { who: "Agent", initials: "◆", agent: true, text: "Rollback finished at 18:20. Error rate back to 0.1%. Move to Monitoring?", chips: ["Yes, monitor", "Hold"] }
  ],
  "Draft update": [
    {
      who: "Agent",
      initials: "◆",
      agent: true,
      text: "Draft: “Some customers may be unable to complete checkout. We have identified the cause and are rolling back a recent change.” Publish it?",
      chips: ["Publish", "Edit"]
    }
  ],
  "Show evidence": [
    { who: "Agent", initials: "◆", agent: true, text: "18:03:01 ERROR payments connection refused · 18:03:18 CRITICAL checkout health check failed · deploy payments@4.12.0 at 17:50 by Priya.", chips: ["Roll back", "Draft update"] }
  ],
  "Yes, monitor": [{ who: "Restora", initials: "RS", text: "Status changed Fixing → Monitoring. Timeline updated. Next update due in 30 minutes." }],
  Hold: [{ who: "Sam Lee", initials: "SL", text: "Let's watch one more region first." }],
  Publish: [{ who: "Restora", initials: "RS", text: "Published to status.restora.io. 1,204 subscribers notified." }],
  Edit: [{ who: "Alex Moreau", initials: "AM", text: "Softened the wording, publishing in a sec." }]
};

/**
 * The hero's incident channel. Messages type themselves in, and the agent's
 * chips are real buttons: click one and the conversation continues.
 */
export function LiveChannel() {
  const [shown, setShown] = useState<Msg[]>([]);
  const [queue, setQueue] = useState<Msg[]>(OPENING);
  const [status, setStatus] = useState("Investigating");
  const [busy, setBusy] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  // Drain the queue one message at a time with a typing pause.
  useEffect(() => {
    if (!queue.length) {
      setBusy(false);
      return;
    }
    setBusy(true);
    const [next, ...rest] = queue;
    const t = window.setTimeout(() => {
      setShown(s => [...s, next]);
      setQueue(rest);
    }, shown.length === 0 ? 500 : 900);
    return () => window.clearTimeout(t);
  }, [queue, shown.length]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: "smooth" });
  }, [shown]);

  function choose(chip: string, from: number) {
    // Chips on older messages go quiet once they've been used.
    setShown(s => s.map((m, i) => (i === from ? { ...m, chips: undefined } : m)));
    setShown(s => [...s, { who: "You", initials: "You", text: chip }]);
    if (chip === "Roll back") setStatus("Fixing");
    if (chip === "Yes, monitor") setStatus("Monitoring");
    setQueue(REPLIES[chip] ?? []);
  }

  function replay() {
    setShown([]);
    setStatus("Investigating");
    setQueue(OPENING);
  }

  return (
    <div className="mkChannel">
      <div className="mkChannelHead">
        <span className="mkChannelName">#inc-1042-checkout-api-unavailable</span>
        <span className="mkChannelMeta">
          INC-1042 · CRITICAL · <b>{status}</b>
        </span>
      </div>
      <div className="mkChannelBody" ref={bodyRef}>
        {shown.map((m, i) => (
          <div className={`mkMsg${m.agent ? " agent" : ""}${m.who === "You" ? " you" : ""}`} key={i}>
            <span className={`mkAvatar${m.agent ? " orange" : ""}`}>{m.initials}</span>
            <div>
              <strong>{m.who}</strong>
              <p>{m.text}</p>
              {m.chips && !busy && (
                <div className="mkMsgActions">
                  {m.chips.map(c => (
                    <button key={c} onClick={() => choose(c, i)}>
                      {c}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="mkTyping" aria-label="Typing">
            <i /><i /><i />
          </div>
        )}
      </div>
      <div className="mkChannelFoot">
        <span className="cardNote">Try it — the chips are live.</span>
        <button className="linkButton" onClick={replay}>
          Replay
        </button>
      </div>
    </div>
  );
}
