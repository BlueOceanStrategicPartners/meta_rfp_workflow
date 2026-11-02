import type { DesignerMediaAsset } from "./designerApi";
import { getAuthorizationHeader } from "./authTokens";

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/** Images from clipboard paste (Win+Shift+S, PrtScn, Copy image, etc.). */
export function imageFilesFromClipboardEvent(event: ClipboardEvent): File[] {
  const out: File[] = [];
  const items = event.clipboardData?.items;
  if (items) {
    for (const item of Array.from(items)) {
      if (item.kind !== "file") continue;
      const type = item.type || "";
      if (!type.startsWith("image/")) continue;
      const file = item.getAsFile();
      if (file) out.push(file);
    }
  }
  if (out.length === 0 && event.clipboardData?.files?.length) {
    for (const file of Array.from(event.clipboardData.files)) {
      if (file.type.startsWith("image/")) out.push(file);
    }
  }
  return out;
}

export function labelPastedScreenshotFile(file: File, index: number): File {
  const type = file.type || "image/png";
  const ext = type.includes("png") ? "png" : type.includes("jpeg") || type.includes("jpg") ? "jpg" : "png";
  const generic = !file.name || file.name === "image.png" || file.name === "blob";
  if (!generic) return file;
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const suffix = index > 0 ? `-${index + 1}` : "";
  return new File([file], `pasted-screenshot-${stamp}${suffix}.${ext}`, { type });
}

export async function uploadDesignerAssetWithProgress(
  file: File,
  templateId: string | null | undefined,
  onProgress: (pct: number) => void
): Promise<DesignerMediaAsset> {
  await fetch("/api/auth/csrf/", { credentials: "include" });
  const csrf = getCookie("csrftoken");

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    if (templateId) form.append("template_id", templateId);

    xhr.open("POST", "/api/designer/assets/upload/");
    xhr.withCredentials = true;
    const bearer = getAuthorizationHeader();
    if (bearer) xhr.setRequestHeader("Authorization", bearer);
    if (csrf) xhr.setRequestHeader("X-CSRFToken", csrf);

    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) {
        onProgress(Math.round((ev.loaded / ev.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as DesignerMediaAsset);
        } catch {
          reject(new Error("Invalid upload response"));
        }
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          reject(new Error(err.detail || "Upload failed"));
        } catch {
          reject(new Error("Upload failed"));
        }
      }
    };
    xhr.onerror = () => reject(new Error("Network error"));
    xhr.send(form);
  });
}
