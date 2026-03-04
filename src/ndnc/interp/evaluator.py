from __future__ import annotations
from typing import Any, Union, Optional
import asyncio
import traceback
import sys
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ..parser.ast import (
	Program, PrintStatement, Assignment, ExprStatement,
	StringLiteral, NumberLiteral, Variable,
	ExpressInterest, FunctionCall, Expr
)

# ローカルで処理できる関数名のセット
_LOCAL_FUNCTIONS = {"modify"}

class Interpreter:
    def __init__(self):
        self._env: dict[str, Any] = {}
        self._env_origin: dict[str, str] = {}  # interest で取得した変数の NDN 名を追跡
        self.app: Optional[NDNApp] = None
        # HashMap for local data
        self._local_data: dict[str, str] = {
            '/data/ryu-local/': 'local data'
        }

    def run(self, program: Program):
        # Check if program uses interest expressions
        has_interest = any(
            (isinstance(st, ExprStatement) and self._has_interest(st.expr)) or
            (isinstance(st, PrintStatement) and self._has_interest(st.expr)) or
            (isinstance(st, Assignment) and self._has_interest(st.expr))
            for st in program
        )
        
        if has_interest:
            try:
                # Use KeychainDigest for simple no-auth communication
                self.app = NDNApp(keychain=KeychainDigest())
                # ローカルデータを NDN プロデューサーとして登録する
                # （リモート関数がこれらをフェッチできるようにするため）
                self._register_local_data_routes()

                async def after_start():
                    try:
                        await self._exec_block(program)
                    except Exception:
                        traceback.print_exc()
                        raise
                    finally:
                        self.app.shutdown()
            
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
        if isinstance(expr, Variable):
            # We can't statically determine if a variable contains an interest result
            # So we conservatively assume it might
            return True
        if isinstance(expr, FunctionCall):
            # ローカルにない関数はリモート呼び出しになるため NDNApp が必要
            return (expr.name not in _LOCAL_FUNCTIONS) or any(self._has_interest(a) for a in expr.args)
        return False

    async def _exec_block(self, node: Program):
        # Program is a list of statements
        for st in node:
            if isinstance(st, PrintStatement):
                await self._exec_print(st)
            elif isinstance(st, Assignment):
                await self._exec_assignment(st)
            elif isinstance(st, ExprStatement):
                await self._exec_expr_stmt(st)
            else:
                raise RuntimeError(f"Unsupported node: {st}")

    async def _exec_print(self, node: PrintStatement):
        # PrintStatement.expr is an expression that needs to be evaluated
        value = await self._eval_expr(node.expr)
        print(value)

    async def _exec_assignment(self, node: Assignment):
        # Evaluate the expression and store it in the environment
        value = await self._eval_expr(node.expr)
        self._env[node.name] = value
        # interest で取得した変数は NDN 名を記録しておく
        if isinstance(node.expr, ExpressInterest):
            self._env_origin[node.name] = node.expr.name

    async def _exec_expr_stmt(self, node: ExprStatement):
        value = await self._eval_expr(node.expr)
        print(value)

    async def _eval_expr(self, expr: Expr) -> Union[int, str]:
        if isinstance(expr, StringLiteral):
            return expr.value
            
        if isinstance(expr, NumberLiteral):
            return expr.value
            
        if isinstance(expr, Variable):
            if expr.name not in self._env:
                raise RuntimeError(f"Variable '{expr.name}' is not defined")
            return self._env[expr.name]
            
        if isinstance(expr, ExpressInterest):
            # Validate that interest name ends with trailing slash
            if not expr.name.endswith('/'):
                print(f"Error: Interest name must end with a trailing slash. Got: {expr.name}", file=sys.stderr)
                print(f"Expected: {expr.name}/", file=sys.stderr)
                sys.exit(1)
            
            # Checking local HashMap
            if expr.name in self._local_data:
                local_value = self._local_data[expr.name]
                try:
                    return int(local_value)
                except ValueError:
                    return local_value
            
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

        if isinstance(expr, FunctionCall):
            arg_values = [await self._eval_expr(a) for a in expr.args]

            if expr.name in _LOCAL_FUNCTIONS:
                return str(arg_values[0]) + " from function"
            elif self.app is not None:
                # Sidecar に倣い、引数は NDN 名として渡す
                ndn_names = [self._to_ndn_name(a) for a in expr.args]
                return await self._call_remote_function(expr.name, ndn_names)
            else:
                raise RuntimeError(f"Unknown function: {expr.name}")

        raise RuntimeError(f"Unsupported expr: {expr}")

    def _register_local_data_routes(self):
        """ローカルデータを NDN プロデューサーとして登録する。
        リモート関数がフェッチできるよう、Interest に応答できるようにする。"""
        for ndn_name, value in self._local_data.items():
            prefix = ndn_name.rstrip('/')
            val_bytes = str(value).encode()

            def make_handler(content):
                def handler(name, param, app_param):
                    self.app.put_data(name, content=content, freshness_period=10000)
                return handler

            self.app.route(prefix)(make_handler(val_bytes))

    def _to_ndn_name(self, expr: Expr) -> str:
        """リモート関数の引数として使う NDN 名を決定する。
        - ExpressInterest → そのまま NDN 名を返す
        - Variable → interest 由来なら記録済みの NDN 名、そうでなければ値を NDN 名として扱う
        - StringLiteral → 先頭 '/' を補完して NDN 名とする"""
        if isinstance(expr, ExpressInterest):
            return expr.name
        if isinstance(expr, Variable):
            if expr.name in self._env_origin:
                return self._env_origin[expr.name]
            val = self._env.get(expr.name, "")
            if isinstance(val, str):
                return val if val.startswith('/') else '/' + val
            return str(val)
        if isinstance(expr, StringLiteral):
            val = expr.value
            return val if val.startswith('/') else '/' + val
        return str(expr)

    async def _call_remote_function(self, func_name: str, ndn_names: list[str]) -> str:
        # Sidecar に倣い、括弧記法で Interest 名を構築する
        # 例: /temperature_average/(/data/tokyo, /data/paris)
        args_str = ", ".join(ndn_names)
        interest_name = "/" + func_name + "/(" + args_str + ")"
        try:
            _data_name, _meta_info, content = await self.app.express_interest(
                interest_name,
                must_be_fresh=True,
                can_be_prefix=False,
                lifetime=20000  # リモート関数が引数をフェッチする時間を考慮して長めに設定
            )
            if content is None:
                return ""
            return bytes(content).decode('utf-8').strip()
        except Exception as e:
            print(f"Error calling remote function '{func_name}': {e}")
            raise