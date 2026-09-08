import { createContext, useContext } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import type { Snapshot } from "../types/api";

export interface InstanceContextValue {
  name: string;
  query: UseQueryResult<Snapshot, Error>;
}

const InstanceContext = createContext<InstanceContextValue | null>(null);

export const InstanceContextProvider = InstanceContext.Provider;

export function useInstanceContext(): InstanceContextValue {
  const ctx = useContext(InstanceContext);
  if (!ctx) {
    throw new Error("useInstanceContext must be used within an InstanceLayout route");
  }
  return ctx;
}
