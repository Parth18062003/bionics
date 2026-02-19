'use client';

import { useState, useMemo } from 'react';

interface CodeViewerProps {
    code: string;
    language?: string;
    maxHeight?: number;
    showLineNumbers?: boolean;
    filename?: string;
    collapsible?: boolean;
    defaultCollapsed?: boolean;
}

const LANGUAGE_LABELS: Record<string, string> = {
    python: 'Python',
    sql: 'SQL',
    scala: 'Scala',
    json: 'JSON',
    yaml: 'YAML',
    markdown: 'Markdown',
    text: 'Text',
};

function detectLanguage(code: string, explicitLang?: string): string {
    if (explicitLang) return explicitLang.toLowerCase();
    if (code.includes('def ') || code.includes('import ') && code.includes('print')) return 'python';
    if (code.includes('SELECT ') || code.includes('FROM ') || code.includes('CREATE TABLE')) return 'sql';
    if (code.includes('val ') || code.includes('def ') && code.includes(': Unit')) return 'scala';
    if (code.trim().startsWith('{') || code.trim().startsWith('[')) return 'json';
    return 'text';
}

function highlightCode(code: string, language: string): Array<{ text: string; type: string }> {
    const tokens: Array<{ text: string; type: string }> = [];
    const lines = code.split('\n');
    
    const keywords: Record<string, string[]> = {
        python: ['def', 'class', 'import', 'from', 'return', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'with', 'as', 'in', 'not', 'and', 'or', 'True', 'False', 'None', 'async', 'await', 'lambda', 'yield', 'raise', 'pass', 'break', 'continue'],
        sql: ['SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS', 'NULL', 'AS', 'ORDER', 'BY', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET', 'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE', 'DROP', 'ALTER', 'INDEX', 'VIEW', 'DATABASE', 'SCHEMA', 'CATALOG', 'DESCRIBE', 'SHOW', 'USE', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'UNION', 'ALL', 'EXISTS', 'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES', 'CONSTRAINT', 'DEFAULT', 'CHECK', 'UNIQUE', 'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK', 'TRANSACTION', 'BEGIN', 'DECLARE', 'EXEC', 'EXECUTE', 'PROCEDURE', 'FUNCTION', 'RETURNS', 'RETURN'],
        scala: ['def', 'val', 'var', 'class', 'object', 'trait', 'extends', 'with', 'import', 'package', 'if', 'else', 'match', 'case', 'for', 'while', 'yield', 'return', 'throw', 'try', 'catch', 'finally', 'new', 'this', 'super', 'true', 'false', 'null', 'type', 'private', 'protected', 'override', 'abstract', 'final', 'sealed', 'implicit', 'lazy', 'async', 'await'],
    };

    const kwSet = new Set(keywords[language] || []);
    
    for (let i = 0; i < lines.length; i++) {
        if (i > 0) {
            tokens.push({ text: '\n', type: 'newline' });
        }
        let line = lines[i];
        
        if (language === 'json') {
            const jsonHighlight = (str: string) => {
                const result: Array<{ text: string; type: string }> = [];
                const regex = /("[^"]*")\s*:/g;
                let lastIndex = 0;
                let match;
                
                while ((match = regex.exec(str)) !== null) {
                    if (match.index > lastIndex) {
                        result.push({ text: str.slice(lastIndex, match.index), type: 'text' });
                    }
                    result.push({ text: match[1], type: 'key' });
                    lastIndex = match.index + match[1].length;
                }
                if (lastIndex < str.length) {
                    result.push({ text: str.slice(lastIndex), type: 'text' });
                }
                return result.length > 0 ? result : [{ text: str, type: 'text' }];
            };
            tokens.push(...jsonHighlight(line));
            continue;
        }
        
        const stringRegex = /(["'`])(?:(?!\1|\\).|\\.)*\1/g;
        const commentRegex = language === 'python' ? /#.*$/ : language === 'sql' ? /--.*$/ : /\/\/.*$/;
        const numberRegex = /\b\d+(?:\.\d+)?\b/g;
        
        let processed = line;
        let offset = 0;
        const lineTokens: Array<{ text: string; type: string }> = [];
        
        const allMatches: Array<{ start: number; end: number; type: string }> = [];
        
        let m;
        while ((m = stringRegex.exec(line)) !== null) {
            allMatches.push({ start: m.index, end: m.index + m[0].length, type: 'string' });
        }
        while ((m = commentRegex.exec(line)) !== null) {
            allMatches.push({ start: m.index, end: m.index + m[0].length, type: 'comment' });
        }
        while ((m = numberRegex.exec(line)) !== null) {
            allMatches.push({ start: m.index, end: m.index + m[0].length, type: 'number' });
        }
        
        allMatches.sort((a, b) => a.start - b.start);
        
        const filtered: typeof allMatches = [];
        for (const match of allMatches) {
            const overlaps = filtered.some(f => match.start < f.end && match.end > f.start);
            if (!overlaps) filtered.push(match);
        }
        
        let pos = 0;
        for (const match of filtered) {
            if (match.start > pos) {
                const before = line.slice(pos, match.start);
                const words = before.split(/(\s+|[(){}\[\],;:.=+\-*/<>!&|]+)/);
                for (const word of words) {
                    if (!word) continue;
                    if (kwSet.has(word)) {
                        lineTokens.push({ text: word, type: 'keyword' });
                    } else if (/^\s+$/.test(word)) {
                        lineTokens.push({ text: word, type: 'whitespace' });
                    } else {
                        lineTokens.push({ text: word, type: 'text' });
                    }
                }
            }
            lineTokens.push({ text: line.slice(match.start, match.end), type: match.type });
            pos = match.end;
        }
        
        if (pos < line.length) {
            const remaining = line.slice(pos);
            const words = remaining.split(/(\s+|[(){}\[\],;:.=+\-*/<>!&|]+)/);
            for (const word of words) {
                if (!word) continue;
                if (kwSet.has(word)) {
                    lineTokens.push({ text: word, type: 'keyword' });
                } else if (/^\s+$/.test(word)) {
                    lineTokens.push({ text: word, type: 'whitespace' });
                } else {
                    lineTokens.push({ text: word, type: 'text' });
                }
            }
        }
        
        tokens.push(...lineTokens);
    }
    
    return tokens;
}

export function CodeViewer({
    code,
    language,
    maxHeight = 500,
    showLineNumbers = true,
    filename,
    collapsible = false,
    defaultCollapsed = false,
}: CodeViewerProps) {
    const [collapsed, setCollapsed] = useState(collapsible && defaultCollapsed);
    const [copied, setCopied] = useState(false);

    const detectedLang = useMemo(() => detectLanguage(code, language), [code, language]);
    const highlighted = useMemo(() => highlightCode(code, detectedLang), [code, detectedLang]);
    const lineCount = code.split('\n').length;

    const handleCopy = async () => {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const getTokencolor = (type: string): string => {
        switch (type) {
            case 'keyword': return 'var(--color-accent)';
            case 'string': return '#10b981';
            case 'comment': return 'var(--color-text-secondary)';
            case 'number': return '#f59e0b';
            case 'key': return '#818cf8';
            default: return 'var(--color-text-primary)';
        }
    };

    if (collapsed) {
        return (
            <div
                style={{
                    padding: 'var(--space-sm) var(--space-md)',
                    background: 'var(--color-bg-tertiary)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                }}
            >
                <button
                    type="button"
                    onClick={() => setCollapsed(false)}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-sm)',
                        background: 'none',
                        border: 'none',
                        color: 'var(--color-text-secondary)',
                        cursor: 'pointer',
                        fontSize: 'var(--font-size-sm)',
                        fontFamily: 'var(--font-mono)',
                    }}
                >
                    <span style={{ transform: 'rotate(0deg)', transition: 'transform 0.15s' }}>▶</span>
                    {filename || `${LANGUAGE_LABELS[detectedLang] || detectedLang} (${lineCount} lines)`}
                </button>
            </div>
        );
    }

    return (
        <div
            style={{
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
                overflow: 'hidden',
                background: 'var(--color-bg-primary)',
            }}
        >
            {/* Header */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-xs) var(--space-md)',
                    background: 'var(--color-bg-tertiary)',
                    borderBottom: '1px solid var(--color-border)',
                    fontSize: 'var(--font-size-xs)',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                    {collapsible && (
                        <button
                            type="button"
                            onClick={() => setCollapsed(true)}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: 'var(--color-text-secondary)',
                                cursor: 'pointer',
                                padding: 0,
                            }}
                        >
                            ▼
                        </button>
                    )}
                    <span style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)' }}>
                        {filename || LANGUAGE_LABELS[detectedLang] || detectedLang}
                    </span>
                    <span style={{ color: 'var(--color-text-tertiary)' }}>
                        {lineCount} lines
                    </span>
                </div>
                <button
                    type="button"
                    onClick={handleCopy}
                    style={{
                        background: 'none',
                        border: 'none',
                        color: copied ? 'var(--color-success)' : 'var(--color-text-secondary)',
                        cursor: 'pointer',
                        fontSize: 'var(--font-size-xs)',
                        padding: 'var(--space-xs) var(--space-sm)',
                        borderRadius: 'var(--radius-sm)',
                        transition: 'all var(--transition-fast)',
                    }}
                >
                    {copied ? '✓ Copied' : 'Copy'}
                </button>
            </div>

            {/* Code */}
            <div
                style={{
                    maxHeight,
                    overflow: 'auto',
                    display: 'flex',
                }}
            >
                {showLineNumbers && (
                    <div
                        style={{
                            padding: 'var(--space-md) var(--space-sm)',
                            background: 'var(--color-bg-tertiary)',
                            color: 'var(--color-text-tertiary)',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 'var(--font-size-xs)',
                            lineHeight: 1.6,
                            textAlign: 'right',
                            userSelect: 'none',
                            borderRight: '1px solid var(--color-border)',
                            minWidth: 40,
                        }}
                        aria-hidden="true"
                    >
                        {code.split('\n').map((_, i) => (
                            <div key={i}>{i + 1}</div>
                        ))}
                    </div>
                )}
                <pre
                    style={{
                        flex: 1,
                        margin: 0,
                        padding: 'var(--space-md)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 'var(--font-size-sm)',
                        lineHeight: 1.6,
                        whiteSpace: 'pre',
                        overflow: 'auto',
                    }}
                >
                    <code>
                        {highlighted.map((token, i) => (
                            <span key={i} style={{ color: getTokencolor(token.type) }}>
                                {token.text}
                            </span>
                        ))}
                    </code>
                </pre>
            </div>
        </div>
    );
}
