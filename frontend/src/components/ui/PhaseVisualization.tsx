'use client';

import type { TaskEvent } from '@/api/types';
import { STATE_COLORS, STATE_LABELS } from '@/api/types';

interface PhaseVisualizationProps {
    currentState: string;
    events: TaskEvent[];
    compact?: boolean;
}

const PHASE_ORDER = [
    'SUBMITTED',
    'PARSING',
    'PARSED',
    'PARSE_FAILED',
    'PLANNING',
    'PLANNED',
    'AGENT_ASSIGNMENT',
    'AGENT_ASSIGNED',
    'IN_DEVELOPMENT',
    'CODE_GENERATED',
    'DEV_FAILED',
    'IN_VALIDATION',
    'VALIDATION_PASSED',
    'VALIDATION_FAILED',
    'OPTIMIZATION_PENDING',
    'IN_OPTIMIZATION',
    'OPTIMIZED',
    'APPROVAL_PENDING',
    'IN_REVIEW',
    'APPROVED',
    'REJECTED',
    'DEPLOYING',
    'DEPLOYED',
    'COMPLETED',
    'CANCELLED',
];

const PHASE_GROUPS = [
    {
        name: 'Planning',
        states: ['SUBMITTED', 'PARSING', 'PARSED', 'PARSE_FAILED', 'PLANNING', 'PLANNED'],
        color: '#8b5cf6',
    },
    {
        name: 'Development',
        states: ['AGENT_ASSIGNMENT', 'AGENT_ASSIGNED', 'IN_DEVELOPMENT', 'CODE_GENERATED', 'DEV_FAILED'],
        color: '#f59e0b',
    },
    {
        name: 'Validation',
        states: ['IN_VALIDATION', 'VALIDATION_PASSED', 'VALIDATION_FAILED'],
        color: '#f97316',
    },
    {
        name: 'Optimization',
        states: ['OPTIMIZATION_PENDING', 'IN_OPTIMIZATION', 'OPTIMIZED'],
        color: '#22d3ee',
    },
    {
        name: 'Approval',
        states: ['APPROVAL_PENDING', 'IN_REVIEW', 'APPROVED', 'REJECTED'],
        color: '#10b981',
    },
    {
        name: 'Deployment',
        states: ['DEPLOYING', 'DEPLOYED', 'COMPLETED', 'CANCELLED'],
        color: '#3b82f6',
    },
];

const ERROR_STATES = ['PARSE_FAILED', 'DEV_FAILED', 'VALIDATION_FAILED', 'REJECTED'];
const SUCCESS_STATES = ['COMPLETED'];
const CANCELLED_STATES = ['CANCELLED'];

function getStateGroup(state: string): typeof PHASE_GROUPS[0] | undefined {
    return PHASE_GROUPS.find(g => g.states.includes(state));
}

function getPhaseStatus(state: string, currentState: string, visitedStates: Set<string>): 'completed' | 'current' | 'pending' | 'error' | 'skipped' {
    if (SUCCESS_STATES.includes(currentState) || currentState === 'COMPLETED') {
        const stateIdx = PHASE_ORDER.indexOf(state);
        const currentIdx = PHASE_ORDER.indexOf(currentState);
        if (stateIdx < currentIdx) return 'completed';
        if (state === currentState) return 'completed';
        return 'skipped';
    }
    
    if (CANCELLED_STATES.includes(currentState)) {
        if (visitedStates.has(state) && state !== currentState) return 'completed';
        if (state === currentState) return 'error';
        return 'skipped';
    }
    
    if (ERROR_STATES.includes(currentState)) {
        if (visitedStates.has(state) && state !== currentState) return 'completed';
        if (state === currentState) return 'error';
        return 'pending';
    }
    
    if (visitedStates.has(state) && state !== currentState) return 'completed';
    if (state === currentState) return 'current';
    return 'pending';
}

