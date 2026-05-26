import { useEffect, useState } from "react";

interface Props {
  createdAt: string;
  status: string;
}

export default function VirtualProgressBar({ createdAt, status }: Props) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (status === "ready") { setProgress(100); return; }
    if (status === "failed" || status !== "converting") { setProgress(0); return; }

    const update = () => {
      const elapsed = (Date.now() - new Date(createdAt).getTime()) / 1000;
      setProgress(Math.round((1 - Math.exp(-elapsed / 1800)) * 100));
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [createdAt, status]);

  if (status !== "converting") return null;

  return (
    <div className="h-1.5 w-full rounded-full bg-blue-100">
      <div
        className="h-full rounded-full bg-blue-500 transition-all duration-1000"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
