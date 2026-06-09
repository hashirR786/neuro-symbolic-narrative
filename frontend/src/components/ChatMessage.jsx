import React from "react";

/**
 * Renders a single chat message bubble.
 * Parses basic markdown: **bold**, > blockquote, newlines.
 */
function parseContent(content) {
  return content
    .split("\n")
    .map((line, i) => {
      // Blockquote
      if (line.startsWith("> ")) {
        const inner = line.slice(2).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        return (
          <blockquote
            key={i}
            className="border-l-2 pl-3 my-1 text-sm"
            style={{ borderColor: "var(--accent-orange)", color: "var(--text-muted)" }}
            dangerouslySetInnerHTML={{ __html: inner }}
          />
        );
      }
      // Bold text inline
      const parts = line.split(/(\*\*.*?\*\*)/g);
      return (
        <p key={i} className={line === "" ? "mb-2" : "mb-1 leading-relaxed"}>
          {parts.map((part, j) =>
            part.startsWith("**") && part.endsWith("**") ? (
              <strong key={j}>{part.slice(2, -2)}</strong>
            ) : (
              <span key={j}>{part}</span>
            )
          )}
        </p>
      );
    });
}

export default function ChatMessage({ role, content }) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3 mb-4 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 mt-1"
        style={{
          background: isUser ? "var(--accent-blue)" : "var(--bg-hover)",
          border: "1px solid var(--border)",
        }}
      >
        {isUser ? "👤" : "📖"}
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm story-prose ${
          isUser
            ? "rounded-tr-sm"
            : "rounded-tl-sm"
        }`}
        style={{
          background: isUser ? "var(--bg-hover)" : "var(--bg-surface)",
          border: "1px solid var(--border)",
        }}
      >
        {parseContent(content)}
      </div>
    </div>
  );
}
