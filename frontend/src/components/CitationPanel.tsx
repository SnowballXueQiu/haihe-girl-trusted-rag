import { BookOpenText, ExternalLink } from "lucide-react";
import type { Citation } from "../types";

export function CitationPanel({ citations }: { citations: Citation[] }) {
  return (
    <section className="citation-panel" aria-label="回答依据">
      <div className="section-kicker">
        <BookOpenText size={15} />
        <span>本轮依据</span>
        <b>{citations.length}</b>
      </div>
      {citations.length === 0 ? (
        <div className="empty-evidence">
          提问后，这里会展示经过校验的原文片段与页码。
        </div>
      ) : (
        <div className="citation-list">
          {citations.map((citation) => (
            <article className="citation-card" key={citation.chunk_id}>
              <div className="citation-meta">
                <span>{citation.publisher}</span>
                {citation.page && <span>第 {citation.page} 页</span>}
              </div>
              <h3>{citation.title}</h3>
              <p>{citation.excerpt.replace(/\u0000/g, "").replace(/\s+/g, " ").trim()}</p>
              {citation.url && (
                <a href={citation.url} target="_blank" rel="noreferrer">
                  查看原文 <ExternalLink size={13} />
                </a>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
