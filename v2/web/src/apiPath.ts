export function apiPath(path: string): string {
 return new URL(path.replace(/^\//, ''), window.location.href).pathname;
}
