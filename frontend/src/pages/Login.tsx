import { useState } from "react";
import { useAuth } from "../app/AuthProvider";
import { Field, FormError, useSubmit } from "../components/forms";
import { Logo } from "../components/Logo";

export function Login() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [notice, setNotice] = useState("");

  const { onSubmit, pending, error } = useSubmit(async () => {
    if (mode === "sign-in") {
      await signIn(email, password);
    } else {
      await signUp(email, password, fullName);
      setNotice(
        "Account created. If your project requires email confirmation, confirm the message we just sent, then sign in."
      );
      setMode("sign-in");
    }
  });

  return (
    <div className="authShell">
      <div className="authCard">
        <div style={{ marginBottom: 20 }}>
          <Logo size={22} />
          <div className="cardNote" style={{ marginTop: 8 }}>Calm, coordinated incident response</div>
        </div>

        <h1 style={{ marginBottom: 6 }}>
          {mode === "sign-in" ? "Sign in" : "Create an account"}
        </h1>
        <p className="cardNote" style={{ marginBottom: 18 }}>
          {mode === "sign-in"
            ? "Responders sign in to declare incidents, post updates and take actions."
            : "Signing up with a seeded responder's address adopts that person's history."}
        </p>

        <form onSubmit={onSubmit}>
          <FormError message={error} />
          {notice && (
            <div className="notice" style={{ marginBottom: 12 }}>
              {notice}
            </div>
          )}

          {mode === "sign-up" && (
            <Field label="Full name">
              <input
                className="input"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Sam Lee"
                required
              />
            </Field>
          )}

          <Field label="Email">
            <input
              className="input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </Field>

          <Field label="Password" hint={mode === "sign-up" ? "At least six characters." : undefined}>
            <input
              className="input"
              type="password"
              autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
          </Field>

          <button className="btn primary" style={{ width: "100%", justifyContent: "center" }} disabled={pending}>
            {pending ? "Working…" : mode === "sign-in" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p className="cardNote" style={{ marginTop: 16 }}>
          {mode === "sign-in" ? "No account yet?" : "Already have an account?"}{" "}
          <button
            className="linkButton"
            onClick={() => {
              setMode(mode === "sign-in" ? "sign-up" : "sign-in");
              setNotice("");
            }}
          >
            {mode === "sign-in" ? "Create one" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}
