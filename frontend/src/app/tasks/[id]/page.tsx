import { TaskView } from "@/components/TaskView";

export default async function TaskPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Task status</h1>
        <p className="mt-1 text-sm text-slate-500">
          Updates every 1.5 seconds until done.
        </p>
      </section>
      <TaskView taskId={id} />
    </div>
  );
}
