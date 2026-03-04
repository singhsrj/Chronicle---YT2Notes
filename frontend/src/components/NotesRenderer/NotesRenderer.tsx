import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import './NotesRenderer.css';
import { sanitizeNotes } from '../../utils/sanitizeLatex';

interface NotesRendererProps {
  content: string;
  isStreaming?: boolean;
}

/**
 * Renders markdown notes with LaTeX math support.
 * Supports both inline ($...$) and block ($$...$$) math equations.
 * Uses sanitizeLatex for deterministic regex-based LaTeX preprocessing.
 */
export function NotesRenderer({ content, isStreaming = false }: NotesRendererProps) {
  if (!content) {
    return (
      <div className="notes-empty">
        <p>No notes to display</p>
      </div>
    );
  }

  // Sanitize content: clean XML tags + fix LaTeX delimiters
  const cleanedContent = sanitizeNotes(content);

  return (
    <div className="notes-renderer">
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Custom heading styles
          h1: ({ children }) => <h1 className="notes-h1">{children}</h1>,
          h2: ({ children }) => <h2 className="notes-h2">{children}</h2>,
          h3: ({ children }) => <h3 className="notes-h3">{children}</h3>,
          h4: ({ children }) => <h4 className="notes-h4">{children}</h4>,
          
          // Custom paragraph
          p: ({ children }) => <p className="notes-p">{children}</p>,
          
          // Custom lists
          ul: ({ children }) => <ul className="notes-ul">{children}</ul>,
          ol: ({ children }) => <ol className="notes-ol">{children}</ol>,
          li: ({ children }) => <li className="notes-li">{children}</li>,
          
          // Custom emphasis
          strong: ({ children }) => <strong className="notes-strong">{children}</strong>,
          em: ({ children }) => <em className="notes-em">{children}</em>,
          
          // Custom code blocks
          code: ({ className, children, ...props }) => {
            const isInline = !className;
            if (isInline) {
              return <code className="notes-code-inline" {...props}>{children}</code>;
            }
            return (
              <code className={`notes-code-block ${className || ''}`} {...props}>
                {children}
              </code>
            );
          },
          
          pre: ({ children }) => <pre className="notes-pre">{children}</pre>,
          
          // Custom blockquote
          blockquote: ({ children }) => (
            <blockquote className="notes-blockquote">{children}</blockquote>
          ),
          
          // Custom horizontal rule
          hr: () => <hr className="notes-hr" />,
          
          // Custom table
          table: ({ children }) => (
            <div className="notes-table-wrapper">
              <table className="notes-table">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="notes-th">{children}</th>,
          td: ({ children }) => <td className="notes-td">{children}</td>,
        }}
      >
        {cleanedContent}
      </ReactMarkdown>
      
      {isStreaming && <span className="notes-cursor">▊</span>}
    </div>
  );
}

export default NotesRenderer;
