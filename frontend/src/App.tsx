import { RouterProvider } from "react-router";
import browserRouter from "@/routes/routes";
import { QueryProvider } from "@/shared/providers/QueryProvider";
import { ToastContainer } from "@/shared/components/ui/Toast";

export default function App() {
  return (
    <QueryProvider>
      <RouterProvider router={browserRouter} />
      <ToastContainer />
    </QueryProvider>
  );
}
