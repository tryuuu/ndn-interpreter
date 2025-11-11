from __future__ import annotations
from typing import Any
from ..parser.ast import Program, PrintStatement, ExprStatement, NumberLiteral, Multiply, Expr

class Interpreter:
    def __init__(self):
        self._env: dict[str, Any] = {}

    def run(self, program: Program):
        # printのみで非同期不要。直接ブロック実行
        import asyncio
        asyncio.run(self._exec_block(program))

    async def _exec_block(self, node: Program):
        # Program is a list of statements
        for st in node:
            if isinstance(st, PrintStatement):
                await self._exec_print(st)
            elif isinstance(st, ExprStatement):
                await self._exec_expr_stmt(st)
            else:
                raise RuntimeError(f"Unsupported node: {st}")

    async def _exec_print(self, node: PrintStatement):
        # PrintStatement.value is already a string
        print(node.value)

    async def _exec_expr_stmt(self, node: ExprStatement):
        value = self._eval_expr(node.expr)
        print(value)

    def _eval_expr(self, expr: Expr) -> int:
        if isinstance(expr, NumberLiteral):
            return expr.value
        if isinstance(expr, Multiply):
            return self._eval_expr(expr.left) * self._eval_expr(expr.right)
        raise RuntimeError(f"Unsupported expr: {expr}")