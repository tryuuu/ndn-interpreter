from __future__ import annotations

from pathlib import Path
from typing import List

from lark import Lark, Transformer, v_args

from .ast import (
	PrintStatement, Assignment, ExprStatement,
	StringLiteral, NumberLiteral, Variable,
	ExpressInterest, Multiply, Divide, FunctionCall, Program, Expr
)


def _load_grammar() -> str:
	grammar_path = Path(__file__).with_name("grammar.lark")
	return grammar_path.read_text(encoding="utf-8")


_PARSER = Lark(_load_grammar(), start="start", parser="lalr")


class _BuildAST(Transformer):
	@v_args(inline=True)
	def assignment_stmt(self, let_token, identifier_token, expr: Expr):  # type: ignore[override]
		# The "=" token is automatically consumed by Lark and not passed to the transformer
		name = str(identifier_token)
		return Assignment(name=name, expr=expr)

	@v_args(inline=True)
	def print_stmt(self, print_token, expr: Expr):  # type: ignore[override]
		return PrintStatement(expr=expr)

	@v_args(inline=True)
	def expr_stmt(self, expr: Expr):  # type: ignore[override]
		return ExprStatement(expr=expr)

	@v_args(inline=True)
	def string_literal(self, string_token):  # type: ignore[override]
		# string_token is a Token('STRING', '"..."')
		# Strip quotes using python literal rules of ESCAPED_STRING: remove the surrounding quotes
		text = str(string_token)
		if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
			text = text[1:-1]
		return StringLiteral(value=text)

	@v_args(inline=True)
	def number_literal(self, num_token):  # type: ignore[override]
		return NumberLiteral(value=int(str(num_token)))

	@v_args(inline=True)
	def variable(self, identifier_token):  # type: ignore[override]
		name = str(identifier_token)
		return Variable(name=name)

	@v_args(inline=True)
	def interest_expr(self, interest_token, string_token):  # type: ignore[override]
		# string_token is a Token('STRING', '"..."')
		# Strip quotes using python literal rules of ESCAPED_STRING: remove the surrounding quotes
		text = str(string_token)
		if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
			text = text[1:-1]
		return ExpressInterest(name=text)

	@v_args(inline=True)
	def mul_expr(self, left: Expr, right: Expr):  # type: ignore[override]
		return Multiply(left=left, right=right)

	@v_args(inline=True)
	def div_expr(self, left: Expr, right: Expr):  # type: ignore[override]
		return Divide(left=left, right=right)

	@v_args(inline=True)
	def call_expr(self, identifier_token, arg: Expr):  # type: ignore[override]
		# The "(" and ")" tokens are automatically consumed by Lark and not passed to the transformer
		name = str(identifier_token)
		return FunctionCall(name=name, arg=arg)

	def start(self, stmts):  # type: ignore[override]
		if isinstance(stmts, list):
			return stmts
		else:
			return [stmts]


def parse(source: str) -> Program:
	tree = _PARSER.parse(source)
	program: Program = _BuildAST().transform(tree)  
	return program
