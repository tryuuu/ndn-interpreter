from __future__ import annotations
from typing import Any, Optional
import asyncio
import json
import hashlib
import os
import time
import sys
from uuid import uuid4
from pathlib import Path
from urllib.parse import urlparse
from ndn.app import NDNApp
from ndn.security import KeychainDigest
from ndn.transport.stream_face import TcpFace, UnixFace
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from segmented_node_wrapper import SegmentedNodeWrapper
from ..ndn_routing import RoutedNDNApp
from ..parser.ast import (
	Program, PrintStatement, ReturnStatement, Assignment, ExprStatement,
	StringLiteral, NumberLiteral, Variable,
	ExpressInterest, FunctionCall, BinOp, UnaryOp, Expr
)

# ローカルで処理できる関数名のセット
_LOCAL_FUNCTIONS = {"concat", "put_image"}
tracer = trace.get_tracer(__name__)


_CACHE_DIR = Path.home() / ".ndnc" / "cache"
_CACHE_TTL = 300  # seconds


class RemoteTcpFace(TcpFace):
    def isLocalFace(self):
        return False


def make_ndn_app():
    uri = urlparse(os.environ['NDN_CLIENT_TRANSPORT'])
    if uri.scheme == 'unix' and uri.path:
        face = UnixFace(uri.path)
    elif uri.scheme in ('tcp', 'tcp4', 'tcp6') and uri.hostname:
        face = RemoteTcpFace(uri.hostname, uri.port or 6363)
    else:
        raise ValueError('NDN_CLIENT_TRANSPORT must be unix:///path or tcp://host:port')
    return RoutedNDNApp(face=face, keychain=KeychainDigest())


def _cache_path(func_name: str) -> Path:
    safe = func_name.lstrip("/").replace("/", "_")
    return _CACHE_DIR / f"{safe}.json"


