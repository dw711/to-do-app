import { useEffect } from 'react';

export default function TaskModal({ isOpen, task, defaultStatus, onClose, onSubmit, onDelete }) {
    // Esc to close — must be before the early return (rules of hooks)
    useEffect(() => {
        if (!isOpen) return;
        function onKey(e) { if (e.key === 'Escape') onClose(); }
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    const isEdit = Boolean(task);

    function handleSubmit(e) {
        e.preventDefault();
        const fd = new FormData(e.target);
        onSubmit({
        title: fd.get('title'),
        description: fd.get('description'),
        status: fd.get('status'),
        priority: fd.get('priority'),
        });
    }

    return (
        <div className="modal-backdrop" onClick={onClose}>
        <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{isEdit ? 'Edit Task' : 'New Task'}</h2>
            {/* key forces the form to reset defaultValues when switching tasks/modes */}
            <form key={isEdit ? task.id : `new-${defaultStatus}`} onSubmit={handleSubmit}>
            <input name="title" placeholder="Title" defaultValue={task?.title ?? ''} required />
            <textarea name="description" placeholder="Description" defaultValue={task?.description ?? ''} rows={3} />
            <select name="status" defaultValue={task?.status ?? defaultStatus}>
                <option value="todo">To Do</option>
                <option value="in_progress">In Progress</option>
                <option value="done">Completed</option>
            </select>
            <select name="priority" defaultValue={task?.priority ?? 'medium'}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
            </select>
            <div className="modal-actions">
                {isEdit && (
                <button type="button" className="delete-btn"
                    onClick={() => { if (window.confirm('Delete this task?')) onDelete(); }}>
                    Delete
                </button>
                )}
                <button type="button" onClick={onClose}>Cancel</button>
                <button type="submit" className="save-btn">{isEdit ? 'Save' : 'Create'}</button>
            </div>
            </form>
        </div>
        </div>
    );
}