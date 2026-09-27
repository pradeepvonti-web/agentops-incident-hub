import { useEffect, useState } from "react";

type State<T> = { data: T | null; loading: boolean; error: string };

/** Runs a fetcher on mount and whenever deps change, with loading and error state. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): State<T> {
  const [state, setState] = useState<State<T>>({
    data: null,
    loading: true,
    error: ""
  });

  useEffect(() => {
    let live = true;
    setState(s => ({ ...s, loading: true, error: "" }));
    fn()
      .then(data => {
        if (live) setState({ data, loading: false, error: "" });
      })
      .catch(e => {
        if (live)
          setState({
            data: null,
            loading: false,
            error: e instanceof Error ? e.message : "Unable to load"
          });
      });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