def _load_cache(func_name: str) -> Optional[str]:
    """キャッシュが有効なら .ndn ソースを返す。期限切れ・未存在なら None。"""
    path = _cache_path(func_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data["cached_at"] > _CACHE_TTL:
            return None
        return data["code"]
    except Exception:
        return None


def _save_cache(func_name: str, code: str) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(func_name)
    path.write_text(json.dumps({"code": code, "cached_at": time.time()}))


def _interest_cache_path(ndn_name: str) -> Path:
    safe = "interest_" + ndn_name.strip("/").replace("/", "_")
    return _CACHE_DIR / f"{safe}.json"


def _load_interest_cache(ndn_name: str) -> Optional[Any]:
    """interest キャッシュが有効なら値を返す。期限切れ・未存在なら None。"""
    path = _interest_cache_path(ndn_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data["cached_at"] > _CACHE_TTL:
            return None
        return data["value"]
    except Exception:
        return None


def _save_interest_cache(ndn_name: str, value: Any) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _interest_cache_path(ndn_name)
    path.write_text(json.dumps({"value": value, "cached_at": time.time()}))

class Interpreter:
    # プロセス内で共有するメモリキャッシュ（関数名 → .ndn コード）
    _code_cache: dict[str, str] = {}
    # プロセス内で共有するメモリキャッシュ（NDN 名 → 取得済みデータ）
    _interest_cache: dict[str, Any] = {}
    # Share completed remote function results across interpreters in this process.
    _function_result_cache: dict[str, Any] = {}

    def __init__(self, args: dict[str, Any] | None = None, base_dir: Path | None = None):
        self.base_dir = Path(base_dir).resolve() if base_dir is not None else Path.cwd()
        self._env: dict[str, Any] = {}
        if args:
            self._env.update(args)
        self.app: Optional[NDNApp] = None
        self._argument_publisher = None
        self._local_data: dict[str, str] = {
            '/data/local/': 'data from local',
        }

    def run(self, program: Program):
        has_interest = any(self._has_interest(st.expr) for st in program)
        if not has_interest:
            return asyncio.run(self._exec_block(program))

        self.app = make_ndn_app()
        self._register_local_data_routes()
        result = None
        failure = None

        async def after_start():
            nonlocal result, failure
            try:
                result = await self._exec_block(program)
            except Exception as exc:
                failure = exc
            finally:
                self.app.shutdown()

        self.app.run_forever(after_start=after_start())
        if failure is not None:
            raise failure
        return result

    def _has_interest(self, expr: Expr) -> bool:
        if isinstance(expr, ExpressInterest):
            if expr.name_is_var:
                # 変数の値は実行時まで不明なのでネットワーク必要とみなす
                return True
            # _local_data にあればネットワーク不要
            return expr.name not in self._local_data
        if isinstance(expr, BinOp):
            return self._has_interest(expr.left) or self._has_interest(expr.right)
        if isinstance(expr, UnaryOp):
            return self._has_interest(expr.operand)
        if isinstance(expr, Variable):
            return False
        if isinstance(expr, FunctionCall):
            # ローカルにない関数はリモート呼び出しになるため NDNApp が必要
            return (expr.name not in _LOCAL_FUNCTIONS) or any(self._has_interest(a) for a in expr.args)
        return False

    async def _exec_block(self, node: Program):
        for st in node:
            if isinstance(st, ReturnStatement):
                return await self._eval_expr(st.expr)
            elif isinstance(st, PrintStatement):
                await self._exec_print(st)
            elif isinstance(st, Assignment):
                await self._exec_assignment(st)
            elif isinstance(st, ExprStatement):
                if isinstance(st.expr, FunctionCall) and st.expr.name == "put_image":
                    return await self._eval_expr(st.expr)
                await self._exec_expr_stmt(st)
            else:
                raise RuntimeError(f"Unsupported node: {st}")

    async def _exec_print(self, node: PrintStatement):
        value = await self._eval_expr(node.expr)
        print(value)

    async def _exec_assignment(self, node: Assignment):
        value = await self._eval_expr(node.expr)
        self._env[node.name] = value

    async def _exec_expr_stmt(self, node: ExprStatement):
        value = await self._eval_expr(node.expr)
        print(value)

    async def _read_content(self, content: Any) -> str | bytes:
        # Function returns a reference; the wrapper fetches the complete result.
        try:
            response = json.loads(bytes(content))
        except ValueError:
            response = None
        if isinstance(response, dict):
            reference = response.get('image_ref') or response.get('result_ref')
            if reference:
                with tracer.start_as_current_span('ndnc.fetch.result', attributes={'ndn.name': reference}):
                    content = await SegmentedNodeWrapper(self.app).fetch(reference, must_be_fresh=True)
                if response.get('image_ref'):
                    return bytes(content)
        raw = bytes(content)
        try:
            return raw.decode('utf-8').strip()
        except UnicodeDecodeError:
            return raw

    async def _eval_expr(self, expr: Expr) -> Any:
        if isinstance(expr, StringLiteral):
            return expr.value

        if isinstance(expr, NumberLiteral):
            return expr.value

        if isinstance(expr, Variable):
            if expr.name not in self._env:
                raise RuntimeError(f"Variable '{expr.name}' is not defined")
            return self._env[expr.name]

        if isinstance(expr, ExpressInterest):
            # name_is_var のとき、変数から実際の NDN 名を解決する
            if expr.name_is_var:
                if expr.name not in self._env:
                    raise RuntimeError(f"Variable '{expr.name}' is not defined (used in interest)")
                ndn_name = str(self._env[expr.name])
            else:
                ndn_name = expr.name

            if not ndn_name.startswith('/'):
                ndn_name = '/' + ndn_name
            if not ndn_name.endswith('/'):
                ndn_name = ndn_name + '/'

            if ndn_name in self._local_data:
                local_value = self._local_data[ndn_name]
                try:
                    return int(local_value)
                except ValueError:
                    return local_value

            if self.app is None:
                return f"mock_{ndn_name.replace('/', '_')}"

            # 1. メモリキャッシュ確認
            if ndn_name in Interpreter._interest_cache:
                trace.get_current_span().add_event('ndnc.cache.hit', {'ndn.name': ndn_name, 'cache.type': 'memory'})
                return Interpreter._interest_cache[ndn_name]

            # 2. ファイルキャッシュ確認
            file_cached = _load_interest_cache(ndn_name)
            if file_cached is not None:
                trace.get_current_span().add_event('ndnc.cache.hit', {'ndn.name': ndn_name, 'cache.type': 'file'})
                Interpreter._interest_cache[ndn_name] = file_cached
                return file_cached

            # 3. ネットワーク取得
            try:
                with tracer.start_as_current_span('ndnc.interest', kind=trace.SpanKind.CLIENT,
                                                 attributes={'ndn.name': ndn_name}):
                    parameters = {}
                    # Inject the current span's traceparent and optional tracestate into ApplicationParameters
                    # so the Sidecar in the Function Pod can continue the same trace.
                    TraceContextTextMapPropagator().inject(parameters)
                    _, _, content = await self.app.express_interest(
                        ndn_name,
                        app_param=json.dumps(parameters).encode('utf-8') if parameters else None,
                        must_be_fresh=True,
                        can_be_prefix=True,
                        lifetime=6000
                    )
                if content is None:
                    return ""
                text = await self._read_content(content)
                try:
                    value = int(text) if isinstance(text, str) else text
                except ValueError:
                    value = text
                Interpreter._interest_cache[ndn_name] = value
                if not isinstance(value, bytes):
                    _save_interest_cache(ndn_name, value)
                    print(f"[ndnc] cached interest '{ndn_name}' (~/.ndnc/cache/)", file=sys.stderr)
                return value
            except Exception as e:
                print(f"Error expressing interest for {expr.name}: {e}")
                raise e

        if isinstance(expr, FunctionCall):
            if expr.name in _LOCAL_FUNCTIONS:
                arg_values = [await self._eval_expr(a) for a in expr.args]
                if expr.name == "concat":
                    return "".join(str(v) for v in arg_values)
                if expr.name == "put_image":
                    if len(arg_values) != 1 or not isinstance(arg_values[0], str):
                        raise RuntimeError("put_image expects exactly one string path")
                    path = self.base_dir / arg_values[0]
                    try:
                        return path.read_bytes()
                    except OSError as exc:
                        raise RuntimeError(f"put_image could not read '{path}': {exc}") from exc
            elif self.app is not None:
                arg_values = []
                for argument in expr.args:
                    if isinstance(argument, ExpressInterest):
                        # Add the Interest name to arg_values as an ExpressInterest without executing it first.
                        name = (str(await self._eval_expr(Variable(argument.name)))
                                if argument.name_is_var else argument.name)
                        arg_values.append(ExpressInterest('/' + name.lstrip('/')))
                    else:
                        arg_values.append(await self._eval_expr(argument))
                return await self._call_remote_function(expr.name, arg_values)
            else:
                raise RuntimeError(f"Unknown function: {expr.name}")

        if isinstance(expr, BinOp):
            left = await self._eval_expr(expr.left)
            right = await self._eval_expr(expr.right)
            left_n = float(left)
            right_n = float(right)
            if expr.op == "+":
                result = left_n + right_n
            elif expr.op == "-":
                result = left_n - right_n
            elif expr.op == "*":
                result = left_n * right_n
            elif expr.op == "/":
                if right_n == 0:
                    raise RuntimeError("Division by zero")
                result = left_n / right_n
            else:
                raise RuntimeError(f"Unknown operator: {expr.op}")
            # 整数に落とせるなら int で返す
            return int(result) if result == int(result) else result

        if isinstance(expr, UnaryOp):
            val = await self._eval_expr(expr.operand)
            if expr.op == "-":
                n = float(val)
                result = -n
                return int(result) if result == int(result) else result
            raise RuntimeError(f"Unknown unary operator: {expr.op}")

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

    @tracer.start_as_current_span('ndnc.function.call')
    async def _call_remote_function(self, func_name: str, arg_values: list[Any]) -> Any:
        trace.get_current_span().set_attribute('ndn.function.name', func_name)
        cache_key = self._function_result_cache_key(func_name, arg_values)
        if cache_key in Interpreter._function_result_cache:
            trace.get_current_span().add_event('ndnc.cache.hit', {
                'ndn.function.name': func_name, 'cache.type': 'memory', 'cache.target': 'function_result'})
            return Interpreter._function_result_cache[cache_key]
        result = await self._execute_remote_function(func_name, arg_values)
        Interpreter._function_result_cache[cache_key] = result
        return result

    @staticmethod
    def _function_result_cache_key(func_name: str, arg_values: list[Any]) -> str:
        arguments = []
        for value in arg_values:
            if isinstance(value, bytes):
                arguments.append(['bytes', hashlib.sha256(value).hexdigest()])
            elif isinstance(value, ExpressInterest):
                arguments.append(['interest', value.name])
            else:
                arguments.append(['value', value])
        # For compress_image(image): ["compress_image", [["bytes", "<image SHA-256>"]]].
        encoded = json.dumps([func_name, arguments], ensure_ascii=False).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    async def _execute_remote_function(self, func_name: str, arg_values: list[Any]) -> Any:
        # 1. リモート側で実行する。空の応答も有効な実行結果なので、
        #    例外時だけローカル実行へフォールバックする。
        wire_args = []
        parameters = {}
        for value in arg_values:
            if isinstance(value, bytes):
                if 'image_ref' in parameters:
                    raise ValueError('Only one image argument can be passed through stdin')
                # Reuse the pre-advertised router prefix instead of waiting for a new route.
                prefix = os.environ['NDN_ROUTER_PREFIX'].rstrip('/') + '/image/arg/' + uuid4().hex
                if self._argument_publisher is None:
                    self._argument_publisher = SegmentedNodeWrapper(self.app, serve=True)
                with tracer.start_as_current_span('ndnc.publish.argument', attributes={
                        'ndn.name': prefix, 'ndn.content.bytes': len(value)}):
                    reference = await self._argument_publisher.publish(prefix, value)
                parameters['image_ref'] = reference
                wire_args.append(reference)
            else:
                wire_args.append(value)
        # ExpressInterest("/print_image") -> /compress_image/(/print_image)
        # json.dumps() wraps string arguments in double quotes.
        args_str = ", ".join(value.name if isinstance(value, ExpressInterest)
                             else json.dumps(value, ensure_ascii=False) for value in wire_args)
        interest_name = "/" + func_name + "/(" + args_str + ")"
        remote_error: Exception
        try:
            with tracer.start_as_current_span('ndnc.function.request', kind=trace.SpanKind.CLIENT,
                                             attributes={'ndn.function.name': func_name, 'ndn.name': interest_name}):
                # Carry this request span to the Sidecar through ApplicationParameters.
                TraceContextTextMapPropagator().inject(parameters)
                _, _, content = await self.app.express_interest(
                    interest_name,
                    app_param=json.dumps(parameters).encode('utf-8') if parameters else None,
                    must_be_fresh=True,
                    can_be_prefix=True,
                    lifetime=20000,
                )
        except Exception as error:
            remote_error = error
            print(
                f"[ndnc] remote execution of '{func_name}' failed; "
                "trying local source fallback",
                file=sys.stderr,
            )
        else:
            if content is None:
                return ""
            return await self._read_content(content)

        # 2. リモート実行失敗時だけ、既存のソースキャッシュをローカル実行する。
        if func_name in Interpreter._code_cache:
            return await self._run_cached(func_name, Interpreter._code_cache[func_name], arg_values)

        # 3. ファイルキャッシュ確認（TTL チェックあり）
        cached_code = _load_cache(func_name)
        if cached_code is not None:
            Interpreter._code_cache[func_name] = cached_code  # メモリにも載せる
            return await self._run_cached(func_name, cached_code, arg_values)

        # 4. キャッシュミス: seed から .ndn ソースを取得してローカル実行する。
        code = await self._fetch_function_code(func_name)
        if code is not None:
            Interpreter._code_cache[func_name] = code  # メモリに保存
            _save_cache(func_name, code)               # ファイルに保存
            print(f"[ndnc] cached '{func_name}' (~/.ndnc/cache/)", file=sys.stderr)
            return await self._run_cached(func_name, code, arg_values)

        # 5. リモート実行・ローカルフォールバックのどちらもできなかった。
        raise remote_error

    async def _fetch_function_code(self, func_name: str) -> Optional[str]:
        """seed から /func_name/code を取得して .ndn ソースを返す。失敗時は None。"""
        interest_name = "/" + func_name + "/code"
        try:
            _, _, content = await self.app.express_interest(
                interest_name,
                must_be_fresh=True,
                can_be_prefix=False,
                lifetime=6000,
            )
            if content is None:
                return None
            return bytes(content).decode('utf-8').strip()
        except Exception:
            return None

    async def _run_cached(self, func_name: str, code: str, arg_values: list[Any]) -> Any:
        """キャッシュ済み .ndn コードを引数付きでローカル実行する。"""
        from ..parser.parser import parse
        # Resolve deferred arguments here only when execution falls back to local source.
        arg_values = [await self._eval_expr(value) if isinstance(value, ExpressInterest) else value
                      for value in arg_values]
        arg_dict = {f"arg{i}": v for i, v in enumerate(arg_values)}
        program = parse(code)
        interp = Interpreter(args=arg_dict, base_dir=self.base_dir)
        interp.app = self.app
        return await interp._exec_block(program)

    async def exec_in_context(self, program: Program, app: NDNApp) -> str | bytes:
        """既存の NDNApp 内で実行し、結果を文字列またはバイト列で返す。print は表示のみ。
        seed サーバーなど、すでにイベントループが動いている環境から呼び出す用途向け。
        通常の run() と異なり、新たなイベントループや NDNApp を起動しない。"""
        self.app = app
        result = await self._exec_block(program)
        return result if isinstance(result, bytes) else ('' if result is None else str(result))
