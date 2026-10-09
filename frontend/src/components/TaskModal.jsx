import { useEffect, useState, useRef } from 'react';

export default function TaskModal({ isOpen, task, defaultStatus, onClose, onSubmit, onDelete, tags = [], onCreateTag, onDeleteTag }) {
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [selectedTagIds, setSelectedTagIds] = useState(() => (task?.tags ?? []).map(tag => tag.id));
    const [newTagName, setNewTagName] = useState('');
    const [newTagColour, setNewTagColour] = useState('#6c8ebf');
    const [creatingTag, setCreatingTag] = useState(false);
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
            }, selectedTagIds);
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

    function toggleTag(tagId) {
        setSelectedTagIds(current =>
            current.includes(tagId) ? current.filter(id => id !== tagId) : [...current, tagId]
        );
    }

    async function handleCreateTag() {
        const name = newTagName.trim();
        if (!name) return;
        setCreatingTag(true);
        setError('');
        try {
            const tag = await onCreateTag({ name, colour: newTagColour });
            setSelectedTagIds(current => current.includes(tag.id) ? current : [...current, tag.id]);
            setNewTagName('');
        } catch (err) {
            setError(err.message || 'Unable to create the tag.');
        } finally {
            setCreatingTag(false);
        }
    }

    async function handleDeleteTag(tagId) {
        if (!window.confirm('Delete this tag? It will be removed from every task that uses it.')) return;
        setError('');
        try {
            await onDeleteTag(tagId);
            setSelectedTagIds(current => current.filter(id => id !== tagId));
        } catch (err) {
            setError(err.message || 'Unable to delete the tag.');
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
            <label className="field-label">
            Due date
            <input
                ref = {dateRef}
                name = "due_date"
                type = "date"
                defaultValue = {task?.due_date ?? ""}
            />
            </label>

            <section className="tag-picker" aria-label="Tags">
                <h3>Tags</h3>
                {tags.length > 0 && (
                <div className="tag-picker-list">
                    {tags.map(tag => {
                        const selected = selectedTagIds.includes(tag.id);
                        return (
                        <span key={tag.id} className={`tag-option${selected ? ' tag-option-selected' : ''}`}>
                            <button
                                type="button"
                                className="tag-option-toggle"
                                aria-pressed={selected}
                                style={selected ? { background: tag.colour, borderColor: tag.colour } : undefined}
                                onClick={() => toggleTag(tag.id)}
                            >
                                <span className="tag-option-dot" style={{ background: tag.colour }} aria-hidden="true" />
                                {tag.name}
                            </button>
                            <button
                                type="button"
                                className="tag-option-remove"
                                aria-label={`Delete tag ${tag.name}`}
                                title="Delete tag"
                                onClick={() => handleDeleteTag(tag.id)}
                            >×</button>
                        </span>
                        );
                    })}
                </div>
                )}
                <div className="tag-create">
                    <input
                        className="tag-create-name"
                        value={newTagName}
                        onChange={e => setNewTagName(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleCreateTag(); } }}
                        placeholder="New tag name"
                        maxLength={50}
                        aria-label="New tag name"
                    />
                    <input
                        className="tag-create-colour"
                        type="color"
                        value={newTagColour}
                        onChange={e => setNewTagColour(e.target.value)}
                        aria-label="Pick a tag colour"
                        title="Pick a colour"
                    />
                    <button
                        type="button"
                        className="tag-create-btn"
                        disabled={!newTagName.trim() || creatingTag}
                        onClick={handleCreateTag}
                    >+ Tag</button>
                </div>
            </section>

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