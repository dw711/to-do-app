import { useEffect, useState } from 'react';
import Board from './components/Board';
import TaskModal from './components/TaskModal';
import './App.css';

function App() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [createStatus, setCreateStatus] = useState('todo');

  useEffect(() => {
    fetch('/api/tasks')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => { setTasks(data); setLoading(false); })
      .catch(err => { setError(err.message); setLoading(false); });
  }, []);

  function openCreate(status = 'todo') {
    setEditingTask(null);
    setCreateStatus(status);
    setModalOpen(true);
  }

  function openEdit(task) {
    setEditingTask(task);
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingTask(null);
  }
  
  async function handleSubmit(data) {
    if (editingTask) {
      const res = await fetch(`/api/tasks/${editingTask.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const updated = await res.json();
      setTasks(tasks.map(t => (t.id === updated.id ? updated : t)));
    } else {
      const res = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const created = await res.json();
      setTasks([...tasks, created]);
    }
    closeModal();
  }

  async function handleDelete() {
    await fetch(`/api/tasks/${editingTask.id}`, { method: 'DELETE' });
    setTasks(tasks.filter(t => t.id !== editingTask.id));
    closeModal();
  }

  // ---- NEW: Handle the drag-and-drop move ----
  async function handleMoveTask(taskId, newStatus, newPosition) {
    // 1. Optimistically update the local tasks state
    setTasks(prev => {
      const index = prev.findIndex(t => t.id === taskId);
      if (index === -1) return prev;
      
      const updatedTask = { ...prev[index], status: newStatus, position: newPosition };
      const newTasks = [...prev];
      newTasks[index] = updatedTask;

      // Simple re-sort by status then position (optional, but keeps array clean)
      newTasks.sort((a, b) => {
        if (a.status !== b.status) return a.status.localeCompare(b.status);
        return a.position - b.position;
      });

      return newTasks;
    });

    // 2. Send the move to the backend
    try {
      await fetch(`/api/tasks/${taskId}/move`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus, position: newPosition }),
      });
    } catch (err) {
      // Optional: rollback or show error toast here
      console.error('Failed to move task', err);
    }
  }

  if (loading) return <div>Loading tasks...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="app">
      <header className="topbar">
        <h1 className="app-name">TaskBoard</h1>
        <button className="new-task-btn" onClick={() => openCreate()}>+ New Task</button>
      </header>
      <Board 
        tasks={tasks} 
        onEditTask={openEdit} 
        onMoveTask={handleMoveTask}
      />
      <TaskModal
        isOpen={modalOpen}
        task={editingTask}
        defaultStatus={createStatus}
        onClose={closeModal}
        onSubmit={handleSubmit}
        onDelete={handleDelete}
      />
    </div>
  );
}

export default App;