"use client";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { AppProvider } from "@/lib/store";

function Workspace() {
  return (
    <div style={{ display: "flex", height: "100vh", width: "100%", backgroundColor: "#ffffff" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0 }}>
        <Navbar />
        <ChatPanel />
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AppProvider>
      <Workspace />
    </AppProvider>
  );
}
