import { useRef, useState } from 'react';
import {
  closestCorners,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import Column from './Column';
import TaskCard from './TaskCard';

const COLUMNS = [
  { id: 'todo', label: 'To Do' },
  { id: 'in_progress', label: 'In Progress' },
  { id: 'done', label: 'Completed' },
];

function findTask(tasks, id) {
  return tasks.find(task => String(task.id) === String(id));
}

export default function Board({ tasks, onEditTask, onMoveTask, onAddTask }) {
  const [activeTask, setActiveTask] = useState(null);
  const [preview, setPreview] = useState(null);
  const previewRef = useRef(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  function updatePreview(nextPreview) {
    previewRef.current = nextPreview;
    setPreview(nextPreview);
  }

  function handleDragStart({ active }) {
    const task = findTask(tasks, active.id);
    if (!task) return;
    setActiveTask(task);

    const columnTasks = tasks
      .filter(item => item.status === task.status)
      .sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
    const index = columnTasks.findIndex(item => String(item.id) === String(task.id));
    updatePreview({
      activeId: String(task.id),
      startStatus: task.status,
      startIndex: index,
      status: task.status,
      index,
    });
  }

  function updateDragPreview({ active, over }) {
    if (!over) return;

    const activeId = String(active.id);
    const overId = String(over.id);
    const movingTask = findTask(tasks, activeId);
    if (!movingTask) return;

    const overTask = findTask(tasks, overId);
    const targetStatus = overTask ? overTask.status : overId;
    if (!COLUMNS.some(column => column.id === targetStatus)) return;

    const targetTasks = tasks
      .filter(task => task.status === targetStatus && String(task.id) !== activeId)
      .sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

    const activeRect = active.rect.current.translated ?? active.rect.current.initial;
    if (!activeRect) return;
    const activeCenter = activeRect.top + activeRect.height / 2;

    // Work out the slot from the card edges, not the column's center. This
    // lets the top and gaps in a column represent useful insertion positions.
    const taskElements = [...document.querySelectorAll(`[data-task-status="${targetStatus}"]`)]
      .filter(element => element.dataset.taskId !== activeId)
      .sort((first, second) =>
        Number(first.dataset.taskPosition) - Number(second.dataset.taskPosition));
    const index = taskElements.findIndex(element => {
      const rect = element.getBoundingClientRect();
      return activeCenter < rect.top + rect.height / 2;
    });
    const insertionIndex = index < 0 ? targetTasks.length : index;

    updatePreview({
      activeId,
      startStatus: previewRef.current?.startStatus ?? movingTask.status,
      startIndex: previewRef.current?.startIndex ?? movingTask.position,
      status: targetStatus,
      index: insertionIndex,
    });
  }

  function finishDrag() {
    setActiveTask(null);
    updatePreview(null);
  }

  function handleDragEnd({ active, over }) {
    const currentPreview = previewRef.current;
    const movingTask = findTask(tasks, active.id);
    finishDrag();

    if (!over || !currentPreview || !movingTask) return;
    if (currentPreview.status === movingTask.status &&
        currentPreview.index === currentPreview.startIndex) return;

    onMoveTask?.(movingTask.id, currentPreview.status, currentPreview.index);
  }

  function collisionDetection(args) {
    const pointerCollisions = pointerWithin(args);
    return pointerCollisions.length ? pointerCollisions : closestCorners(args);
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={collisionDetection}
      onDragStart={handleDragStart}
      onDragOver={updateDragPreview}
      onDragMove={updateDragPreview}
      onDragEnd={handleDragEnd}
      onDragCancel={finishDrag}
    >
      <div className="board">
        {COLUMNS.map(column => {
          const columnTasks = tasks
            .filter(task => task.status === column.id)
            .sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
          const isSourceColumn = preview?.startStatus === column.id;
          const visibleTasks = preview && !isSourceColumn
            ? columnTasks.filter(task => String(task.id) !== preview.activeId)
            : columnTasks;
          let taskCount = columnTasks.length;
          if (preview && preview.startStatus !== preview.status) {
            if (column.id === preview.startStatus) taskCount -= 1;
            if (column.id === preview.status) taskCount += 1;
          }

          return (
            <Column
              key={column.id}
              column={column}
              tasks={visibleTasks}
              taskCount={taskCount}
              onEditTask={onEditTask}
              onAddTask={onAddTask}
              isDropTarget={preview?.status === column.id}
              insertionIndex={preview?.status === column.id ? preview.index : null}
              draggedTaskId={isSourceColumn ? preview.activeId : null}
            />
          );
        })}
      </div>
      <DragOverlay dropAnimation={null}>
        {activeTask ? <TaskCard task={activeTask} isOverlay /> : null}
      </DragOverlay>
    </DndContext>
  );
}
