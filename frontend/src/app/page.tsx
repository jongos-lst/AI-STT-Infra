import { UploadCard } from "@/components/UploadCard";

export default function Home() {
  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Transcribe & summarize audio
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Drop an audio file. We&apos;ll transcribe it and summarize the result.
        </p>
      </section>
      <UploadCard />
    </div>
  );
}
