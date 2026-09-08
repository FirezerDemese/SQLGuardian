import {
  createBrowserRouter,
  createHashRouter,
  RouterProvider,
} from "react-router-dom";
import { IS_DEMO } from "./api/endpoints";
import { AppShell } from "./components/layout/AppShell";
import { FleetOverviewPage } from "./pages/FleetOverviewPage";
import { InstanceLayout } from "./pages/InstanceLayout";
import { InstanceOverviewPage } from "./pages/InstanceOverviewPage";
import { InstanceAiPage } from "./pages/InstanceAiPage";
import { InstanceJobsPage } from "./pages/InstanceJobsPage";
import { InstanceDatabasesPage } from "./pages/InstanceDatabasesPage";
import { InstanceBlockingPage } from "./pages/InstanceBlockingPage";
import { InstanceWaitsPage } from "./pages/InstanceWaitsPage";
import { InstanceResponsePage } from "./pages/InstanceResponsePage";
import { InstanceReportPage } from "./pages/InstanceReportPage";
import { RunbooksPage } from "./pages/RunbooksPage";
import { NotFoundPage } from "./pages/NotFoundPage";

// Demo builds use hash routing so the static GitHub Pages deploy never 404s
// on refresh/deep links; live builds keep clean URLs under /dashboard.
const createRouter = IS_DEMO ? createHashRouter : createBrowserRouter;

const router = createRouter(
  [
    {
      path: "/",
      element: <AppShell />,
      children: [
        { index: true, element: <FleetOverviewPage /> },
        { path: "runbooks", element: <RunbooksPage /> },
        {
          path: "instance/:name",
          element: <InstanceLayout />,
          children: [
            { index: true, element: <InstanceOverviewPage /> },
            { path: "response", element: <InstanceResponsePage /> },
            { path: "report", element: <InstanceReportPage /> },
            { path: "ai", element: <InstanceAiPage /> },
            { path: "jobs", element: <InstanceJobsPage /> },
            { path: "databases", element: <InstanceDatabasesPage /> },
            { path: "blocking", element: <InstanceBlockingPage /> },
            { path: "waits", element: <InstanceWaitsPage /> },
          ],
        },
        { path: "*", element: <NotFoundPage /> },
      ],
    },
  ],
  // Hash router paths live inside the hash, so no basename in demo builds;
  // live builds follow the Vite base ("/dashboard").
  IS_DEMO
    ? undefined
    : { basename: import.meta.env.BASE_URL.replace(/\/$/, "") }
);

export default function App() {
  return <RouterProvider router={router} />;
}
