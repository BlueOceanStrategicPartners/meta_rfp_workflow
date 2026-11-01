import type { DesignerMediaAsset } from "./designerApi";
import { getAuthorizationHeader } from "./authTokens";

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
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
