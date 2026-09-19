import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import TaskCard from './TaskCard';

export default function Column({ column, tasks, onEditTask }) {
    const { setNodeRef } = useDroppable({ id: column.id });

    return (
        <div ref={setNodeRef} className="column">
            <h3>{column.label} ({tasks.length})</h3>
            
            {/* The item IDs MUST match the task IDs */}
            <SortableContext 
                items={tasks.map(task => task.id)} 
                strategy={verticalListSortingStrategy}
            >
                {tasks.map(task => (
                    <TaskCard 
                        key={task.id} 
                        task={task} 
                        onEdit={() => onEditTask(task)}
                    />
                ))}
            </SortableContext>
        </div>
    );
}