const DESIGNER_TEMPLATE_KEY = "rfp_designer_last_template_id";
const MAP_STUDIO_KEY = "rfp_map_studio_last_map_id";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, id: string | null) {
  try {
    if (id) localStorage.setItem(key, id);
    else localStorage.removeItem(key);
  } catch {
    /* private mode / blocked storage */
  }
}

export function readLastDesignerTemplateId(): string | null {
  return read(DESIGNER_TEMPLATE_KEY);
}

export function writeLastDesignerTemplateId(id: string | null) {
  write(DESIGNER_TEMPLATE_KEY, id);
}

export function readLastMapStudioId(): string | null {
  return read(MAP_STUDIO_KEY);
}

export function writeLastMapStudioId(id: string | null) {
  write(MAP_STUDIO_KEY, id);
}
