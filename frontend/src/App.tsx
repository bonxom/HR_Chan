import { RouterProvider } from "react-router";
import browserRouter from "@/routes/routes";
import { QueryProvider } from "@/shared/providers/QueryProvider";

export default function App() {
  return (
    <QueryProvider>
      <RouterProvider router={browserRouter} />
    </QueryProvider>
  );
}
