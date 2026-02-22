/**
 * AADAP — RequirementsPanel Component
 * ======================================
 * Displays extracted requirements with progressive disclosure and editing.
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
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-1">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {label}
        </label>
        {isIncomplete && (
          <span className="text-amber-500 text-lg" title="Incomplete or low confidence">
            ⚠
          </span>
        )}
        {hasValue && (
          <span className="text-xs text-gray-400">
            {Math.round(confidence * 100)}% confident
          </span>
        )}
      </div>
      {isList ? (
        <textarea
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md 
                     focus:outline-none focus:ring-2 focus:ring-blue-500
                     dark:bg-gray-800 dark:border-gray-600 dark:text-white"
          rows={3}
          value={displayValue}
          onChange={(e) => onChange(e.target.value.split('\n').filter(Boolean))}
          placeholder={`Enter ${label.toLowerCase()}...`}
        />
      ) : (
        <input
          type="text"
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md 
                     focus:outline-none focus:ring-2 focus:ring-blue-500
                     dark:bg-gray-800 dark:border-gray-600 dark:text-white"
          value={displayValue}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`Enter ${label.toLowerCase()}...`}
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

  return (
    <div className="h-full flex flex-col bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Requirements
        </h2>
        <p className="text-sm text-gray-500">
          {filledCount}/4 required fields
        </p>
      </div>

      {/* Core Fields */}
      <div className="flex-1 overflow-y-auto p-4">
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
        <div className="mt-4">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700"
          >
            <svg
              className={`w-4 h-4 transition-transform ${showDetails ? 'rotate-90' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            {showDetails ? 'Hide Details' : 'Show Details'}
          </button>

          {showDetails && (
            <div className="mt-3 space-y-4">
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
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={onCreateTask}
          disabled={!isComplete || isCreating}
          className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-colors ${
            isComplete && !isCreating
              ? 'bg-blue-600 hover:bg-blue-700 cursor-pointer'
              : 'bg-gray-300 dark:bg-gray-700 cursor-not-allowed'
          }`}
          title={!isComplete ? 'Complete all required fields' : undefined}
        >
          {isCreating ? 'Creating...' : 'Create Task'}
        </button>
        {!isComplete && (
          <p className="mt-2 text-xs text-center text-gray-500">
            Complete all required fields (marked with ⚠)
          </p>
        )}
      </div>
    </div>
  );
}
