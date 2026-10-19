export class ApiError extends Error {
  readonly status: number;
  readonly path: string;

  constructor(status: number, path: string, message?: string) {
    super(message ?? `API ${status}: ${path}`);
    this.name = 'ApiError';
    this.status = status;
    this.path = path;
  }
}
