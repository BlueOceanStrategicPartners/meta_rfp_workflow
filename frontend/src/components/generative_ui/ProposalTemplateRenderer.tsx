import DOMPurify from "dompurify";

type Props = { html: string; css?: string };

export default function ProposalTemplateRenderer({ html, css = "" }: Props) {
  const safe = DOMPurify.sanitize(html);
  return (
    <div className="fixed inset-0 z-50 bg-black/80 overflow-auto p-8">
      {css && <style>{css}</style>}
      <div className="max-w-4xl mx-auto bg-white text-black rounded-xl p-6" dangerouslySetInnerHTML={{ __html: safe }} />
    </div>
  );
}
