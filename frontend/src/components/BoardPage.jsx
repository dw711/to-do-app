import { useEffect, useState } from 'react';
import Board from './Board';
import TaskModal from './TaskModal';
import { apiJson } from '../api';
import { useAuth } from '../AuthContext';

export default function BoardPage() {
  const { user, logout } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [tags, setTags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [moveError, setMoveError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [createStatus, setCreateStatus] = useState('todo');
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('taskboard_theme') === 'dark');

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? 'dark' : 'light';
    localStorage.setItem('taskboard_theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  useEffect(() => {
    apiJson('/api/tasks').then(setTasks).catch(err => setError(err.message)).finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    apiJson('/api/tags').then(setTags).catch(() => {});
  }, []);
  const openCreate = (status = 'todo') => { setEditingTask(null); setCreateStatus(status); setModalOpen(true); };
  const openEdit = task => { setEditingTask(task); setModalOpen(true); };
  const closeModal = () => { setModalOpen(false); setEditingTask(null); };

  async function handleSubmit(data, tagIds) {
    const editing = Boolean(editingTask);
    const updated = await apiJson(editing ? `/api/tasks/${editingTask.id}` : '/api/tasks', {
      method: editing ? 'PATCH' : 'POST', body: JSON.stringify(data),
    });
    setTasks(current => editing ? current.map(task => task.id === updated.id ? updated : task) : [...current, updated]);
    // Tag changes are sent separately, per the design — replace the whole set so the returned task reflects them.
    if (Array.isArray(tagIds)) {
      const withTags = await apiJson(`/api/tasks/${updated.id}/tags`, {
        method: 'PUT', body: JSON.stringify({ tag_ids: tagIds }),
      });
      setTasks(current => current.map(task => task.id === withTags.id ? withTags : task));
    }
    closeModal();
  }
  async function handleCreateTag(data) {
    const tag = await apiJson('/api/tags', { method: 'POST', body: JSON.stringify(data) });
    setTags(current => [...current, tag]);
    return tag;
  }
  async function handleDeleteTag(tagId) {
    await apiJson(`/api/tags/${tagId}`, { method: 'DELETE' });
    setTags(current => current.filter(tag => tag.id !== tagId));
    setTasks(current => current.map(task => ({
      ...task,
      tags: (task.tags ?? []).filter(tag => tag.id !== tagId),
    })));
  }
  async function handleDelete() {
    await apiJson(`/api/tasks/${editingTask.id}`, { method: 'DELETE' });
    setTasks(current => current.filter(task => task.id !== editingTask.id));
    closeModal();
  }
  async function handleMoveTask(taskId, newStatus, newPosition) {
    const previousTasks = tasks;
    const columns = new Map();
    for (const task of tasks) {
      const columnTasks = columns.get(task.status) ?? [];
      columnTasks.push(task);
      columns.set(task.status, columnTasks);
    }
    for (const columnTasks of columns.values()) {
      columnTasks.sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
    }

    const movingTask = tasks.find(task => task.id === taskId);
    if (!movingTask) return;
    const sourceTasks = columns.get(movingTask.status) ?? [];
    const oldIndex = sourceTasks.findIndex(task => task.id === taskId);
    sourceTasks.splice(oldIndex, 1);

    const destinationTasks = columns.get(newStatus) ?? [];
    columns.set(newStatus, destinationTasks);
    destinationTasks.splice(Math.max(0, Math.min(newPosition, destinationTasks.length)), 0, {
      ...movingTask,
      status: newStatus,
    });

    const optimisticTasks = [...columns.values()].flatMap(columnTasks =>
      columnTasks.map((task, position) => ({ ...task, position })),
    );
    setTasks(optimisticTasks);
    setMoveError('');
    try {
      await apiJson(`/api/tasks/${taskId}/move`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus, position: newPosition }),
      });
    } catch (err) {
      setTasks(previousTasks);
      setMoveError(`Couldn't move task: ${err.message}`);
    }
  }

  if (loading) return <div>Loading tasks...</div>;
  if (error) return <div>Error: {error}</div>;
  return <div className="app">
    <header className="topbar"><h1 className="app-name">TaskBoard</h1><div className="user-actions">
      <span>{user?.display_name}</span><button onClick={logout}>Log out</button>
      <button
        type="button"
        className="theme-toggle"
        onClick={() => setDarkMode(current => !current)}
        aria-label={`Switch to ${darkMode ? 'light' : 'dark'} mode`}
        aria-pressed={darkMode}
      >
        {darkMode ? '☀ Light mode' : '☾ Dark mode'}
      </button>
      <button className="new-task-btn" onClick={() => openCreate()}>+ New Task</button>
    </div></header>
    {moveError && <div className="board-toast" role="alert">
      <span>{moveError}</span>
      <button type="button" aria-label="Dismiss error" onClick={() => setMoveError('')}>×</button>
    </div>}
    <Board tasks={tasks} onEditTask={openEdit} onMoveTask={handleMoveTask} onAddTask={openCreate} />
    {/* key remounts the modal per task so its tag selection re-initialises from task.tags */}
    <TaskModal key={editingTask?.id ?? 'new'} isOpen={modalOpen} task={editingTask} defaultStatus={createStatus} onClose={closeModal} onSubmit={handleSubmit} onDelete={handleDelete} tags={tags} onCreateTag={handleCreateTag} onDeleteTag={handleDeleteTag} />
  </div>;
}