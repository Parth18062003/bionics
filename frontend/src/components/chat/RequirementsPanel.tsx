/**
 * AADAP — RequirementsPanel Component
 * ======================================
 * Displays extracted requirements with progressive disclosure and editing.
 * Uses CSS variables for consistent theming.
 */

'use client';

import { useState } from 'react';
import type { ExtractedRequirements, RequirementsUpdateRequest } from '@/types/chat';

interface RequirementsPanelProps {
  requirements: ExtractedRequirements | null;
  onUpdate: (updates: RequirementsUpdateRequest) => void;
  onCreateTask: () => void;
  isCreating?: boolean;
}

interface FieldEditorProps {
  label: string;
  field: { value: string | string[] | null; confidence: number } | null;
  isList?: boolean;
  onChange: (value: string | string[]) => void;
}

function FieldEditor({ label, field, isList = false, onChange }: FieldEditorProps) {
  const hasValue = field?.value != null;
  const confidence = field?.confidence ?? 0;
  const isIncomplete = !hasValue || confidence < 0.7;

  const displayValue = isList
    ? Array.isArray(field?.value) ? field.value.join('\n') : ''
    : typeof field?.value === 'string' ? field.value : '';

  return (
    <div style={{ marginBottom: 'var(--space-lg)' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-sm)',
          marginBottom: 'var(--space-xs)',
        }}
      >
        <label
          style={{
            fontSize: 'var(--font-size-sm)',
            fontWeight: 500,
            color: 'var(--color-text-secondary)',
          }}
        >
          {label}
        </label>
        {isIncomplete && (
          <span
            style={{ color: 'var(--color-warning)', fontSize: '1rem' }}
            title="Incomplete or low confidence"
          >
            ⚠
          </span>
        )}
        {hasValue && (
          <span
            style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-text-tertiary)',
            }}
          >
            {Math.round(confidence * 100)}%
          </span>
        )}
      </div>
      {isList ? (
        <textarea
          style={{
            width: '100%',
            padding: 'var(--space-md)',
            fontSize: 'var(--font-size-sm)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-bg-input)',
            color: 'var(--color-text-primary)',
            fontFamily: 'var(--font-family)',
            resize: 'vertical',
            outline: 'none',
          }}
          rows={3}
          value={displayValue}
          onChange={(e) => onChange(e.target.value.split('\n').filter(Boolean))}
          placeholder={`Enter ${label.toLowerCase()}...`}
          onFocus={(e) => {
            e.target.style.borderColor = 'var(--color-border-focus)';
          }}
          onBlur={(e) => {
            e.target.style.borderColor = 'var(--color-border)';
          }}
        />
      ) : (
        <input
          type="text"
          style={{
            width: '100%',
            padding: 'var(--space-md)',
            fontSize: 'var(--font-size-sm)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-bg-input)',
            color: 'var(--color-text-primary)',
            fontFamily: 'var(--font-family)',
            outline: 'none',
          }}
          value={displayValue}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`Enter ${label.toLowerCase()}...`}
          onFocus={(e) => {
            e.target.style.borderColor = 'var(--color-border-focus)';
          }}
          onBlur={(e) => {
            e.target.style.borderColor = 'var(--color-border)';
          }}
        />
      )}
    </div>
  );
}

