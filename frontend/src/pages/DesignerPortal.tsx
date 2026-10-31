import { useState } from "react";

export default function DesignerPortal() {
  const [html, setHtml] = useState("");
  const [preview, setPreview] = useState("");

  const generate = async () => {
    const res = await fetch("/api/designer/chat/", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction: "luxury dark template" }),
    });
    const data = await res.json();
    setHtml(data.html_markup || "");
    setPreview(data.html_markup || "");
  };

  return (
    <div className="min-h-screen pt-16 p-6 grid md:grid-cols-2 gap-4">
      <section className="space-y-3">
        <h1 className="text-2xl">Designer Studio</h1>
        <button type="button" onClick={generate} className="px-4 py-2 rounded bg-violet-600">
          AI Generate Template
        </button>
        <textarea
          className="w-full h-64 bg-black/40 rounded p-3 font-mono text-xs"
          value={html}
          onChange={(e) => setHtml(e.target.value)}
        />
      </section>
      <section className="bg-white text-black rounded-xl p-4 overflow-auto">
        <h2 className="text-lg mb-2">Live Preview</h2>
        <div dangerouslySetInnerHTML={{ __html: preview }} />
      </section>
    </div>
  );
}
