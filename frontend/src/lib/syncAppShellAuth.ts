import { isStudioRole } from "./authTokens";

export function syncAppShellFromRole(
  role: string | undefined | null,
  setClientAuthed: (value: boolean) => void,
  setDesignerAuthed: (value: boolean) => void,
) {
  if (role === "CLIENT") {
    setClientAuthed(true);
    setDesignerAuthed(false);
    return;
  }
  if (isStudioRole(role ?? undefined)) {
    setClientAuthed(false);
    setDesignerAuthed(true);
    return;
  }
  setClientAuthed(false);
  setDesignerAuthed(false);
}
