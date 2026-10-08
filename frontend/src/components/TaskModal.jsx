import { useEffect, useState, useRef } from 'react';

export default function TaskModal({ isOpen, task, defaultStatus, onClose, onSubmit, onDelete }) {
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const dateRef = useRef(null);
    // Esc to close — must be before the early return (rules of hooks)
    useEffect(() => {
        if (!isOpen) return;
        function onKey(e) { if (e.key === 'Escape') onClose(); }
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [isOpen, onClose, task?.id, task?.due_date]);

    if (!isOpen) return null;
    

    const isEdit = Boolean(task);

    async function handleSubmit(e) {
        e.preventDefault();
        const fd = new FormData(e.target);
        setSaving(true);
        setError('');
        try {
            await onSubmit({
                title: fd.get('title'),
                description: fd.get('description'),
                status: fd.get('status'),
                priority: fd.get('priority'),
                due_date: fd.get('due_date') || null,
            });
        } catch (err) {
            setError(err.message || 'Unable to save the task.');
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete() {
        setSaving(true);
        setError('');
        try {
            await onDelete();
        } catch (err) {
            setError(err.message || 'Unable to delete the task.');
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="modal-backdrop" onClick={onClose}>
        <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{isEdit ? 'Edit Task' : 'New Task'}</h2>
            {/* key forces the form to reset defaultValues when switching tasks/modes */}
            <form key={isEdit ? task.id : `new-${defaultStatus}`} onSubmit={handleSubmit}>
            <label className="field-label">Title
                <input name="title" placeholder="Give this task a title" defaultValue={task?.title ?? ''} maxLength={200} required />
            </label>
            <label className="field-label">Description
                <textarea name="description" placeholder="Add a few details (optional)" defaultValue={task?.description ?? ''} rows={3} maxLength={2000} />
            </label>
            <label className="field-label">Status
            <select name="status" defaultValue={task?.status ?? defaultStatus}>
                <option value="todo">To Do</option>
                <option value="in_progress">In Progress</option>
                <option value="done">Completed</option>
            </select>
            </label>
            <label className = "field-label">Priority
            <select name="priority" defaultValue={task?.priority ?? "medium"}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
            </select>
            </label>
            <label>
            Due date
            <input
                ref = {dateRef}
                name = "due_date"
                type = "date"
                defaultValue = {task?.due_date ?? ""}
            />
            </label>

            {error && <div className="auth-error" role="alert">{error}</div>}
            <div className="modal-actions">
                {isEdit && (
                <button type="button" className="delete-btn"
                    disabled={saving}
                    onClick={() => { if (window.confirm('Delete this task?')) handleDelete(); }}>
                    Delete
                </button>
                )}
                <button type="button" onClick={onClose} disabled={saving}>Cancel</button>
                <button type="submit" className="save-btn" disabled={saving}>{saving ? 'Saving…' : isEdit ? 'Save' : 'Create'}</button>
            </div>
            </form>
        </div>
        </div>
    );
}