/**
 * `form_update`의 `path`(점 구분, 2-0.7)로 중첩 값을 읽고 씁니다.
 * 배열 안의 항목은 `item_id`로 가리킵니다 (예: `competencies.careers.career_001.main_duties`).
 * 원본은 바꾸지 않고 바뀐 경로만 새 객체로 복사합니다.
 */
type Node = Record<string, unknown> | unknown[];

const ITEM_ID = 'item_id';

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const findIndex = (list: unknown[], segment: string) => {
  const byId = list.findIndex((item) => isObject(item) && item[ITEM_ID] === segment);
  if (byId !== -1) return byId;
  const index = Number(segment);
  return Number.isInteger(index) && index >= 0 && index < list.length ? index : -1;
};

const childOf = (node: unknown, segment: string): unknown => {
  if (Array.isArray(node)) {
    const index = findIndex(node, segment);
    return index === -1 ? undefined : node[index];
  }
  return isObject(node) ? node[segment] : undefined;
};

export const getPath = (root: unknown, path: string): unknown =>
  path.split('.').reduce<unknown>((node, segment) => childOf(node, segment), root);

const cloneWithChild = (node: unknown, segment: string, child: unknown): Node => {
  if (Array.isArray(node)) {
    const index = findIndex(node, segment);
    const next = [...node];
    if (index === -1) next.push(isObject(child) ? { [ITEM_ID]: segment, ...child } : child);
    else next[index] = child;
    return next;
  }
  return { ...(isObject(node) ? node : {}), [segment]: child };
};

const update = (node: unknown, segments: string[], fn: (current: unknown) => unknown): unknown => {
  if (segments.length === 0) return fn(node);
  const [head, ...rest] = segments;
  return cloneWithChild(node, head, update(childOf(node, head), rest, fn));
};

export const setPath = <T>(root: T, path: string, value: unknown): T =>
  update(root, path.split('.'), () => value) as T;

/**
 * 경로의 배열 끝에 항목을 더합니다. 배열이 없으면 새로 만듭니다.
 * 같은 `item_id`가 이미 있으면 새로 더하지 않고 그 항목에 합칩니다 (같은 경력이 두 번 들어가지 않게).
 */
export const appendPath = <T>(root: T, path: string, value: unknown): T =>
  update(root, path.split('.'), (current) => {
    const list = Array.isArray(current) ? current : [];
    const itemId = isObject(value) ? value[ITEM_ID] : undefined;
    const index = typeof itemId === 'string' ? findIndex(list, itemId) : -1;
    if (index === -1) return [...list, value];
    const next = [...list];
    next[index] = { ...(next[index] as Record<string, unknown>), ...(value as object) };
    return next;
  }) as T;

/** 경로의 값을 지웁니다. 부모가 배열이면 그 항목을 빼고, 객체면 키를 없앱니다. */
export const removePath = <T>(root: T, path: string): T => {
  const segments = path.split('.');
  const last = segments.pop();
  if (last === undefined) return root;
  return update(root, segments, (parent) => {
    if (Array.isArray(parent)) {
      const index = findIndex(parent, last);
      return index === -1 ? parent : parent.filter((_, i) => i !== index);
    }
    if (!isObject(parent)) return parent;
    return Object.fromEntries(Object.entries(parent).filter(([key]) => key !== last));
  }) as T;
};
