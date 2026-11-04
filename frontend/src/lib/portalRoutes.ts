/** Default app route after sign-in, based on account role from /api/auth/login/. */
export function homePathForRole(role: string | undefined | null): string {
  switch (role) {
    case "CLIENT":
      return "/client";
    case "DESIGNER":
      return "/designer";
    case "ADMIN":
      return "/admin";
    default:
      return "/login";
  }
}

export function isLoginPath(pathname: string): boolean {
  return pathname === "/" || pathname === "/login";
}
