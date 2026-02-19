'use client';

import { useState } from 'react';

interface ErrorDetail {
    message: string;
    type?: string;
    code?: string;
    stack_trace?: string;
    suggestion?: string;
    timestamp?: string;
    retryable?: boolean;
    context?: Record<string, unknown>;
}

interface ErrorDiagnosticsProps {
    error: ErrorDetail | string;
    onRetry?: () => void;
    onDismiss?: () => void;
    compact?: boolean;
}

function parseError(error: ErrorDetail | string): ErrorDetail {
    if (typeof error === 'string') {
        const lines = error.split('\n');
        let message = lines[0];
        let stack_trace: string | undefined;
        let type: string | undefined;
        
        const stackStart = lines.findIndex(l => l.includes('at ') || l.includes('Traceback') || l.includes('Stack trace'));
        if (stackStart > 0) {
            message = lines.slice(0, stackStart).join('\n');
            stack_trace = lines.slice(stackStart).join('\n');
        }
        
        if (error.includes('Error:') || error.includes('Exception:')) {
            const match = error.match(/(\w+(?:Error|Exception)):/);
            if (match) type = match[1];
        }
        
        return { message, stack_trace, type };
    }
    return error;
}

function getErrorSeverity(error: ErrorDetail): 'critical' | 'error' | 'warning' {
    const msg = error.message.toLowerCase();
    if (msg.includes('critical') || msg.includes('fatal') || msg.includes('timeout')) return 'critical';
    if (msg.includes('warning') || msg.includes('deprecated')) return 'warning';
    return 'error';
}

function getErrorIcon(severity: 'critical' | 'error' | 'warning'): string {
    switch (severity) {
        case 'critical': return '⛔';
        case 'warning': return '⚠️';
        default: return '❌';
    }
}

