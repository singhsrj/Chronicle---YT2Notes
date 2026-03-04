/**
 * sanitizeLatex.ts  v4
 *
 * Fixes:
 *  - Multiline \begin{bmatrix}...\end{bmatrix} blocks
 *  - $$$$ → $$  (double-wrapping artifact)
 *  - $$ inside already-$$ blocks (nested delimiter bug)
 *  - Display math on own lines (required for remark-math)
 *  - **$$ adjacency issues
 *  - Inline math containing matrices → display math
 *  - All previous delimiter normalization
 */

/**
 * Step 0 — Convert inline math containing matrices to display math
 * Matrices should never be in inline $...$ mode
 */
function promoteMatrixToDisplay(text: string): string {
  // Match $...$ containing \begin{bmatrix/pmatrix/vmatrix} and convert to $$...$$
  // This handles: $X_1 = \begin{bmatrix} 0 \ 1 \end{bmatrix} $
  let out = text.replace(
    /\$([^$]*\\begin\{(?:bmatrix|pmatrix|vmatrix|matrix)\}[\s\S]*?\\end\{(?:bmatrix|pmatrix|vmatrix|matrix)\}[^$]*)\$/g,
    (_: string, inner: string) => `\n$$${inner.trim()}$$\n`
  );

  // Fix matrix line breaks: `\ ` (backslash space) should be `\\` (double backslash)
  // Inside matrix environments
  out = out.replace(
    /(\\begin\{(?:bmatrix|pmatrix|vmatrix|matrix)\})([\s\S]*?)(\\end\{(?:bmatrix|pmatrix|vmatrix|matrix)\})/g,
    (_: string, begin: string, inner: string, end: string) => {
      // Replace `\ ` or `\` at end of content segments with `\\`
      const fixedInner = inner.replace(/\\\s+(?=\d|\\|[a-zA-Z])/g, '\\\\ ');
      return `${begin}${fixedInner}${end}`;
    }
  );

  return out;
}

/**
 * Step 1 — Deduplicate stacked $$ signs produced by double-wrapping.
 * e.g.  $$$$...$$$$  or  $$$...$$$  → $$...$$
 */
function deduplicateDollars(text: string): string {
  // Collapse 3 or 4 consecutive $ into exactly 2
  return text.replace(/\${3,4}/g, "$$");
}

/**
 * Step 2 — Extract and protect all already-valid $...$ and $$...$$ blocks
 * so later regexes don't accidentally re-process them.
 * Returns { text, blocks } where blocks is a Map of placeholder → original.
 */
