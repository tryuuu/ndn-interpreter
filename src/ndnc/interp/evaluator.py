from __future__ import annotations
from typing import Any
from ..parser.ast import Program, PrintStatement

class Interpreter:
    def __init__(self):
        self._env: dict[str, Any] = {}

    def run(self, program: Program):
        # printのみで非同期不要。直接ブロック実行
        import asyncio
        asyncio.run(self._exec_block(program))

    async def _exec_block(self, node: Program):
        # Program is List[PrintStatement], so node is already a list
        for st in node:
            if isinstance(st, PrintStatement):
                await self._exec_print(st)
            else:
                raise RuntimeError(f"Unsupported node: {st}")

    async def _exec_print(self, node: PrintStatement):
        # PrintStatement.value is already a string
        print(node.value)