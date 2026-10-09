import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

export default function TaskCard({ task, onEdit, isOverlay = false, isDraggingSource = false }) {
  if (isOverlay) return <TaskCardContent task={task} isOverlay />;
  return <SortableTaskCard task={task} onEdit={onEdit} isDraggingSource={isDraggingSource} />;
}

function SortableTaskCard({ task, onEdit, isDraggingSource }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDraggingSource ? 0.12 : isDragging ? 0.48 : 1,
    cursor: 'grab',
    ...(isDraggingSource ? { pointerEvents: 'none' } : {}),
  };

  return (
    <TaskCardContent
      task={task}
      onEdit={onEdit}
      nodeRef={setNodeRef}
      dragProps={{ ...attributes, ...listeners }}
      style={style}
      isDraggingSource={isDraggingSource}
    />
  );
}

function TaskCardContent({ task, onEdit, nodeRef, dragProps, style, isOverlay = false, isDraggingSource = false }) {

  const description = task.description?.trim();
  const tags = Array.isArray(task.tags) ? task.tags : [];

  return (
    <li
      ref={nodeRef}
      style={style}
      {...dragProps}
      data-task-id={task.id}
      data-task-status={task.status}
      data-task-position={task.position ?? 0}
      className={`task-card ${isOverlay ? 'task-card-overlay' : ''} ${isDraggingSource ? 'task-card-source' : ''}`}
      onClick={onEdit}
      aria-label={`Edit task ${task.title}`}
    >
      <h4>{task.title}</h4>
      {description && <p>{description}</p>}
      {task.due_date && <DueDateChip dueDate={task.due_date} status={task.status} />}
      {task.priority && <span className={`badge priority-${task.priority}`}>{task.priority.toUpperCase()}</span>}
      {tags.length > 0 && (
        <div className="tag-pills">
          {tags.map((tag) => (
            <span
              key={tag.id ?? tag.name}
              className="tag-pill"
              style={{ background: tag.colour || '#e2e8f0', color: '#0f172a' }}
            >
              {tag.name}
            </span>
          ))}
        </div>
      )}
    </li>
  );
}

function DueDateChip({ dueDate, status }) {
  const due = new Date(dueDate + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const overdue = due < today && status !== "done";
  const label = due.toLocaleDateString("en-GB", { day: "numeric", month: "short" });

  return (
    <span className={`due-chip${overdue ? " overdue" : ""}`}>
      Due {label}
    </span>
  );
}