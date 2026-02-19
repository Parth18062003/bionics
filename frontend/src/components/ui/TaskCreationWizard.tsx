'use client';

import { useState, useEffect } from 'react';
import type { QuickAction, TaskMode, OperationType, CatalogResponse, SchemaResponse, TableResponse } from '@/api/types';
import { QUICK_ACTIONS } from '@/api/types';
import { listCatalogs, listSchemas, listTables, createTask } from '@/api/client';
import { ErrorBanner } from './ErrorBanner';

interface TaskCreationWizardProps {
    onComplete?: (taskId: string) => void;
    onCancel?: () => void;
    preselectedAction?: QuickAction;
}

type WizardStep = 'select-mode' | 'configure' | 'preview';

const TASK_MODE_CONFIG: Record<TaskMode, { label: string; description: string; icon: string }> = {
    generate_code: { label: 'Generate Code', description: 'Create new code artifacts', icon: '💻' },
    execute_code: { label: 'Execute Code', description: 'Run existing code', icon: '▶️' },
    read: { label: 'Read Data', description: 'View and preview data', icon: '👁️' },
    list: { label: 'List Resources', description: 'Browse catalogs, tables, files', icon: '📋' },
    manage: { label: 'Manage Resources', description: 'Create, update, or delete resources', icon: '⚙️' },
};

