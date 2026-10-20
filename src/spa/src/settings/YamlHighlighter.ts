/** Token kinds for Settings YAML syntax highlighting. */
export type YamlTokenKind =
  | "plain"
  | "comment"
  | "key"
  | "punct"
  | "string"
  | "number"
  | "bool"
  | "null";

export type YamlToken = { kind: YamlTokenKind; text: string };

const ESC: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
};

const BOOLS = new Set(["true", "True", "TRUE", "false", "False", "FALSE"]);
const NULLS = new Set(["null", "Null", "NULL", "~"]);
const NUMBER_RE = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/;

/** Lightweight line-oriented YAML highlighter (no full YAML parse). */
export class YamlHighlighter {
  highlightHtml(source: string): string {
    return this.tokenize(source)
      .map((token) => this.renderToken(token))
      .join("");
  }

  tokenize(source: string): YamlToken[] {
    const tokens: YamlToken[] = [];
    const lines = source.split("\n");
    for (let i = 0; i < lines.length; i += 1) {
      tokens.push(...this.tokenizeLine(lines[i] ?? ""));
      if (i < lines.length - 1) tokens.push({ kind: "plain", text: "\n" });
    }
    return tokens;
  }

  private renderToken(token: YamlToken): string {
    const escaped = escapeHtml(token.text);
    if (token.kind === "plain") return escaped;
    return `<span class="yh-${token.kind}">${escaped}</span>`;
  }

  private tokenizeLine(line: string): YamlToken[] {
    if (!line) return [];
    const indent = leadingWs(line);
    const body = line.slice(indent.length);
    if (!body) return [{ kind: "plain", text: indent }];
    if (body.startsWith("#")) {
      return [
        { kind: "plain", text: indent },
        { kind: "comment", text: body },
      ];
    }
    return [{ kind: "plain", text: indent }, ...this.tokenizeBody(body)];
  }

  private tokenizeBody(body: string): YamlToken[] {
    const tokens: YamlToken[] = [];
    let rest = body;
    while (rest) {
      if (rest.startsWith("#")) {
        tokens.push({ kind: "comment", text: rest });
        break;
      }
      const list = rest.match(/^(- )(.*)$/);
      if (list) {
        tokens.push({ kind: "punct", text: "- " });
        rest = list[2] ?? "";
        continue;
      }
      const mapped = this.tryMapping(rest);
      if (mapped) {
        tokens.push(...mapped.tokens);
        rest = mapped.rest;
        continue;
      }
      tokens.push(...this.tokenizeScalar(rest));
      break;
    }
    return tokens;
  }

  private tryMapping(
    rest: string,
  ): { tokens: YamlToken[]; rest: string } | null {
    const m = rest.match(/^([^:#\s][^:#]*?)(:)([ \t]+|$)/);
    if (!m) return null;
    const key = m[1] ?? "";
    const colon = m[2] ?? ":";
    const ws = m[3] ?? "";
    const after = rest.slice(key.length + colon.length + ws.length);
    const tokens: YamlToken[] = [
      { kind: "key", text: key },
      { kind: "punct", text: colon },
    ];
    if (ws) tokens.push({ kind: "plain", text: ws });
    return { tokens, rest: after };
  }

  private tokenizeScalar(value: string): YamlToken[] {
    if (!value) return [];
    const commentAt = bareCommentIndex(value);
    const scalar = commentAt >= 0 ? value.slice(0, commentAt) : value;
    const comment = commentAt >= 0 ? value.slice(commentAt) : "";
    const tokens = this.classifyScalar(scalar);
    if (comment) tokens.push({ kind: "comment", text: comment });
    return tokens;
  }

  private classifyScalar(value: string): YamlToken[] {
    if (!value) return [];
    const trimmed = value.trimEnd();
    const trail = value.slice(trimmed.length);
    if (!trimmed) return [{ kind: "plain", text: value }];
    const kind = scalarKind(trimmed);
    const tokens: YamlToken[] = [{ kind, text: trimmed }];
    if (trail) tokens.push({ kind: "plain", text: trail });
    return tokens;
  }
}

function scalarKind(value: string): YamlTokenKind {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return "string";
  }
  if (BOOLS.has(value)) return "bool";
  if (NULLS.has(value)) return "null";
  if (NUMBER_RE.test(value)) return "number";
  return "string";
}

function bareCommentIndex(value: string): number {
  if (value.startsWith('"') || value.startsWith("'")) return -1;
  const idx = value.indexOf(" #");
  return idx >= 0 ? idx + 1 : -1;
}

function leadingWs(line: string): string {
  const m = line.match(/^[\t ]*/);
  return m?.[0] ?? "";
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"]/g, (ch) => ESC[ch] ?? ch);
}
