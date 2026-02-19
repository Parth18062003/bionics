'use client';

import { useState, useMemo } from 'react';
import { CodeViewer } from './CodeViewer';

interface OutputVisualizationProps {
    output?: string | null;
    outputType?: 'text' | 'json' | 'table' | 'html' | 'auto';
    maxHeight?: number;
    title?: string;
}

function detectOutputType(output: string): 'json' | 'table' | 'html' | 'text' {
    const trimmed = output.trim();
    
    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || 
        (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
        try {
            JSON.parse(trimmed);
            return 'json';
        } catch {
            // Not valid JSON
        }
    }
    
    if (trimmed.startsWith('<') && trimmed.includes('>')) {
        return 'html';
    }
    
    const lines = trimmed.split('\n');
    if (lines.length >= 2) {
        const firstLine = lines[0];
        const delimiterMatch = firstLine.match(/[\t|,]/);
        if (delimiterMatch) {
            const delimiter = delimiterMatch[0];
            const firstCols = firstLine.split(delimiter).length;
            if (firstCols >= 2) {
                const consistentColumns = lines.slice(0, 5).every(line => 
                    line.split(delimiter).length === firstCols
                );
                if (consistentColumns) return 'table';
            }
        }
    }
    
    return 'text';
}

function parseTableOutput(output: string): { headers: string[]; rows: string[][] } | null {
    const lines = output.trim().split('\n');
    if (lines.length < 2) return null;
    
    let delimiter: string | null = null;
    const firstLine = lines[0];
    
    if (firstLine.includes('\t')) delimiter = '\t';
    else if (firstLine.includes('|')) delimiter = '|';
    else if (firstLine.includes(',')) delimiter = ',';
    else return null;
    
    const rows = lines.map(line => 
        line.split(delimiter!).map(cell => cell.trim())
    );
    
    return {
        headers: rows[0],
        rows: rows.slice(1),
    };
}

function formatJson(json: unknown, indent = 2): string {
    return JSON.stringify(json, null, indent);
}

