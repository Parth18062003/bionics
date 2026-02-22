/**
 * AADAP — LogFilters Component
 * ==============================
 * Multi-select dropdown for log levels and search input.
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import type { LogLevel } from '@/types/log';

interface LogFiltersProps {
  levels: LogLevel[];
  onLevelChange: (levels: LogLevel[]) => void;
  search: string;
  onSearchChange: (search: string) => void;
  onReset?: () => void;
}

const LEVELS: LogLevel[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

const LEVEL_COLORS: Record<LogLevel, string> = {
  DEBUG: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  INFO: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  WARNING: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  ERROR: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
};

export function LogFilters({
  levels,
  onLevelChange,
  search,
  onSearchChange,
  onReset,
}: LogFiltersProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleLevel = (level: LogLevel) => {
    if (levels.includes(level)) {
      onLevelChange(levels.filter((l) => l !== level));
    } else {
      onLevelChange([...levels, level]);
    }
  };

  const selectAll = () => {
    onLevelChange(LEVELS);
  };

  const clearAll = () => {
    onLevelChange([]);
  };

  const handleReset = () => {
    onLevelChange([]);
    onSearchChange('');
    onReset?.();
  };

  return (
    <div className="flex items-center gap-3">
      {/* Level Multi-Select Dropdown */}
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          <span>Levels</span>
          {levels.length > 0 && (
            <span className="px-1.5 py-0.5 text-xs bg-blue-500 text-white rounded">
              {levels.length}
            </span>
          )}
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {isOpen && (
          <div className="absolute top-full left-0 mt-1 w-48 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50">
            <div className="p-2 border-b border-gray-200 dark:border-gray-700 flex justify-between">
              <button
                onClick={selectAll}
                className="text-xs text-blue-500 hover:text-blue-700"
              >
                Select all
              </button>
              <button
                onClick={clearAll}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                Clear all
              </button>
            </div>
            <div className="p-2 space-y-1">
              {LEVELS.map((level) => (
                <label
                  key={level}
                  className="flex items-center gap-2 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={levels.includes(level)}
                    onChange={() => toggleLevel(level)}
                    className="w-4 h-4 rounded border-gray-300 dark:border-gray-600"
                  />
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${LEVEL_COLORS[level]}`}>
                    {level}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Search Input */}
      <div className="relative flex-1 max-w-md">
        <svg
          className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          type="text"
          placeholder="Search logs..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700"
        />
      </div>

      {/* Reset Button */}
      {(levels.length > 0 || search) && (
        <button
          onClick={handleReset}
          className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        >
          Reset
        </button>
      )}
    </div>
  );
}
