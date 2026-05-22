import "@fontsource-variable/inter";
import "@fontsource/geist-mono/400.css";
import "./globals.css";

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { WorkbenchProvider } from "./context/V3WorkbenchContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <WorkbenchProvider>
          <App />
        </WorkbenchProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
