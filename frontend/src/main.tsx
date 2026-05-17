import "@fontsource-variable/inter";
import "@fontsource/geist-mono/400.css";
import "./globals.css";

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { WorkbenchProvider } from "./context/V3WorkbenchContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <WorkbenchProvider>
        <App />
      </WorkbenchProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
