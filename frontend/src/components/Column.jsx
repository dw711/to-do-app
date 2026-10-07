import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import TaskCard from './TaskCard';

export default function Column({
  column,
  tasks,
  taskCount,
  onEditTask,
  onAddTask,
  isDropTarget,
  insertionIndex,
  draggedTaskId,
}) {
  const { setNodeRef } = useDroppable({ id: column.id });
  const showInsertionPreview = Number.isInteger(insertionIndex);
  const taskItems = [];
  let visibleIndex = 0;
  let previewRendered = false;

  for (const task of tasks) {
    if (showInsertionPreview && !previewRendered && insertionIndex === visibleIndex) {
      taskItems.push(<DropPreview key="drop-preview" />);
      previewRendered = true;
    }
    taskItems.push(
      <TaskCard
        key={task.id}
        task={task}
        onEdit={() => onEditTask(task)}
        isDraggingSource={String(task.id) === draggedTaskId}
      />,
    );
    if (String(task.id) !== draggedTaskId) visibleIndex += 1;
  }
  if (showInsertionPreview && !previewRendered) {
    taskItems.push(<DropPreview key="drop-preview" />);
  }

  return (
    <section
      ref={setNodeRef}
      className={`column ${column.id === 'done' ? 'completed' : ''} ${isDropTarget ? 'drop-target' : ''}`}
      aria-label={`${column.label} column`}
    >
      <div className="column-header">
        <h3 className="column-title">{column.label}</h3>
        <span className="column-badge">{taskCount}</span>
      </div>

      <SortableContext items={tasks.map((task) => task.id)} strategy={verticalListSortingStrategy}>
        <ul className={`column-list ${isDropTarget ? 'is-drop-target' : ''}`}>
          {taskItems}
          {tasks.length === 0 && !showInsertionPreview && (
            <li className="column-empty">Drop a task here</li>
          )}
        </ul>
      </SortableContext>

      <button type="button" className="column-add-btn" onClick={() => onAddTask(column.id)}>+ Add task</button>
    </section>
  );
}

function DropPreview() {
  return (
    <li className="drop-preview" aria-label="Task will be placed here">
      <span />
      <span>Drop here</span>
      <span />
    </li>
  );
}