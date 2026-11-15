import { RouterProvider } from "react-router";
import browserRouter from "@/routes/routes";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { QueryProvider } from "@/shared/providers/QueryProvider";
import { ToastContainer } from "@/shared/components/ui/Toast";

export default function App() {
  return (
    <QueryProvider>
      <AuthProvider>
        <RouterProvider router={browserRouter} />
      </AuthProvider>
      <ToastContainer />
    </QueryProvider>
  );
}
