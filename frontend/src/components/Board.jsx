import { useState, useEffect } from 'react';
import { 
DndContext, 
PointerSensor, 
KeyboardSensor, 
useSensor, 
useSensors, 
closestCorners, 
DragOverlay 
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import Column from './Column';
import TaskCard from './TaskCard';

const COLUMNS = [
{ id: 'todo', label: 'To Do' },
{ id: 'in_progress', label: 'In Progress' },
{ id: 'done', label: 'Completed' },
];

export default function Board({ tasks, onEditTask, onMoveTask }) {
// Local state for instant visual feedback during drag
const [localTasks, setLocalTasks] = useState(tasks);
const [activeTask, setActiveTask] = useState(null);

// Sync local state when parent props change
useEffect(() => {
    setLocalTasks(tasks);
}, [tasks]);

const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
);

function handleDragStart(event) {
    setActiveTask(tasks.find(t => t.id === event.active.id));
}

function handleDragOver(event) {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id;
    const overId = over.id;

    const activeTask = localTasks.find(t => t.id === activeId);
    if (!activeTask) return;

    // Determine target column: if over a task, use its status; if over a column, use column id
    const overTask = localTasks.find(t => t.id === overId);
    const overColumnId = overTask ? overTask.status : overId;

    // If hovering over a new column, update the status in localTasks
    if (activeTask.status !== overColumnId) {
    setLocalTasks(prev => {
        const activeIndex = prev.findIndex(t => t.id === activeId);
        const updatedTask = { ...prev[activeIndex], status: overColumnId };
        const updatedTasks = [...prev];
        updatedTasks.splice(activeIndex, 1);
        updatedTasks.push(updatedTask);
        return updatedTasks;
    });
    }
}

function handleDragEnd(event) {
    const { active, over } = event;
    setActiveTask(null);
    if (!over) return;

    const activeId = active.id;
    const overId = over.id;

    // Find the moved task and the target task/column
    const activeIndex = localTasks.findIndex(t => t.id === activeId);
    const overTask = localTasks.find(t => t.id === overId);
    const overIndex = overTask ? localTasks.findIndex(t => t.id === overId) : localTasks.length;

    if (activeIndex === -1 || overIndex === -1) return;

    // Create new array with the moved item in its final spot
    const updatedTasks = [...localTasks];
    const [movedTask] = updatedTasks.splice(activeIndex, 1);
    updatedTasks.splice(overIndex, 0, movedTask);

    // Update local visual state immediately
    setLocalTasks(updatedTasks);

    // Calculate the new position for the backend (it's just the array index now)
    const newPosition = overIndex;
    const newStatus = movedTask.status;

    // Call the parent's handler to persist the move
    if (onMoveTask) {
    onMoveTask(movedTask.id, newStatus, newPosition);
    }
}

return (
    <DndContext 
    sensors={sensors}
    collisionDetection={closestCorners}
    onDragStart={handleDragStart}
    onDragOver={handleDragOver}
    onDragEnd={handleDragEnd}
    >
    <div className="board">
        {COLUMNS.map(col => (
        <Column
            key={col.id}
            column={col}
            tasks={localTasks
            .filter(task => task.status === col.id)
            .sort((a, b) => a.position - b.position)}
            onEditTask={onEditTask}
        />
        ))}
    </div>

    {/* Ghost card that follows cursor */}
    <DragOverlay>
        {activeTask ? <TaskCard task={activeTask} /> : null}
    </DragOverlay>
    </DndContext>
);
}