function protectExistingMath(text: string): { text: string; blocks: Map<string, string> } {
  const blocks = new Map<string, string>();
  let idx = 0;

  // Protect display math first ($$...$$), then inline ($...$)
  const protected_ = text
    // $$...$$ — display (multiline safe)
    .replace(/\$\$([\s\S]*?)\$\$/g, (match) => {
      const key = `\x00MATH_DISPLAY_${idx++}\x00`;
      blocks.set(key, match);
      return key;
    })
    // $...$ — inline (single line only, avoid false positives)
    // Skip if contains \begin{ (should be display math)
    .replace(/\$([^\n$]+?)\$/g, (match, inner) => {
      // Don't protect if it contains matrix commands - let normalizeDelimiters handle it
      if (/\\begin\{/.test(inner)) {
        return match;
      }
      const key = `\x00MATH_INLINE_${idx++}\x00`;
      blocks.set(key, match);
      return key;
    });

  return { text: protected_, blocks };
}

/** Step 3 — Restore protected blocks */
function restoreMath(text: string, blocks: Map<string, string>): string {
  let out = text;
  for (const [key, val] of blocks) {
    out = out.replace(key, val);
  }
  return out;
}

/**
 * Step 4 — Normalize unprotected (malformed) delimiters
 */
function normalizeDelimiters(text: string): string {
  let out = text;

  // \[ ... \]  →  $$...$$ on own line
  out = out.replace(/\\\[\s*([\s\S]*?)\s*\\\]/g, (_: string, inner: string) => `\n$$${inner.trim()}$$\n`);

  // \( ... \)  →  $...$
  out = out.replace(/\\\(\s*([\s\S]*?)\s*\\\)/g, (_: string, inner: string) => `$${inner.trim()}$`);

  // \begin{equation}...\end{equation}  →  $$...$$ on own line
  out = out.replace(
    /\\begin\{equation\*?\}([\s\S]*?)\\end\{equation\*?\}/g,
    (_: string, inner: string) => `\n$$${inner.trim()}$$\n`
  );

  // \begin{align}...\end{align}  →  $$...$$ on own line
  out = out.replace(
    /\\begin\{align\*?\}([\s\S]*?)\\end\{align\*?\}/g,
    (_: string, inner: string) => `\n$$${inner.trim()}$$\n`
  );

  // \begin{bmatrix}...\end{bmatrix}  →  $$\begin{bmatrix}...\end{bmatrix}$$ on own line
  out = out.replace(
    /\\begin\{bmatrix\}([\s\S]*?)\\end\{bmatrix\}/g,
    (_: string, inner: string) => `\n$$\\begin{bmatrix}${inner}\\end{bmatrix}$$\n`
  );

  // \begin{pmatrix}...\end{pmatrix}  →  $$\begin{pmatrix}...\end{pmatrix}$$ on own line
  out = out.replace(
    /\\begin\{pmatrix\}([\s\S]*?)\\end\{pmatrix\}/g,
    (_: string, inner: string) => `\n$$\\begin{pmatrix}${inner}\\end{pmatrix}$$\n`
  );

  // \begin{vmatrix}...\end{vmatrix}  →  $$\begin{vmatrix}...\end{vmatrix}$$ on own line
  out = out.replace(
    /\\begin\{vmatrix\}([\s\S]*?)\\end\{vmatrix\}/g,
    (_: string, inner: string) => `\n$$\\begin{vmatrix}${inner}\\end{vmatrix}$$\n`
  );

  // ( \latexCommand ... )  →  $...$
  // Only when content starts with backslash (LaTeX command)
  // Be more conservative - don't match if inner contains newlines or looks like prose
  out = out.replace(/\(\s*(\\[a-zA-Z][^()\n]*?)\s*\)/g, (_: string, inner: string) => `$${inner.trim()}$`);

  // Remove stray trailing backslash at end of any line
  out = out.replace(/\\\s*$/gm, "");

  return out;
}

/**
 * Step 5 — Ensure display math is properly separated
 * remark-math requires $$ to be on its own line or properly spaced
 */
function fixDisplayMathSpacing(text: string): string {
  let out = text;

  // Fix **$$ → ** \n$$ (bold before display math needs line break)
  out = out.replace(/\*\*\s*\$\$/g, "**\n$$");
  
  // Fix $$** → $$ \n** (display math before bold needs line break)
  out = out.replace(/\$\$\s*\*\*/g, "$$\n**");

  // Ensure display math has line breaks before and after if inline with text
  // Match $$ that's not at start of line and not preceded by newline
  out = out.replace(/([^\n])\$\$([^$])/g, "$1\n$$\n$2");
  
  // Match $$ at end that's not followed by newline
  out = out.replace(/\$\$([^\n$])/g, "$$\n$1");

  // Clean up excessive newlines
  out = out.replace(/\n{3,}/g, "\n\n");

  return out;
}

/**
 * Step 6 — Fix common LLM output patterns that break KaTeX
 */
function fixCommonPatterns(text: string): string {
  let out = text;

  // Fix $ \Sigma $ with spaces → $\Sigma$
  out = out.replace(/\$\s+([^$]+?)\s+\$/g, (_: string, inner: string) => `$${inner.trim()}$`);

  // Fix single $ at end of line that might be unclosed
  // Only if it's not part of $$
  out = out.replace(/([^$])\$\s*$/gm, "$1");

  // Fix - **$ pattern (list item with bold math) - ensure space
  out = out.replace(/^(\s*-\s*)\*\*\$/gm, "$1**$");

  return out;
}

/**
 * Main export — call this on raw LLM notes before rendering.
 * Works in parallel with streaming - just call on each chunk.
 *
 * @param text - Raw notes string from Ollama / your API
 * @returns Cleaned string ready for KaTeX / ReactMarkdown+remarkMath
 */
export function sanitizeLatex(text: string): string {
  // Round 0: promote inline math containing matrices to display math
  let out = promoteMatrixToDisplay(text);

  // Round 1: collapse any $$$$
  out = deduplicateDollars(out);

  // Round 2: protect already-valid math blocks
  const { text: protected_, blocks } = protectExistingMath(out);

  // Round 3: fix everything outside the protected blocks
  const normalized = normalizeDelimiters(protected_);

  // Round 4: restore protected blocks
  out = restoreMath(normalized, blocks);

  // Round 5: one more dedup pass in case normalization created new $$$$
  out = deduplicateDollars(out);

  // Round 6: fix display math spacing for remark-math compatibility
  out = fixDisplayMathSpacing(out);

  // Round 7: fix common LLM patterns
  out = fixCommonPatterns(out);

  return out;
}

/**
 * Clean XML-like tags that LLM might output
 */
export function cleanXmlTags(content: string): string {
  return content
    // Remove <notes_structure> wrapper
    .replace(/<\/?notes_structure>/gi, '')
    // Remove <section name="..."> tags but keep content
    .replace(/<section\s+name="([^"]+)"[^>]*>/gi, '\n## $1\n')
    // Remove </section> tags
    .replace(/<\/section>/gi, '\n')
    // Remove any optional attributes
    .replace(/\s+optional="[^"]*"/gi, '')
    // Clean up excessive newlines
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/**
 * Combined sanitization - XML cleaning + LaTeX fixing
 */
export function sanitizeNotes(text: string): string {
  const xmlCleaned = cleanXmlTags(text);
  return sanitizeLatex(xmlCleaned);
}

export default sanitizeLatex;
