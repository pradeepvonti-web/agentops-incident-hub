import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import "../marketing.css";
import { Logo, LogoMark } from "../components/Logo";
import { HeroScene } from "../marketing/HeroScene";
import { LiveChannel } from "../marketing/LiveChannel";
import { Tilt } from "../marketing/Tilt";
import { DemoVideo, DemoModal, LoopVideo } from "../marketing/DemoVideo";
import { useMarketingAnimations, refreshScroll } from "../marketing/animate";

/* ------------------------------------------------------------------ content */

const MENUS: Record<string, { title: string; body: string }[]> = {
  Products: [
    { title: "On-call", body: "Schedules, overrides and escalation paths" },
    { title: "Alerts", body: "Route every signal to the right responder" },
    { title: "Response", body: "One workspace for the whole incident" },
    { title: "Status pages", body: "Keep customers informed without extra work" },
    { title: "Post-incident", body: "Checklists and follow-ups that get done" },
    { title: "Insights", body: "MTTD, MTTR and where incidents come from" }
  ],
  Solutions: [
    { title: "Platform teams", body: "Own reliability across every service" },
    { title: "SRE", body: "Cut toil out of the response loop" },
    { title: "Support", body: "Know what to tell customers, and when" },
    { title: "Leadership", body: "Evidence-only summaries, nothing invented" }
  ],
  Resources: [
    { title: "Documentation", body: "Every endpoint, every rule, every field" },
    { title: "Blog", body: "How we think about incidents" },
    { title: "Changelog", body: "What shipped this week" },
    { title: "Community", body: "Responders helping responders" }
  ],
  Customers: [
    { title: "Customer stories", body: "How teams moved and what changed" },
    { title: "Northwind", body: "Fifteen years of patchwork replaced in ten weeks" },
    { title: "Kestrel", body: "Confidence back in the on-call rota" }
  ]
};

const LOGOS = ["Northwind", "Kestrel", "Meridian", "Lumen", "Talis", "Fernway", "Orbital", "Halcyon"];

const PILLARS = [
  {
    key: "on-call",
    title: "On-call gets the right people in the room",
    body: "Route alerts to the right person every time, automatically. Filters take the noise out, and overrides keep the rota from burning anyone out.",
    link: "Discover On-call",
    to: "/on-call",
    quote: {
      logo: "Kestrel",
      text: "Nobody likes getting paged, but the paging here is painless. You get to the work that matters fast, and the schedule takes care of itself.",
      name: "Brian Scanlan",
      role: "Senior Principal Engineer, Kestrel"
    },
    visual: "schedule"
  },
  {
    key: "investigations",
    title: "Investigations get you a cause in minutes",
    body: "Evidence is gathered from the moment an incident is declared: logs, deployments, the last thing that changed. A structured hypothesis lands before the call does.",
    link: "Discover Investigations",
    to: "/incidents",
    quote: {
      logo: "Lumen",
      text: "Incidents are all hands on deck. The coordination and communication is what we lean on, and getting the channel and the call set up is straightforward.",
      name: "Sabin Roman",
      role: "Engineering Manager, Lumen"
    },
    visual: "timeline"
  },
  {
    key: "response",
    title: "Response lets you fix faster, with fewer people",
    body: "Updates, actions and follow-ups sit beside the metadata that decides who does what. Every change reaches every responder in under a second.",
    link: "Discover Response",
    to: "/incidents",
    quote: {
      logo: "Meridian",
      text: "If you took this away tomorrow we would really struggle. It is foundational to how we run an incident now.",
      name: "Anna Roussanova",
      role: "Engineering Manager, Meridian"
    },
    visual: "board"
  },
  {
    key: "status",
    title: "Status pages keep customers in the loop",
    body: "Component status and customer updates, published from the incident you are already working. Nobody rewrites the same message into a second tool.",
    link: "Discover Status pages",
    to: "/status",
    quote: {
      logo: "Talis",
      text: "Our status page finally matches what is actually going on, because the same person writing the update is the one fixing the problem.",
      name: "Priya Desai",
      role: "Head of Support, Talis"
    },
    visual: "status"
  }
];

