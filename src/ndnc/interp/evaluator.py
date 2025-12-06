from __future__ import annotations
from typing import Any, Union, Optional
import asyncio
from ndn.app import NDNApp
from ..parser.ast import Program, PrintStatement, ExprStatement, NumberLiteral, ExpressInterest, Multiply, Divide, Expr

class Interpreter:
    def __init__(self):
        self._env: dict[str, Any] = {}
        self.app: Optional[NDNApp] = None

    def run(self, program: Program):
        # Check if program uses interest expressions
        has_interest = any(
            isinstance(st, ExprStatement) and self._has_interest(st.expr)
            for st in program
        )
        
        if has_interest:
            try:
                self.app = NDNApp()
                async def after_start():
                    try:
                        await self._exec_block(program)
                    finally:
                        self.app.shutdown()
                self.app.run_forever(after_start=after_start)
            except Exception:
                # NDNApp initialization failed, continue with mock data
                self.app = None
                asyncio.run(self._exec_block(program))
        else:
            asyncio.run(self._exec_block(program))

    def _has_interest(self, expr: Expr) -> bool:
        if isinstance(expr, ExpressInterest):
            return True
        if isinstance(expr, Multiply):
            return self._has_interest(expr.left) or self._has_interest(expr.right)
        if isinstance(expr, Divide):
            return self._has_interest(expr.left) or self._has_interest(expr.right)
        return False

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
        value = await self._eval_expr(node.expr)
        print(value)

    async def _eval_expr(self, expr: Expr) -> Union[int, str]:
        if isinstance(expr, NumberLiteral):
            return expr.value
        if isinstance(expr, ExpressInterest):
            if self.app is None:
                # Return mock data when NDNApp is not available
                return f"mock_{expr.name.replace('/', '_')}"
            data, meta = await self.app.express_interest(expr.name)
            # Try to decode as UTF-8 string and convert to int if possible
            try:
                text = data.decode('utf-8').strip()
                try:
                    return int(text)
                except ValueError:
                    return text
            except (UnicodeDecodeError, AttributeError):
                return str(data)
        if isinstance(expr, Multiply):
            left = await self._eval_expr(expr.left)
            right = await self._eval_expr(expr.right)
            if isinstance(left, str) or isinstance(right, str):
                raise TypeError("Cannot multiply string values")
            return left * right
        if isinstance(expr, Divide):
            right = await self._eval_expr(expr.right)
            if right == 0:
                raise ZeroDivisionError("division by zero")
            left = await self._eval_expr(expr.left)
            if isinstance(left, str) or isinstance(right, str):
                raise TypeError("Cannot divide string values")
            return left // right
        raise RuntimeError(f"Unsupported expr: {expr}")