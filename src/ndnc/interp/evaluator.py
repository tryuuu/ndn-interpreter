from __future__ import annotations
from typing import Any, Union, Optional
import asyncio
import traceback
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
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
                # Use KeychainDigest for simple no-auth communication
                self.app = NDNApp(keychain=KeychainDigest())
                
                async def after_start():
                    try:
                        await self._exec_block(program)
                    except Exception:
                        traceback.print_exc()
                        raise
                    finally:
                        self.app.shutdown()
                
                # 【修正】 after_start() と呼び出して、コルーチンとして渡す
                self.app.run_forever(after_start=after_start())
                
            except Exception as e:
                print(f"DEBUG: NDN Connection/Execution Failed: {e}")
                traceback.print_exc()
                
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
            
            try:
                # python-ndn returns (data_name, meta_info, content)
                # We need to await the function call
                data_name, meta_info, content = await self.app.express_interest(
                    expr.name,
                    must_be_fresh=True,
                    can_be_prefix=True,
                    lifetime=6000
                )
                
                if content is None:
                    return ""
                
                # Convert bytes to string/int
                text = bytes(content).decode('utf-8').strip()
                try:
                    return int(text)
                except ValueError:
                    return text
            except Exception as e:
                print(f"Error expressing interest for {expr.name}: {e}")
                raise e

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