export function PhaseVisualization({ currentState, events, compact = false }: PhaseVisualizationProps) {
    const visitedStates = new Set(events.map(e => e.to_state));
    const currentGroup = getStateGroup(currentState);
    
    if (compact) {
        return (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-xs)',
                    flexWrap: 'wrap',
                }}
            >
                {PHASE_GROUPS.map((group, idx) => {
                    const isActive = group === currentGroup;
                    const isCompleted = group.states.some(s => visitedStates.has(s) && s !== currentState);
                    const hasError = group.states.includes(currentState) && ERROR_STATES.includes(currentState);
                    
                    let bg = 'var(--color-bg-tertiary)';
                    let color = 'var(--color-text-secondary)';
                    
                    if (hasError) {
                        bg = 'var(--color-danger-muted)';
                        color = 'var(--color-danger)';
                    } else if (isActive) {
                        bg = group.color + '20';
                        color = group.color;
                    } else if (isCompleted) {
                        bg = 'var(--color-success-muted)';
                        color = 'var(--color-success)';
                    }
                    
                    return (
                        <div key={group.name} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                            {idx > 0 && <span style={{ color: 'var(--color-text-tertiary)' }}>→</span>}
                            <div
                                style={{
                                    padding: 'var(--space-xs) var(--space-sm)',
                                    borderRadius: 'var(--radius-sm)',
                                    background: bg,
                                    color,
                                    fontSize: 'var(--font-size-xs)',
                                    fontWeight: isActive ? 600 : 400,
                                }}
                            >
                                {group.name}
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    }
    
    return (
        <div
            style={{
                padding: 'var(--space-lg)',
                background: 'var(--color-bg-secondary)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
            }}
        >
            {/* Progress bar */}
            <div
                style={{
                    display: 'flex',
                    height: 8,
                    borderRadius: 4,
                    overflow: 'hidden',
                    marginBottom: 'var(--space-lg)',
                    background: 'var(--color-bg-tertiary)',
                }}
            >
                {PHASE_GROUPS.map((group, idx) => {
                    const isActive = group === currentGroup;
                    const isCompleted = group.states.every(s => visitedStates.has(s));
                    const hasError = group.states.includes(currentState) && ERROR_STATES.includes(currentState);
                    
                    let bg = 'transparent';
                    if (hasError) bg = 'var(--color-danger)';
                    else if (isCompleted && !ERROR_STATES.some(s => visitedStates.has(s))) bg = 'var(--color-success)';
                    else if (isActive) bg = group.color;
                    
                    return (
                        <div
                            key={group.name}
                            style={{
                                flex: 1,
                                background: bg,
                                borderRight: idx < PHASE_GROUPS.length - 1 ? '1px solid var(--color-bg-primary)' : 'none',
                            }}
                            title={group.name}
                        />
                    );
                })}
            </div>
            
            {/* Phase groups */}
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                    gap: 'var(--space-md)',
                }}
            >
                {PHASE_GROUPS.map(group => {
                    const isActive = group === currentGroup;
                    const groupStates = group.states.map(s => ({
                        state: s,
                        status: getPhaseStatus(s, currentState, visitedStates),
                    }));
                    
                    const completedCount = groupStates.filter(s => s.status === 'completed').length;
                    const hasError = groupStates.some(s => s.status === 'error');
                    
                    return (
                        <div
                            key={group.name}
                            style={{
                                padding: 'var(--space-md)',
                                borderRadius: 'var(--radius-md)',
                                background: isActive ? group.color + '10' : 'var(--color-bg-tertiary)',
                                border: isActive ? `1px solid ${group.color}40` : '1px solid transparent',
                            }}
                        >
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    marginBottom: 'var(--space-sm)',
                                }}
                            >
                                <span
                                    style={{
                                        fontSize: 'var(--font-size-xs)',
                                        fontWeight: 600,
                                        color: hasError ? 'var(--color-danger)' : isActive ? group.color : 'var(--color-text-primary)',
                                    }}
                                >
                                    {group.name}
                                </span>
                                <span
                                    style={{
                                        fontSize: 'var(--font-size-xs)',
                                        color: 'var(--color-text-secondary)',
                                    }}
                                >
                                    {completedCount}/{groupStates.length}
                                </span>
                            </div>
                            
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
                                {groupStates.map(({ state, status }) => (
                                    <div
                                        key={state}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 'var(--space-xs)',
                                            fontSize: 'var(--font-size-xs)',
                                            color: status === 'completed'
                                                ? 'var(--color-success)'
                                                : status === 'current'
                                                ? STATE_COLORS[state]
                                                : status === 'error'
                                                ? 'var(--color-danger)'
                                                : status === 'skipped'
                                                ? 'var(--color-text-tertiary)'
                                                : 'var(--color-text-secondary)',
                                            opacity: status === 'pending' || status === 'skipped' ? 0.6 : 1,
                                        }}
                                    >
                                        <span
                                            style={{
                                                width: 6,
                                                height: 6,
                                                borderRadius: '50%',
                                                background: status === 'completed'
                                                    ? 'var(--color-success)'
                                                    : status === 'current'
                                                    ? STATE_COLORS[state]
                                                    : status === 'error'
                                                    ? 'var(--color-danger)'
                                                    : 'var(--color-text-tertiary)',
                                            }}
                                        />
                                        <span
                                            style={{
                                                textDecoration: status === 'skipped' ? 'line-through' : 'none',
                                            }}
                                        >
                                            {STATE_LABELS[state] || state}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