const LEDGER = [
  { icon: "▤", text: "Has access to every piece of context your team has ever produced" },
  { icon: "⇉", text: "Reasons across telemetry, deployments, code and incident history" },
  { icon: "◆", text: "Challenges its own conclusions before sharing them with a responder" },
  { icon: "↗", text: "Gets sharper with every incident as repeating patterns are learned" }
];

const STORIES = [
  {
    company: "Northwind",
    title: "How Northwind replaced fifteen years of patchwork tooling in ten weeks",
    link: "See how Northwind runs incidents",
    tint: "#f1ebe2"
  },
  {
    company: "Kestrel",
    title: "How Kestrel got confidence back in its incident response",
    link: "See how Kestrel runs incidents",
    tint: "#e8eef2"
  },
  {
    company: "Meridian",
    title: "How Meridian cut hours of manual process out of every incident",
    link: "See how Meridian runs incidents",
    tint: "#efe9f3"
  }
];

/* ------------------------------------------------------------------ page */

export function Landing() {
  const [banner, setBanner] = useState(true);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [mode, setMode] = useState<"problem" | "solution">("problem");
  const [demoOpen, setDemoOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useMarketingAnimations(root);
  useEffect(() => {
    refreshScroll();
  }, [mode]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpenMenu(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="mk" ref={root}>
      {banner && (
        <div className="mkAnnounce">
          <span>Join us at the reliability summit</span>
          <span className="mkAnnounceBadge">RS/26</span>
          <span className="mkAnnounceMeta">
            <b>LDN</b> 23 days
          </span>
          <span className="mkAnnounceMeta">
            <b>SF</b> 30 days
          </span>
          <Link to="/login" className="mkAnnounceArrow" aria-label="Register">
            →
          </Link>
          <button className="mkAnnounceClose" onClick={() => setBanner(false)} aria-label="Dismiss">
            ✕
          </button>
        </div>
      )}

      <header className="mkNav" onMouseLeave={() => setOpenMenu(null)}>
        <div className="mkNavInner">
          <Link to="/" className="mkBrand" aria-label="Restora home">
            <Logo size={19} />
          </Link>

          <nav className="mkLinks">
            {Object.keys(MENUS).map(label => (
              <div
                key={label}
                className="mkMenuWrap"
                onMouseEnter={() => setOpenMenu(label)}
              >
                <button
                  className={openMenu === label ? "mkLink open" : "mkLink"}
                  aria-haspopup="true"
                  aria-expanded={openMenu === label}
                  onClick={() => setOpenMenu(openMenu === label ? null : label)}
                >
                  {label}
                  <span className="chev" />
                </button>
                {openMenu === label && (
                  <div className="mkMenu">
                    {MENUS[label].map(item => (
                      <Link key={item.title} to="/login" className="mkMenuItem">
                        <strong>{item.title}</strong>
                        <span>{item.body}</span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <Link to="/login" className="mkLink">
              Pricing
            </Link>
          </nav>

          <div className="mkNavActions">
            <Link to="/login" className="mkLink">
              Log in
            </Link>
            <Link to="/login" className="mkBtn primary">
              Get a demo
            </Link>
            <Link to="/login" className="mkBtn chip">
              Get started for free
            </Link>
          </div>
        </div>
      </header>

      <main className="mkMain">
        {/* ------------------------------------------------------- hero */}
        <section className="mkHero">
          <HeroScene />
          <h1 aria-label="Run every incident like your best one">
            {["Run", "every", "incident"].map(w => (
              <span className="mkWord" key={w}>
                <span data-hero-word>{w}</span>
              </span>
            ))}
            <br />
            {["like", "your", "best", "one"].map(w => (
              <span className="mkWord" key={w}>
                <span data-hero-word>{w}</span>
              </span>
            ))}
          </h1>
          <p className="mkLead" data-hero>
            The incident platform built to detect, respond and learn, with an agent that
            understands your systems and the people who run them.
          </p>
          <div className="mkCtas" data-hero>
            <button className="mkBtn primary lg" onClick={() => setDemoOpen(true)}>
              <span className="mkPlayIcon">▶</span> Watch the demo
            </button>
            <Link to="/login" className="mkBtn chip lg">
              Get started for free
            </Link>
          </div>

          <div className="mkStage" data-stage>
            <div className="mkStageGlow" aria-hidden="true" />
            <Tilt max={4}>
              <HeroComposite />
            </Tilt>
          </div>

          <ul className="mkStats" data-reveal="stagger">
            <li>
              <strong data-count="4" data-suffix="m">0</strong>
              <span>median time to declare</span>
            </li>
            <li>
              <strong data-count="36" data-suffix="m">0</strong>
              <span>median time to fix</span>
            </li>
            <li>
              <strong data-count="1204">0</strong>
              <span>status subscribers notified per update</span>
            </li>
            <li>
              <strong data-count="100" data-suffix="%">0</strong>
              <span>of status changes on the timeline, written by trigger</span>
            </li>
          </ul>
        </section>

        <DemoVideo onExpand={() => setDemoOpen(true)} />

        {/* ------------------------------------------------------ logos */}
        <section className="mkLogos" aria-label="Customers">
          <div className="mkLogoTrack" data-marquee>
            {[...LOGOS, ...LOGOS].map((name, i) => (
              <span key={`${name}-${i}`} className="mkLogo">
                {name}
              </span>
            ))}
          </div>
        </section>

        {/* ------------------------------------------------- case study */}
        <section className="mkCase" data-reveal>
          <div className="mkCaseCopy">
            <div className="mkCaseBrands">
              <span className="mkLogo">Northwind</span>
              <span className="mkX">×</span>
              <span className="mkBrand sm">
                <Logo size={15} />
              </span>
            </div>
            <h2>How Northwind replaced fifteen years of patchwork tooling in ten weeks</h2>
            <p className="mkMuted">
              With Restora, Northwind modernised incident response across 1,200 engineers and
              strengthened reliability company-wide.
            </p>
            <blockquote>
              “If you took this away tomorrow, we'd really struggle. It's foundational to how
              we respond now.”
            </blockquote>
            <p className="mkAuthor">
              Anna Roussanova <span>Engineering Manager</span>
            </p>
            <div className="mkCaseLinks">
              <Link to="/login" className="mkTextLink">
                Read their story →
              </Link>
              <Link to="/login" className="mkTextLink">
                Watch video <span className="mkDur">3:47</span>
              </Link>
            </div>
          </div>
          <div className="mkCaseMedia" aria-hidden="true">
            <div className="mkCasePhoto">
              <span className="mkPlay">▶ Watch video</span>
            </div>
          </div>
        </section>

        {/* -------------------------------------------- problem / solution */}
        <section className="mkToggleSection" data-reveal>
          <div className="mkToggle" role="tablist">
            <button
              role="tab"
              aria-selected={mode === "problem"}
              className={mode === "problem" ? "on" : undefined}
              onClick={() => setMode("problem")}
            >
              Problem
            </button>
            <button
              role="tab"
              aria-selected={mode === "solution"}
              className={mode === "solution" ? "on" : undefined}
              onClick={() => setMode("solution")}
            >
              Solution
            </button>
          </div>

          {mode === "problem" ? (
            <>
              <h2>Incidents are slowing you down</h2>
              <p className="mkLead">
                The real cost of an incident isn't the downtime. It's the engineers who dropped
                everything, the customers who noticed, and the roadmap that slipped again. The
                teams that win break the cycle.
              </p>
              <Chaos />
            </>
          ) : (
            <>
              <h2>Humans and agents, working in lockstep</h2>
              <p className="mkLead">
                One system supports a responder and an agent working together, from the moment
                an alert fires all the way through to the follow-ups getting done.
              </p>
              <Lockstep />
            </>
          )}
        </section>

        {/* ---------------------------------------------------- platform */}
        <section className="mkPlatform" data-reveal>
          <h2 className="mkDisplay">
            Meet the platform keeping
            <br />
            your software running
          </h2>
          <PlatformDiagram />
        </section>

        {/* ------------------------------------------------------ ledger */}
        <section className="mkLedger">
          <div className="mkLedgerInner">
            <h2>Built on the Ledger</h2>
            <p>
              The Ledger is a living model of your production environment, built from your
              incidents, your systems and your team.
            </p>
            <Link to="/login" className="mkBtn chip">
              Learn more about the Ledger
            </Link>
            <div className="mkLedgerGrid" data-reveal="stagger">
              {LEDGER.map(item => (
                <div className="mkLedgerCard" key={item.text}>
                  <span className="mkLedgerIcon">{item.icon}</span>
                  <p>{item.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------- pillars */}
        <section className="mkPillars">
          <h2 className="mkDisplay md">From first alert to final fix</h2>
          <p className="mkLead">
            On-call, investigations, incident response and status pages, built to work as one
            system rather than four tools.
          </p>

          {PILLARS.map(p => (
            <article className="mkPillar" key={p.key} data-reveal>
              <div className="mkPillarHead">
                <h3>{p.title}</h3>
                <p>{p.body}</p>
                <Link to={p.to} className="mkDiscover">
                  {p.link} →
                </Link>
              </div>
              <div className="mkPillarBody">
                <Tilt max={5}>
                <figure className="mkQuoteCard">
                  <div className="mkQuoteTop">
                    <span className="mkLogo">{p.quote.logo}</span>
                    <span className="mkExt">↗</span>
                  </div>
                  <blockquote>“{p.quote.text}”</blockquote>
                  <figcaption>
                    <strong>{p.quote.name}</strong>
                    <span>{p.quote.role}</span>
                  </figcaption>
                </figure>
                </Tilt>
                <div className="mkVisual" data-float>
                  <PillarVisual kind={p.visual} />
                </div>
              </div>
            </article>
          ))}
        </section>

        {/* ------------------------------------------------------- event */}
        <section className="mkEvent" data-reveal>
          <div className="mkEventArt" aria-hidden="true">
            <span className="mkEventBadge">RS/26</span>
            <span className="mkEventLine">Don't miss out!</span>
          </div>
          <div className="mkEventCopy">
            <span className="mkPillOrange">RS/26</span>
            <h2>The reliability summit</h2>
            <p className="mkMuted">
              A day of candid, practitioner-led conversations on what it actually takes to
              build and operate reliable systems at scale.
            </p>
            <ul className="mkEventMeta">
              <li>
                <span>▦</span> October 20 <span>⌾</span> London
              </li>
              <li>
                <span>▦</span> October 27 <span>⌾</span> San Francisco
              </li>
            </ul>
            <Link to="/login" className="mkBtn primary">
              Get a ticket
            </Link>
          </div>
        </section>

        {/* ---------------------------------------------------- stories */}
        <section className="mkStories">
          <div className="mkStars" aria-label="Rated five stars">
            <span className="mkG">G</span> ★★★★★
          </div>
          <h2>
            Built for teams where
            <br />
            downtime isn't an option
          </h2>
          <Link to="/login" className="mkBtn chip">
            Read all customer stories
          </Link>
          <div className="mkStoryRow" data-reveal="stagger">
            {STORIES.map(s => (
              <Tilt key={s.company} max={5}>
              <article className="mkStory">
                <div className="mkStoryMedia" style={{ background: s.tint }}>
                  <span className="mkPlay">▶ Watch video</span>
                </div>
                <h3>{s.title}</h3>
                <Link to="/login" className="mkTextLink accent">
                  {s.link}
                </Link>
              </article>
              </Tilt>
            ))}
          </div>
        </section>
      </main>

      {demoOpen && <DemoModal onClose={() => setDemoOpen(false)} />}

      {/* ------------------------------------------------ closer + footer */}
      <section className="mkCloser">
        <div className="mkCloserInner" data-reveal>
          <h2 className="mkDisplay">
            So good, you'll break
            <br />
            things on purpose
          </h2>
          <p>
            Ready to put an agent to work on your incidents?
            <br />
            Book a call with our team today.
          </p>
          <div className="mkCtas">
            <Link to="/login" className="mkBtn chip lg">
              Talk to an expert
            </Link>
            <Link to="/login" className="mkBtn chip lg">
              Get started for free
            </Link>
          </div>
        </div>

        <footer className="mkFoot">
          <div className="mkFootBrand">
            <Logo size={19} tone="light" />
            <div className="mkSocial">
              {["◐", "in", "𝕏", "◉", "f", "▶", "#"].map((s, i) => (
                <span key={i}>{s}</span>
              ))}
            </div>
            <p>© 2026 Restora. All rights reserved.</p>
          </div>
          <div className="mkFootCols">
            <div>
              <h4>Product</h4>
              {["On-call", "Investigations", "Incident response", "Status pages", "Changelog"].map(t => (
                <Link key={t} to="/login">
                  {t}
                </Link>
              ))}
            </div>
            <div>
              <h4>Learn</h4>
              {["Blog", "Customer stories", "Documentation", "Alternatives", "Community"].map(t => (
                <Link key={t} to="/login">
                  {t}
                </Link>
              ))}
            </div>
            <div>
              <h4>Company</h4>
              {["Legal", "Privacy choices", "Security and compliance", "Careers"].map(t => (
                <Link key={t} to="/login">
                  {t}
                </Link>
              ))}
              <Link to="/status">Status</Link>
            </div>
          </div>
        </footer>
      </section>
    </div>
  );
}

/* --------------------------------------------------------------- visuals */

/** The hero: an incident channel beside the live board, on the oat stage. */
function HeroComposite() {
  return (
    <div className="mkComposite">
      <LiveChannel />

      <LoopVideo
        className="mkAppShot video"
        src="restora-demo"
        label="The Restora workspace, live"
      />
    </div>
  );
}

function Chaos() {
  const nodes = [
    ["Fetched the failing PR", "#4410"],
    ["Rolled back deploy", "#89237"],
    ["Fix drafted", "PR opened"],
    ["Status page updated", ""]
  ];
  return (
    <div className="mkDiagram">
      <div className="mkDiagramCenter">All systems operational</div>
      <div className="mkDiagramRow">
        {nodes.map(([t, m]) => (
          <div className="mkDiagramNode" key={t}>
            <span className="dot" />
            <div>
              <em>Resolved</em>
              <strong>{t}</strong>
              {m && <span>{m}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Lockstep() {
  return (
    <div className="mkDiagram">
      <div className="mkDiagramRow lock">
        {["Alert fires", "Agent investigates", "Responder decides", "Fix ships", "Follow-ups done"].map(
          (t, i) => (
            <div className="mkDiagramStep" key={t}>
              <span className={i % 2 ? "who human" : "who agent"}>{i % 2 ? "Human" : "Agent"}</span>
              <strong>{t}</strong>
            </div>
          )
        )}
      </div>
    </div>
  );
}

function PlatformDiagram() {
  return (
    <div className="mkPlat">
      <div className="mkPlatCol">
        <span className="mkPlatLabel">Interfaces</span>
        <div className="mkPlatAgent">
          <span className="mkPlatAgentIcon">◆</span>
          <strong>Restora agent</strong>
          {["Web", "Slack", "MCP", "API", "Mobile", "CLI"].map(t => (
            <span key={t} className="mkPlatChip">
              {t}
            </span>
          ))}
        </div>
      </div>
      <span className="mkPlatArrow">→</span>
      <div className="mkPlatCol">
        <span className="mkPlatLabel">Core products</span>
        <div className="mkPlatList">
          {["On-call", "Investigations", "Response", "Status pages"].map(t => (
            <span key={t}>
              <i />
              {t}
            </span>
          ))}
        </div>
        <span className="mkPlatLabel">Operational layer</span>
        <div className="mkPlatList tight">
          {["Integrations", "Policies", "Insights", "Workflows"].map(t => (
            <span key={t}>
              <i />
              {t}
            </span>
          ))}
        </div>
      </div>
      <span className="mkPlatArrow">→</span>
      <div className="mkPlatCol">
        <span className="mkPlatLabel">The Ledger</span>
        <div className="mkPlatSources">
          {["Incidents", "Runbooks", "Catalog", "Deployments", "Logs", "Metrics", "Pull requests", "Your docs", "Telemetry"].map(
            t => (
              <span key={t}>{t}</span>
            )
          )}
        </div>
        <p className="mkPlatNote">Production intelligence model</p>
      </div>
    </div>
  );
}

function PillarVisual({ kind }: { kind: string }) {
  const clip = { schedule: "clip-oncall", timeline: "clip-investigate", status: "clip-status" }[kind];
  if (clip) {
    return (
      <div className="mkVis">
        <LoopVideo className="mkClip" src={clip} label={`${kind} walkthrough`} />
      </div>
    );
  }
  if (kind === "schedule") {
    return (
      <div className="mkVis">
        <span className="mkVisTag">Cover requests</span>
        <div className="mkSched">
          <div className="mkSchedHead">
            <span />
            <span>Mon 27</span>
            <span className="now">10:29</span>
            <span>21:00</span>
            <span>Tue 28</span>
          </div>
          {[
            ["EUR", "Mike Smith", 0, 38, "a"],
            ["AMER", "Jenny Wicks", 30, 40, "b"],
            ["APAC", "Mark Dean", 62, 28, "c"]
          ].map(([r, n, l, w, c]) => (
            <div className="mkSchedRow" key={r as string}>
              <span className="mkSchedLabel">{r}</span>
              <span
                className={`mkSchedBar ${c}`}
                style={{ left: `${l}%`, width: `${w}%` }}
              >
                {n}
              </span>
            </div>
          ))}
        </div>
        <span className="mkVisTag bottom">Follow the ☀</span>
      </div>
    );
  }
  if (kind === "timeline") {
    return (
      <div className="mkVis">
        <div className="mkTl">
          {[
            ["17:20", "Alert fired: search p95 above threshold"],
            ["17:26", "Incident declared at ERROR"],
            ["17:44", "Cause identified: query-expansion flag"],
            ["18:05", "Status changed from Fixing to Monitoring"]
          ].map(([t, s]) => (
            <div key={t} className="mkTlRow">
              <span className="mono">{t}</span>
              <i />
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (kind === "board") {
    return (
      <div className="mkVis">
        <div className="mkMini">
          <div className="mkMiniHead">
            <span>INC-1042 Checkout API unavailable</span>
            <span className="badge badge-critical">CRITICAL</span>
          </div>
          <div className="mkMiniTabs">
            {["Updates", "Timeline", "Actions", "Follow-ups"].map((t, i) => (
              <span key={t} className={i === 2 ? "on" : undefined}>
                {t}
              </span>
            ))}
          </div>
          {[
            ["Roll back payments 4.12.0", "Priya Raman", false],
            ["Drain checkout pods in eu-west", "Sam Lee", false],
            ["Post customer-facing status update", "Alex Moreau", true]
          ].map(([t, o, d]) => (
            <div key={t as string} className="mkMiniRow">
              <span className={`check${d ? " on" : ""}`}>✓</span>
              <span className={d ? "strike" : undefined}>{t}</span>
              <span className="mkMiniOwner">{o}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="mkVis">
      <div className="mkStatusStack">
        <div className="mkStatusCard back2" />
        <div className="mkStatusCard back1" />
        <div className="mkStatusCard">
          <div className="mkStatusHead">
            <span className="mkLogo">Northwind</span>
            <span>Subscribe to updates</span>
          </div>
          <div className="mkStatusOk">✓ We're fully operational</div>
          <div className="mkStatusRows">
            {["Checkout", "Search", "Identity"].map(c => (
              <span key={c}>
                <i />
                {c}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
