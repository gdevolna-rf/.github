"use client";
import type { ReactNode } from "react";
import { InstructorWorkspace } from "@/components/instructor-cabinet/InstructorWorkspace";

export default function InstructorLayout({ children }: { children: ReactNode }) {
  return <InstructorWorkspace>{children}</InstructorWorkspace>;
}
