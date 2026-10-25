import { createBrowserRouter } from "react-router";
import { homeRoutes } from "@/features/home/routes";
import { Layout } from "@/shared/layouts/Layout";

const browserRouter = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      ...homeRoutes,
      { path: "*", element: <p>Page not found.</p> },
    ],
  },
]);

export default browserRouter;