export function TaskCreationWizard({ onComplete, onCancel, preselectedAction }: TaskCreationWizardProps) {
    const [step, setStep] = useState<WizardStep>(preselectedAction ? 'configure' : 'select-mode');
    const [selectedMode, setSelectedMode] = useState<TaskMode | null>(preselectedAction?.task_mode ?? null);
    const [selectedAction, setSelectedAction] = useState<QuickAction | null>(preselectedAction ?? null);
    const [platform, setPlatform] = useState<'fabric' | 'databricks'>(preselectedAction?.platform as 'fabric' | 'databricks' ?? 'databricks');
    
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [environment, setEnvironment] = useState<'SANDBOX' | 'PRODUCTION'>('SANDBOX');
    
    const [catalogs, setCatalogs] = useState<CatalogResponse[]>([]);
    const [schemas, setSchemas] = useState<SchemaResponse[]>([]);
    const [tables, setTables] = useState<TableResponse[]>([]);
    const [selectedCatalog, setSelectedCatalog] = useState('');
    const [selectedSchema, setSelectedSchema] = useState('');
    const [selectedTable, setSelectedTable] = useState('');
    
    const [loading, setLoading] = useState(false);
    const [loadingCatalogs, setLoadingCatalogs] = useState(false);
    const [loadingSchemas, setLoadingSchemas] = useState(false);
    const [loadingTables, setLoadingTables] = useState(false);
    const [error, setError] = useState<string | null>(null);
    
    const filteredActions = QUICK_ACTIONS.filter(a => 
        selectedMode ? a.task_mode === selectedMode : true
    );
    
    useEffect(() => {
        if (step === 'configure' && platform) {
            loadCatalogs();
        }
    }, [step, platform]);
    
    useEffect(() => {
        if (selectedCatalog) {
            loadSchemas(selectedCatalog);
        } else {
            setSchemas([]);
        }
        setSelectedSchema('');
        setTables([]);
        setSelectedTable('');
    }, [selectedCatalog]);
    
    useEffect(() => {
        if (selectedCatalog && selectedSchema) {
            loadTables(selectedCatalog, selectedSchema);
        } else {
            setTables([]);
        }
        setSelectedTable('');
    }, [selectedCatalog, selectedSchema]);
    
    async function loadCatalogs() {
        setLoadingCatalogs(true);
        try {
            const result = await listCatalogs(platform);
            setCatalogs(result);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load catalogs');
        } finally {
            setLoadingCatalogs(false);
        }
    }
    
    async function loadSchemas(catalog: string) {
        setLoadingSchemas(true);
        try {
            const result = await listSchemas(platform, catalog);
            setSchemas(result);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load schemas');
        } finally {
            setLoadingSchemas(false);
        }
    }
    
    async function loadTables(catalog: string, schema: string) {
        setLoadingTables(true);
        try {
            const result = await listTables(platform, catalog, schema);
            setTables(result);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load tables');
        } finally {
            setLoadingTables(false);
        }
    }
    
    function handleActionSelect(action: QuickAction) {
        setSelectedAction(action);
        setSelectedMode(action.task_mode);
        if (action.platform !== 'any') {
            setPlatform(action.platform as 'fabric' | 'databricks');
        }
        setTitle(action.label);
        setDescription(action.description);
        setStep('configure');
    }
    
    function handleModeSelect(mode: TaskMode) {
        setSelectedMode(mode);
    }
    
    function canProceed(): boolean {
        if (!selectedMode) return false;
        
        if (['list', 'read', 'manage'].includes(selectedMode)) {
            if (!selectedCatalog) return false;
            if (['list_tables', 'preview_table', 'get_schema'].includes(selectedAction?.operation_type ?? '') && !selectedSchema) return false;
            if (['preview_table', 'get_schema'].includes(selectedAction?.operation_type ?? '') && !selectedTable) return false;
        }
        
        if (!title.trim()) return false;
        
        return true;
    }
    
    async function handleSubmit() {
        if (!canProceed()) return;
        
        setLoading(true);
        setError(null);
        
        try {
            const task = await createTask({
                title: title.trim(),
                description: description.trim() || undefined,
                environment,
                task_mode: selectedMode ?? undefined,
                operation_type: selectedAction?.operation_type,
                platform,
                catalog: selectedCatalog || undefined,
                schema_name: selectedSchema || undefined,
                table: selectedTable || undefined,
                selection_context: selectedCatalog ? {
                    catalog: selectedCatalog,
                    schema: selectedSchema || null,
                    table: selectedTable || null,
                } : undefined,
            });
            
            onComplete?.(task.id);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to create task');
        } finally {
            setLoading(false);
        }
    }
    
    return (
        <div className="card" style={{ maxWidth: 800 }}>
            {error && <ErrorBanner message={error} />}
            
            {/* Step indicator */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-sm)',
                    marginBottom: 'var(--space-xl)',
                    fontSize: 'var(--font-size-sm)',
                }}
            >
                {['select-mode', 'configure', 'preview'].map((s, i) => (
                    <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                        {i > 0 && <span style={{ color: 'var(--color-text-tertiary)' }}>→</span>}
                        <div
                            style={{
                                padding: 'var(--space-xs) var(--space-sm)',
                                borderRadius: 'var(--radius-sm)',
                                background: step === s ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
                                color: step === s ? 'white' : 'var(--color-text-secondary)',
                            }}
                        >
                            {i + 1}. {s === 'select-mode' ? 'Select' : s === 'configure' ? 'Configure' : 'Preview'}
                        </div>
                    </div>
                ))}
            </div>
            
            {/* Step 1: Select Mode / Quick Action */}
            {step === 'select-mode' && (
                <div>
                    <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
                        What would you like to do?
                    </h2>
                    
                    {/* Task Modes */}
                    <div
                        style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                            gap: 'var(--space-md)',
                            marginBottom: 'var(--space-xl)',
                        }}
                    >
                        {(Object.keys(TASK_MODE_CONFIG) as TaskMode[]).map(mode => {
                            const config = TASK_MODE_CONFIG[mode];
                            return (
                                <button
                                    key={mode}
                                    type="button"
                                    onClick={() => handleModeSelect(mode)}
                                    style={{
                                        padding: 'var(--space-md)',
                                        borderRadius: 'var(--radius-md)',
                                        border: selectedMode === mode ? '2px solid var(--color-accent)' : '1px solid var(--color-border)',
                                        background: selectedMode === mode ? 'var(--color-accent-muted)' : 'var(--color-bg-secondary)',
                                        cursor: 'pointer',
                                        textAlign: 'left',
                                    }}
                                >
                                    <div style={{ fontSize: '1.25rem', marginBottom: 'var(--space-xs)' }}>{config.icon}</div>
                                    <div style={{ fontWeight: 600, marginBottom: 'var(--space-xs)' }}>{config.label}</div>
                                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                                        {config.description}
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                    
                    {/* Quick Actions */}
                    {selectedMode && (
                        <>
                            <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
                                Quick Actions
                            </h3>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                                {filteredActions.map(action => (
                                    <button
                                        key={action.id}
                                        type="button"
                                        onClick={() => handleActionSelect(action)}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 'var(--space-md)',
                                            padding: 'var(--space-md) var(--space-lg)',
                                            borderRadius: 'var(--radius-md)',
                                            border: '1px solid var(--color-border)',
                                            background: 'var(--color-bg-secondary)',
                                            cursor: 'pointer',
                                            textAlign: 'left',
                                        }}
                                    >
                                        <span style={{ fontSize: '1.25rem' }}>{action.icon}</span>
                                        <div>
                                            <div style={{ fontWeight: 500 }}>{action.label}</div>
                                            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                                                {action.description}
                                            </div>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </>
                    )}
                    
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--space-xl)' }}>
                        <button
                            type="button"
                            className="btn btn-primary"
                            disabled={!selectedMode}
                            onClick={() => setStep('configure')}
                        >
                            Continue
                        </button>
                    </div>
                </div>
            )}
            
            {/* Step 2: Configure */}
            {step === 'configure' && (
                <div>
                    <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
                        Configure Task
                    </h2>
                    
                    {/* Platform selection */}
                    <div className="form-group">
                        <label className="form-label">Platform</label>
                        <div style={{ display: 'flex', gap: 'var(--space-md)' }}>
                            {['databricks', 'fabric'].map(p => (
                                <button
                                    key={p}
                                    type="button"
                                    onClick={() => setPlatform(p as 'fabric' | 'databricks')}
                                    style={{
                                        flex: 1,
                                        padding: 'var(--space-md)',
                                        borderRadius: 'var(--radius-md)',
                                        border: platform === p ? '2px solid var(--color-accent)' : '1px solid var(--color-border)',
                                        background: platform === p ? 'var(--color-accent-muted)' : 'var(--color-bg-secondary)',
                                        cursor: 'pointer',
                                    }}
                                >
                                    {p === 'databricks' ? '⚡ Databricks' : '🔷 Microsoft Fabric'}
                                </button>
                            ))}
                        </div>
                    </div>
                    
                    {/* Title & Description */}
                    <div className="form-group">
                        <label htmlFor="wizard-title" className="form-label">Task Title *</label>
                        <input
                            id="wizard-title"
                            type="text"
                            className="form-input"
                            value={title}
                            onChange={e => setTitle(e.target.value)}
                            placeholder="Enter a descriptive title"
                        />
                    </div>
                    
                    <div className="form-group">
                        <label htmlFor="wizard-description" className="form-label">Description</label>
                        <textarea
                            id="wizard-description"
                            className="form-textarea"
                            value={description}
                            onChange={e => setDescription(e.target.value)}
                            rows={3}
                            placeholder="Additional details or constraints"
                        />
                    </div>
                    
                    {/* Selection context for list/read/manage modes */}
                    {['list', 'read', 'manage'].includes(selectedMode ?? '') && (
                        <div
                            className="card"
                            style={{ padding: 'var(--space-lg)', borderLeft: '3px solid var(--color-accent)', marginBottom: 'var(--space-lg)' }}
                        >
                            <div className="font-semibold mb-md" style={{ fontSize: 'var(--font-size-sm)' }}>
                                📂 Resource Selection
                            </div>
                            
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-md)' }}>
                                <div className="form-group">
                                    <label htmlFor="wizard-catalog" className="form-label">Catalog</label>
                                    <select
                                        id="wizard-catalog"
                                        className="form-select"
                                        value={selectedCatalog}
                                        onChange={e => setSelectedCatalog(e.target.value)}
                                        disabled={loadingCatalogs}
                                    >
                                        <option value="">{loadingCatalogs ? 'Loading...' : 'Select catalog'}</option>
                                        {catalogs.map(c => (
                                            <option key={c.id} value={c.name}>{c.name}</option>
                                        ))}
                                    </select>
                                </div>
                                
                                <div className="form-group">
                                    <label htmlFor="wizard-schema" className="form-label">Schema</label>
                                    <select
                                        id="wizard-schema"
                                        className="form-select"
                                        value={selectedSchema}
                                        onChange={e => setSelectedSchema(e.target.value)}
                                        disabled={!selectedCatalog || loadingSchemas}
                                    >
                                        <option value="">{loadingSchemas ? 'Loading...' : 'Select schema'}</option>
                                        {schemas.map(s => (
                                            <option key={s.id} value={s.name}>{s.name}</option>
                                        ))}
                                    </select>
                                </div>
                                
                                <div className="form-group">
                                    <label htmlFor="wizard-table" className="form-label">Table</label>
                                    <select
                                        id="wizard-table"
                                        className="form-select"
                                        value={selectedTable}
                                        onChange={e => setSelectedTable(e.target.value)}
                                        disabled={!selectedSchema || loadingTables}
                                    >
                                        <option value="">{loadingTables ? 'Loading...' : 'Select table'}</option>
                                        {tables.map(t => (
                                            <option key={t.id} value={t.name}>{t.name}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </div>
                    )}
                    
                    {/* Environment */}
                    <div className="form-group">
                        <label className="form-label">Environment</label>
                        <div style={{ display: 'flex', gap: 'var(--space-md)' }}>
                            {['SANDBOX', 'PRODUCTION'].map(env => (
                                <button
                                    key={env}
                                    type="button"
                                    onClick={() => setEnvironment(env as 'SANDBOX' | 'PRODUCTION')}
                                    style={{
                                        flex: 1,
                                        padding: 'var(--space-sm) var(--space-md)',
                                        borderRadius: 'var(--radius-sm)',
                                        border: environment === env ? '2px solid var(--color-accent)' : '1px solid var(--color-border)',
                                        background: environment === env ? 'var(--color-accent-muted)' : 'var(--color-bg-secondary)',
                                        cursor: 'pointer',
                                    }}
                                >
                                    {env === 'SANDBOX' ? '🧪 Sandbox' : '🏭 Production'}
                                </button>
                            ))}
                        </div>
                    </div>
                    
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 'var(--space-xl)' }}>
                        <button type="button" className="btn btn-ghost" onClick={() => setStep('select-mode')}>
                            ← Back
                        </button>
                        <button
                            type="button"
                            className="btn btn-primary"
                            disabled={!canProceed()}
                            onClick={handleSubmit}
                        >
                            {loading ? (
                                <>
                                    <div className="loading-spinner" style={{ width: 16, height: 16 }} />
                                    Creating...
                                </>
                            ) : (
                                'Create Task'
                            )}
                        </button>
                    </div>
                </div>
            )}
            
            {onCancel && (
                <button type="button" className="btn btn-ghost" onClick={onCancel} style={{ marginTop: 'var(--space-md)' }}>
                    Cancel
                </button>
            )}
        </div>
    );
}