export function RequirementsPanel({
  requirements,
  onUpdate,
  onCreateTask,
  isCreating = false,
}: RequirementsPanelProps) {
  const [showDetails, setShowDetails] = useState(false);

  const handleFieldChange = (
    field: keyof RequirementsUpdateRequest,
    value: string | string[]
  ) => {
    onUpdate({
      [field]: { value, confidence: 1.0 }, // User edits are 100% confident
    });
  };

  // Calculate completeness
  const requiredFields = ['task_name', 'description', 'target_table', 'objective'] as const;
  const filledCount = requiredFields.filter((key) => {
    const field = requirements?.[key];
    return field?.value != null && field.confidence >= 0.7;
  }).length;

  const isComplete = requirements?.is_complete ?? false;
  const progressPercent = (filledCount / 4) * 100;

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--color-bg-card)',
        borderLeft: '1px solid var(--color-border)',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: 'var(--space-lg)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <h2
          style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            marginBottom: 'var(--space-sm)',
          }}
        >
          Task Requirements
        </h2>
        
        {/* Progress bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-md)',
          }}
        >
          <div
            style={{
              flex: 1,
              height: '6px',
              background: 'var(--color-bg-tertiary)',
              borderRadius: 'var(--radius-full)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${progressPercent}%`,
                height: '100%',
                background: isComplete
                  ? 'var(--color-success)'
                  : 'var(--color-accent)',
                borderRadius: 'var(--radius-full)',
                transition: 'width var(--transition-base)',
              }}
            />
          </div>
          <span
            style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-text-secondary)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {filledCount}/4
          </span>
        </div>
      </div>

      {/* Core Fields */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 'var(--space-lg)',
        }}
      >
        <FieldEditor
          label="Task Name"
          field={requirements?.task_name ?? null}
          onChange={(v) => handleFieldChange('task_name', v)}
        />
        <FieldEditor
          label="Description"
          field={requirements?.description ?? null}
          onChange={(v) => handleFieldChange('description', v)}
        />
        <FieldEditor
          label="Target Table"
          field={requirements?.target_table ?? null}
          onChange={(v) => handleFieldChange('target_table', v)}
        />
        <FieldEditor
          label="Objective"
          field={requirements?.objective ?? null}
          onChange={(v) => handleFieldChange('objective', v)}
        />

        {/* Expandable Details */}
        <div style={{ marginTop: 'var(--space-lg)' }}>
          <button
            onClick={() => setShowDetails(!showDetails)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              background: 'transparent',
              border: 'none',
              color: 'var(--color-accent)',
              fontSize: 'var(--font-size-sm)',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                transform: showDetails ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform var(--transition-fast)',
              }}
            >
              <path d="M9 18l6-6-6-6" />
            </svg>
            {showDetails ? 'Hide Details' : 'Show Details'}
          </button>

          {showDetails && (
            <div style={{ marginTop: 'var(--space-md)' }}>
              <FieldEditor
                label="Success Criteria"
                field={requirements?.success_criteria ?? null}
                isList
                onChange={(v) => handleFieldChange('success_criteria', v)}
              />
              <FieldEditor
                label="Constraints"
                field={requirements?.constraints ?? null}
                isList
                onChange={(v) => handleFieldChange('constraints', v)}
              />
            </div>
          )}
        </div>
      </div>

      {/* Create Task Button */}
      <div
        style={{
          padding: 'var(--space-lg)',
          borderTop: '1px solid var(--color-border)',
        }}
      >
        <button
          onClick={onCreateTask}
          disabled={!isComplete || isCreating}
          style={{
            width: '100%',
            padding: 'var(--space-md) var(--space-lg)',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            background: isComplete && !isCreating
              ? 'var(--color-success)'
              : 'var(--color-bg-tertiary)',
            color: isComplete && !isCreating
              ? '#fff'
              : 'var(--color-text-tertiary)',
            fontSize: 'var(--font-size-base)',
            fontWeight: 500,
            cursor: isComplete && !isCreating
              ? 'pointer'
              : 'not-allowed',
            transition: 'all var(--transition-fast)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--space-sm)',
          }}
          title={!isComplete ? 'Complete all required fields' : undefined}
        >
          {isCreating ? (
            <>
              <div
                className="loading-spinner"
                style={{ width: 16, height: 16 }}
              />
              Creating Task...
            </>
          ) : (
            <>
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 5v14M5 12h14" />
              </svg>
              Create Task
            </>
          )}
        </button>
        {!isComplete && (
          <p
            style={{
              marginTop: 'var(--space-sm)',
              fontSize: 'var(--font-size-xs)',
              textAlign: 'center',
              color: 'var(--color-text-tertiary)',
            }}
          >
            Complete all required fields (marked with ⚠)
          </p>
        )}
      </div>
    </div>
  );
}
