import "@fontsource-variable/inter";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./styles/index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { api } from "@/api";
import { tokenStore } from "@/auth/tokenStore";

import { App } from "./app/App";
import { createQueryClient } from "./app/queryClient";

const root = document.getElementById("root");
if (root === null) throw new Error("Missing #root element.");

createRoot(root).render(
  <StrictMode>
    <App client={api} store={tokenStore} queryClient={createQueryClient()} />
  </StrictMode>,
);
