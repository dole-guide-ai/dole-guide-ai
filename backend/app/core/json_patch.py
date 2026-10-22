"""서류(이력서·신청서·절차) jsonb에 JSON Patch를 적용하는 공용 함수입니다.

서류의 칸은 `{value, status, source, ...}`(FormField) 모양으로 값과 상태를 같이 둡니다.
경로는 JSON Pointer와 같지만, 반복 항목(경력·학력 등) 목록은 순번이 아니라 item_id로 가리킵니다.
예: `/careers/c1/company_name`은 careers 목록에서 item_id가 c1인 항목의 company_name 칸입니다.

- replace·add로 칸을 고치면 값이 바뀌고, 상태는 confirmed, 출처는 넘겨준 source가 됩니다.
- 목록 경로(`/careers` 또는 `/careers/-`)에 add하면 항목을 하나 붙입니다. item_id가 없으면 만듭니다.
- 항목 경로(`/careers/c1`)를 remove하면 항목을 지웁니다.
- 칸 경로를 remove하면 빈 칸(missing)으로 돌립니다.
- `/status`(저장·제출)는 칸이 아니므로 여기서 다루지 않습니다. `split_status`로 먼저 떼어 냅니다.

원본을 바꾸지 않고 새 dict를 돌려주며, 대화 턴의 form_update 이벤트와 REST 응답에 쓸
FormUpdate 목록도 같이 돌려줍니다. DB와 HTTP를 모르는 순수 함수라 서비스와 AI 도구가 같이 씁니다.
"""

import copy
import uuid
from typing import Any

from app.core.errors import UnprocessableError
from app.schemas.common import (
    ErrorCode,
    FieldSource,
    FieldStatus,
    FormField,
    FormName,
    FormUpdate,
    JsonPatchOp,
)

STATUS_PATH = "/status"
ITEM_ID = "item_id"


def split_status(patch: list[JsonPatchOp]) -> JsonPatchOp | None:
    """`/status` 바꾸기면 그 한 줄을, 칸 고치기면 None을 돌려줍니다. 둘을 섞으면 422."""
    status_ops = [op for op in patch if op.path == STATUS_PATH]
    if not status_ops:
        return None
    if len(patch) > 1:
        raise UnprocessableError(code=ErrorCode.STATUS_WITH_FIELDS)
    return status_ops[0]


def apply_patch(
    data: dict[str, Any],
    patch: list[JsonPatchOp],
    *,
    form: FormName,
    source: FieldSource,
) -> tuple[dict[str, Any], list[FormUpdate]]:
    """패치를 순서대로 적용합니다. 한 줄이라도 틀리면 아무것도 바꾸지 않고 422."""
    result = copy.deepcopy(data)
    updates: list[FormUpdate] = []
    for index, op in enumerate(patch):
        if op.path == STATUS_PATH:
            raise UnprocessableError(code=ErrorCode.STATUS_WITH_FIELDS)
        try:
            updates.append(_apply_one(result, op, form, source))
        except _BadPathError:
            # 경로 원문은 입력값이라 오류에 넣지 않고 몇 번째 연산인지만 알려 줍니다.
            raise UnprocessableError(
                "고칠 칸을 찾지 못했어요.",
                details=[{"field": f"patch[{index}]", "reason": "unknown_path"}],
            ) from None
    return result, updates


def _apply_one(root: dict[str, Any], op: JsonPatchOp, form: FormName, source: FieldSource):
    *parents, last = _segments(op.path)
    container = _resolve(root, parents)

    if isinstance(container, list):
        return _apply_to_list(container, last, op, form, source)
    # 칸 안쪽(`/title/value`)이나 항목 id(`/careers/c1/item_id`)는 직접 고칠 수 없습니다.
    if not isinstance(container, dict) or _is_field(container) or last == ITEM_ID:
        raise _BadPathError

    if op.op == "remove":
        if last not in container:
            raise _BadPathError
        target = container[last]
        if isinstance(target, list):
            container[last] = []
        else:
            container[last] = FormField().model_dump(mode="json")
        return FormUpdate(form=form, path=op.path, op="remove", status=FieldStatus.MISSING)

    if op.op == "add" and isinstance(container.get(last), list):
        return _apply_to_list(container[last], "-", op, form, source)
    if isinstance(container.get(last), list):
        # 목록 자체를 덮어쓰는 것은 막습니다. 항목은 하나씩 add·remove합니다.
        raise _BadPathError
    field = _confirmed(container.get(last), op.value, source)
    container[last] = field
    return FormUpdate(
        form=form,
        path=op.path,
        op=op.op,
        value=op.value,
        status=FieldStatus.CONFIRMED,
        source=source,
    )


def _apply_to_list(
    items: list[Any], last: str, op: JsonPatchOp, form: FormName, source: FieldSource
) -> FormUpdate:
    if op.op == "add" and last == "-":
        if not isinstance(op.value, dict):
            raise _BadPathError
        item = _new_item(op.value, source)
        if any(isinstance(i, dict) and i.get(ITEM_ID) == item[ITEM_ID] for i in items):
            raise _BadPathError
        items.append(item)
        return FormUpdate(
            form=form,
            path=f"{op.path.removesuffix('/-')}/{item['item_id']}",
            op="add",
            value=op.value,
            status=FieldStatus.CONFIRMED,
            source=source,
        )
    index = _item_index(items, last)
    if op.op == "remove":
        items.pop(index)
        return FormUpdate(form=form, path=op.path, op="remove")
    # 항목 통째로 바꾸기는 칸별 replace로 하도록 막습니다.
    raise _BadPathError


def _new_item(value: dict[str, Any], source: FieldSource) -> dict[str, Any]:
    item: dict[str, Any] = {ITEM_ID: str(value.get(ITEM_ID) or uuid.uuid4().hex[:8])}
    for key, raw in value.items():
        if key != ITEM_ID:
            item[key] = _confirmed(None, raw, source)
    return item


def _confirmed(existing: Any, value: Any, source: FieldSource) -> dict[str, Any]:
    base = FormField.model_validate(existing) if _is_field(existing) else FormField()
    return base.model_copy(
        update={
            "value": value,
            "status": FieldStatus.CONFIRMED,
            "source": source,
            "transformed": False,
        }
    ).model_dump(mode="json")


def _is_field(node: Any) -> bool:
    return isinstance(node, dict) and "status" in node and "value" in node


def _resolve(root: dict[str, Any], parents: list[str]) -> Any:
    node: Any = root
    for seg in parents:
        if isinstance(node, list):
            node = node[_item_index(node, seg)]
        elif isinstance(node, dict) and not _is_field(node) and seg in node:
            node = node[seg]
        else:
            raise _BadPathError
    return node


def _item_index(items: list[Any], item_id: str) -> int:
    for i, item in enumerate(items):
        if isinstance(item, dict) and item.get(ITEM_ID) == item_id:
            return i
    raise _BadPathError


def _segments(path: str) -> list[str]:
    segments = [s.replace("~1", "/").replace("~0", "~") for s in path.split("/")[1:]]
    if not segments or any(s == "" for s in segments):
        raise _BadPathError
    return segments


class _BadPathError(Exception):
    """없는 칸이나 고칠 수 없는 경로. apply_patch가 422로 바꿉니다."""
