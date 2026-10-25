import { Link, Outlet } from "react-router";

export function Layout() {
  return <main><header><Link to="/">HR Chan</Link><span>Hiring & onboarding</span></header><Outlet /></main>;
}
