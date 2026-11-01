import type { DesignerMediaAsset } from "./designerApi";
import { getAuthorizationHeader } from "./authTokens";

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export async function uploadMapAssetWithProgress(
  file: File,
  venueMapId: string | null,
  onProgress: (pct: number) => void
): Promise<DesignerMediaAsset> {
  await fetch("/api/auth/csrf/", { credentials: "include" });
  const token = getCookie("csrftoken");
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    if (venueMapId) form.append("venue_map_id", venueMapId);
    xhr.open("POST", "/api/maps/assets/upload/");
    xhr.withCredentials = true;
    const bearer = getAuthorizationHeader();
    if (bearer) xhr.setRequestHeader("Authorization", bearer);
    if (token) xhr.setRequestHeader("X-CSRFToken", token);
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) onProgress(Math.round((ev.loaded / ev.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as DesignerMediaAsset);
      } else {
        reject(new Error("Upload failed"));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(form);
  });
}
