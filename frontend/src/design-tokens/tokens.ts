/**
 * AADAP Design Tokens
 * Source: DESIGN_SYSTEM.md (authoritative)
 *
 * These are value-only constants. No CSS is generated or applied here.
 * Phase 7.1: Import only — no usage in layouts or pages.
 */

// ---------- Colors ----------

export const colors = {
    neutral: {
        white: '#FFFFFF',
        50: '#F7F8FA',
        100: '#EEEEF0',
        200: '#E2E2E8',
        300: '#C8C8D0',
        500: '#71717A',
        700: '#3F3F46',
        900: '#1A1A2E',
    },
    primary: {
        100: '#EEF2FF',
        500: '#4A6CF7',
        600: '#3B5DE6',
    },
    semantic: {
        info: {
            foreground: '#64748B',
            background: '#F8FAFC',
        },
        success: {
            foreground: '#059669',
            background: '#ECFDF5',
        },
        warning: {
            foreground: '#D97706',
            background: '#FFFBEB',
        },
        destructive: {
            foreground: '#DC2626',
            background: '#FFF1F2',
        },
    },
} as const

// ---------- Typography ----------

export const typography = {
    fontFamily: {
        sans: 'Inter, system-ui, sans-serif',
        mono: 'JetBrains Mono, monospace',
    },
    fontSize: {
        pageTitle: '20px',
        sectionHeading: '16px',
        body: '14px',
        caption: '12px',
        monospace: '13px',
    },
    fontWeight: {
        regular: 400,
        medium: 500,
        semibold: 600,
    },
    lineHeight: {
        body: 1.5,
    },
} as const

// ---------- Spacing ----------

export const spacing = {
    1: '4px',
    2: '8px',
    3: '12px',
    4: '16px',
    6: '24px',
    8: '32px',
} as const

// ---------- Border Radius ----------

export const borderRadius = {
    md: '6px',
} as const
