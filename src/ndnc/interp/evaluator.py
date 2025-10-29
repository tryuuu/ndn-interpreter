from __future__ import annotations
from typing import Any
from ..parser.ast import Program, Print, Var

class Interpreter:
    def __init__(self):
        self._env: dict[str, Any] = {}

def run(self, program: Program):
# printのみで非同期不要。直接ブロック実行
    import asyncio
    asyncio.run(self._exec_block(program))

async def _exec_block(self, node: Program | list[Any]):
    stmts = node.stmts if isinstance(node, Program) else node
    for st in stmts:
        if isinstance(st, Print):
            await self._exec_print(st)
        else:
            raise RuntimeError(f"Unsupported node: {st}")

async def _exec_print(self, node: Print):
    val = node.value
    if isinstance(val, Var):
        v = self._env.get(val.name)
    else:
        v = val
    print(v)