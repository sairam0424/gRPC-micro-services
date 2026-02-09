"use client";

import { useAuth } from "@/context/auth-context";
import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !user && pathname !== "/login" && pathname !== "/signup") {
      router.push("/login");
    }
  }, [user, isLoading, router, pathname]);

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return <>{children}</>;
}
