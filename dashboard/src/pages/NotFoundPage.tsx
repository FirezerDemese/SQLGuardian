import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-text-secondary">
      <p className="text-lg font-medium text-text-primary">Page not found</p>
      <Link to="/" className="text-accent hover:underline">
        Back to Fleet Overview
      </Link>
    </div>
  );
}