export function ErrorDiagnostics({ error, onRetry, onDismiss, compact = false }: ErrorDiagnosticsProps) {
    const [showStack, setShowStack] = useState(false);
    const [showContext, setShowContext] = useState(false);
    
    const parsed = parseError(error);
    const severity = getErrorSeverity(parsed);
    const icon = getErrorIcon(severity);
    
    const bgColor = severity === 'critical'
        ? 'rgba(239, 68, 68, 0.1)'
        : severity === 'warning'
        ? 'rgba(245, 158, 11, 0.1)'
        : 'var(--color-danger-muted)';
    
    const borderColor = severity === 'critical'
        ? 'rgba(239, 68, 68, 0.3)'
        : severity === 'warning'
        ? 'rgba(245, 158, 11, 0.3)'
        : 'rgba(239, 68, 68, 0.2)';
    
    if (compact) {
        return (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-sm)',
                    padding: 'var(--space-sm) var(--space-md)',
                    background: bgColor,
                    borderRadius: 'var(--radius-sm)',
                    borderLeft: `3px solid ${severity === 'critical' ? 'var(--color-danger)' : severity === 'warning' ? 'var(--color-warning)' : 'var(--color-danger)'}`,
                }}
            >
                <span aria-hidden="true">{icon}</span>
                <span
                    style={{
                        flex: 1,
                        fontSize: 'var(--font-size-sm)',
                        color: 'var(--color-danger)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                    }}
                    title={parsed.message}
                >
                    {parsed.message}
                </span>
                {onRetry && parsed.retryable !== false && (
                    <button
                        type="button"
                        onClick={onRetry}
                        style={{
                            padding: 'var(--space-xs) var(--space-sm)',
                            fontSize: 'var(--font-size-xs)',
                            background: 'var(--color-danger)',
                            color: 'white',
                            border: 'none',
                            borderRadius: 'var(--radius-sm)',
                            cursor: 'pointer',
                        }}
                    >
                        Retry
                    </button>
                )}
            </div>
        );
    }
    
    return (
        <div
            style={{
                padding: 'var(--space-lg)',
                background: bgColor,
                borderRadius: 'var(--radius-md)',
                border: `1px solid ${borderColor}`,
                borderLeft: `3px solid ${severity === 'critical' ? 'var(--color-danger)' : severity === 'warning' ? 'var(--color-warning)' : 'var(--color-danger)'}`,
            }}
            role="alert"
        >
            {/* Header */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    marginBottom: parsed.stack_trace || parsed.suggestion ? 'var(--space-md)' : 0,
                }}
            >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-sm)', flex: 1, minWidth: 0 }}>
                    <span style={{ fontSize: '1.25rem', flexShrink: 0 }} aria-hidden="true">{icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        {parsed.type && (
                            <div
                                style={{
                                    fontSize: 'var(--font-size-xs)',
                                    color: 'var(--color-text-secondary)',
                                    marginBottom: 'var(--space-xs)',
                                    fontFamily: 'var(--font-mono)',
                                }}
                            >
                                {parsed.type}
                                {parsed.code && ` (${parsed.code})`}
                            </div>
                        )}
                        <div
                            style={{
                                fontSize: 'var(--font-size-sm)',
                                color: 'var(--color-danger)',
                                fontWeight: 500,
                                lineHeight: 1.5,
                                wordBreak: 'break-word',
                            }}
                        >
                            {parsed.message}
                        </div>
                        {parsed.timestamp && (
                            <div
                                style={{
                                    fontSize: 'var(--font-size-xs)',
                                    color: 'var(--color-text-tertiary)',
                                    marginTop: 'var(--space-xs)',
                                }}
                            >
                                {parsed.timestamp}
                            </div>
                        )}
                    </div>
                </div>
                
                <div style={{ display: 'flex', gap: 'var(--space-xs)', flexShrink: 0 }}>
                    {onRetry && parsed.retryable !== false && (
                        <button
                            type="button"
                            onClick={onRetry}
                            style={{
                                padding: 'var(--space-xs) var(--space-md)',
                                fontSize: 'var(--font-size-sm)',
                                background: 'var(--color-danger)',
                                color: 'white',
                                border: 'none',
                                borderRadius: 'var(--radius-sm)',
                                cursor: 'pointer',
                            }}
                        >
                            Retry
                        </button>
                    )}
                    {onDismiss && (
                        <button
                            type="button"
                            onClick={onDismiss}
                            style={{
                                padding: 'var(--space-xs) var(--space-sm)',
                                fontSize: 'var(--font-size-sm)',
                                background: 'transparent',
                                color: 'var(--color-text-secondary)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-sm)',
                                cursor: 'pointer',
                            }}
                            aria-label="Dismiss error"
                        >
                            ✕
                        </button>
                    )}
                </div>
            </div>
            
            {/* Suggestion */}
            {parsed.suggestion && (
                <div
                    style={{
                        marginTop: 'var(--space-md)',
                        padding: 'var(--space-md)',
                        background: 'rgba(16, 185, 129, 0.1)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid rgba(16, 185, 129, 0.2)',
                    }}
                >
                    <div
                        style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-success)',
                            fontWeight: 600,
                            marginBottom: 'var(--space-xs)',
                        }}
                    >
                        💡 Suggestion
                    </div>
                    <div
                        style={{
                            fontSize: 'var(--font-size-sm)',
                            color: 'var(--color-text-primary)',
                        }}
                    >
                        {parsed.suggestion}
                    </div>
                </div>
            )}
            
            {/* Stack trace toggle */}
            {parsed.stack_trace && (
                <div style={{ marginTop: 'var(--space-md)' }}>
                    <button
                        type="button"
                        onClick={() => setShowStack(!showStack)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-xs)',
                            background: 'none',
                            border: 'none',
                            color: 'var(--color-text-secondary)',
                            cursor: 'pointer',
                            fontSize: 'var(--font-size-xs)',
                            padding: 0,
                        }}
                    >
                        <span
                            style={{
                                transform: showStack ? 'rotate(90deg)' : 'none',
                                transition: 'transform 0.15s',
                                display: 'inline-block',
                            }}
                        >
                            ▶
                        </span>
                        Stack trace
                    </button>
                    {showStack && (
                        <pre
                            style={{
                                marginTop: 'var(--space-sm)',
                                padding: 'var(--space-md)',
                                background: 'var(--color-bg-primary)',
                                borderRadius: 'var(--radius-sm)',
                                fontFamily: 'var(--font-mono)',
                                fontSize: 'var(--font-size-xs)',
                                color: 'var(--color-text-secondary)',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                                maxHeight: 300,
                                overflow: 'auto',
                            }}
                        >
                            {parsed.stack_trace}
                        </pre>
                    )}
                </div>
            )}
            
            {/* Context toggle */}
            {parsed.context && Object.keys(parsed.context).length > 0 && (
                <div style={{ marginTop: 'var(--space-md)' }}>
                    <button
                        type="button"
                        onClick={() => setShowContext(!showContext)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-xs)',
                            background: 'none',
                            border: 'none',
                            color: 'var(--color-text-secondary)',
                            cursor: 'pointer',
                            fontSize: 'var(--font-size-xs)',
                            padding: 0,
                        }}
                    >
                        <span
                            style={{
                                transform: showContext ? 'rotate(90deg)' : 'none',
                                transition: 'transform 0.15s',
                                display: 'inline-block',
                            }}
                        >
                            ▶
                        </span>
                        Error context
                    </button>
                    {showContext && (
                        <pre
                            style={{
                                marginTop: 'var(--space-sm)',
                                padding: 'var(--space-md)',
                                background: 'var(--color-bg-primary)',
                                borderRadius: 'var(--radius-sm)',
                                fontFamily: 'var(--font-mono)',
                                fontSize: 'var(--font-size-xs)',
                                color: 'var(--color-text-secondary)',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                                maxHeight: 200,
                                overflow: 'auto',
                            }}
                        >
                            {JSON.stringify(parsed.context, null, 2)}
                        </pre>
                    )}
                </div>
            )}
        </div>
    );
}