export function OutputVisualization({
    output,
    outputType = 'auto',
    maxHeight = 400,
    title,
}: OutputVisualizationProps) {
    const [viewMode, setViewMode] = useState<'auto' | 'json' | 'raw' | 'table'>('auto');
    
    const detectedType = useMemo(() => {
        if (outputType !== 'auto') return outputType;
        if (!output) return 'text';
        return detectOutputType(output);
    }, [output, outputType]);
    
    const tableData = useMemo(() => {
        if (!output) return null;
        if (detectedType === 'table' || (detectedType === 'json' && viewMode === 'table')) {
            if (detectedType === 'table') {
                return parseTableOutput(output);
            }
            // Try to parse JSON as array of objects for table view
            try {
                const parsed = JSON.parse(output);
                if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'object') {
                    const headers = Object.keys(parsed[0]);
                    const rows = parsed.map(obj => headers.map(h => String(obj[h] ?? '')));
                    return { headers, rows };
                }
            } catch {
                // Not valid JSON
            }
        }
        return null;
    }, [output, detectedType, viewMode]);
    
    const parsedJson = useMemo(() => {
        if (!output || detectedType !== 'json') return null;
        try {
            return JSON.parse(output);
        } catch {
            return null;
        }
    }, [output, detectedType]);
    
    if (!output) {
        return (
            <div
                style={{
                    padding: 'var(--space-lg)',
                    background: 'var(--color-bg-tertiary)',
                    borderRadius: 'var(--radius-md)',
                    textAlign: 'center',
                    color: 'var(--color-text-secondary)',
                    fontSize: 'var(--font-size-sm)',
                }}
            >
                No output available
            </div>
        );
    }
    
    const effectiveViewMode = viewMode === 'auto' ? 'raw' : viewMode;
    
    return (
        <div
            style={{
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
                overflow: 'hidden',
            }}
        >
            {/* Header with view mode toggle */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-xs) var(--space-md)',
                    background: 'var(--color-bg-tertiary)',
                    borderBottom: '1px solid var(--color-border)',
                }}
            >
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                    {title || 'Output'}
                </span>
                
                <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
                    {detectedType === 'json' && (
                        <>
                            <button
                                type="button"
                                onClick={() => setViewMode('json')}
                                style={{
                                    padding: 'var(--space-xs) var(--space-sm)',
                                    fontSize: 'var(--font-size-xs)',
                                    borderRadius: 'var(--radius-sm)',
                                    border: 'none',
                                    background: effectiveViewMode === 'json' ? 'var(--color-accent)' : 'transparent',
                                    color: effectiveViewMode === 'json' ? 'white' : 'var(--color-text-secondary)',
                                    cursor: 'pointer',
                                }}
                            >
                                JSON
                            </button>
                            {parsedJson && Array.isArray(parsedJson) && (
                                <button
                                    type="button"
                                    onClick={() => setViewMode('table')}
                                    style={{
                                        padding: 'var(--space-xs) var(--space-sm)',
                                        fontSize: 'var(--font-size-xs)',
                                        borderRadius: 'var(--radius-sm)',
                                        border: 'none',
                                        background: effectiveViewMode === 'table' ? 'var(--color-accent)' : 'transparent',
                                        color: effectiveViewMode === 'table' ? 'white' : 'var(--color-text-secondary)',
                                        cursor: 'pointer',
                                    }}
                                >
                                    Table
                                </button>
                            )}
                        </>
                    )}
                    {detectedType === 'table' && (
                        <button
                            type="button"
                            onClick={() => setViewMode('table')}
                            style={{
                                padding: 'var(--space-xs) var(--space-sm)',
                                fontSize: 'var(--font-size-xs)',
                                borderRadius: 'var(--radius-sm)',
                                border: 'none',
                                background: effectiveViewMode === 'table' ? 'var(--color-accent)' : 'transparent',
                                color: effectiveViewMode === 'table' ? 'white' : 'var(--color-text-secondary)',
                                cursor: 'pointer',
                            }}
                        >
                            Table
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={() => setViewMode('raw')}
                        style={{
                            padding: 'var(--space-xs) var(--space-sm)',
                            fontSize: 'var(--font-size-xs)',
                            borderRadius: 'var(--radius-sm)',
                            border: 'none',
                            background: effectiveViewMode === 'raw' ? 'var(--color-accent)' : 'transparent',
                            color: effectiveViewMode === 'raw' ? 'white' : 'var(--color-text-secondary)',
                            cursor: 'pointer',
                        }}
                    >
                        Raw
                    </button>
                </div>
            </div>
            
            {/* Content */}
            <div style={{ maxHeight, overflow: 'auto' }}>
                {effectiveViewMode === 'table' && tableData ? (
                    <table
                        style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            fontSize: 'var(--font-size-sm)',
                        }}
                    >
                        <thead>
                            <tr style={{ background: 'var(--color-bg-tertiary)' }}>
                                {tableData.headers.map((header, i) => (
                                    <th
                                        key={i}
                                        style={{
                                            padding: 'var(--space-sm) var(--space-md)',
                                            textAlign: 'left',
                                            fontWeight: 600,
                                            borderBottom: '1px solid var(--color-border)',
                                            whiteSpace: 'nowrap',
                                        }}
                                    >
                                        {header}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {tableData.rows.slice(0, 100).map((row, i) => (
                                <tr
                                    key={i}
                                    style={{
                                        background: i % 2 === 0 ? 'var(--color-bg-primary)' : 'var(--color-bg-secondary)',
                                    }}
                                >
                                    {row.map((cell, j) => (
                                        <td
                                            key={j}
                                            style={{
                                                padding: 'var(--space-sm) var(--space-md)',
                                                borderBottom: '1px solid var(--color-border)',
                                                maxWidth: 300,
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap',
                                            }}
                                            title={cell}
                                        >
                                            {cell}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : effectiveViewMode === 'json' && parsedJson ? (
                    <CodeViewer
                        code={formatJson(parsedJson)}
                        language="json"
                        maxHeight={maxHeight}
                        showLineNumbers={false}
                    />
                ) : detectedType === 'html' ? (
                    <div
                        style={{
                            padding: 'var(--space-md)',
                            background: 'white',
                        }}
                        dangerouslySetInnerHTML={{ __html: output }}
                    />
                ) : (
                    <pre
                        style={{
                            margin: 0,
                            padding: 'var(--space-md)',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 'var(--font-size-sm)',
                            lineHeight: 1.6,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            color: 'var(--color-success)',
                        }}
                    >
                        {output}
                    </pre>
                )}
            </div>
            
            {/* Footer with row count */}
            {effectiveViewMode === 'table' && tableData && tableData.rows.length > 100 && (
                <div
                    style={{
                        padding: 'var(--space-xs) var(--space-md)',
                        background: 'var(--color-bg-tertiary)',
                        borderTop: '1px solid var(--color-border)',
                        fontSize: 'var(--font-size-xs)',
                        color: 'var(--color-text-secondary)',
                    }}
                >
                    Showing first 100 of {tableData.rows.length} rows
                </div>
            )}
        </div>
    );
}
