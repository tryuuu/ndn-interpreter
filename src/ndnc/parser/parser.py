from __future__ import annotations

from pathlib import Path
from typing import List

from lark import Lark, Transformer, v_args

from .ast import PrintStatement, ExprStatement, NumberLiteral, ExpressInterest, Multiply, Divide, Program


def _load_grammar() -> str:
	grammar_path = Path(__file__).with_name("grammar.lark")
	return grammar_path.read_text(encoding="utf-8")


_PARSER = Lark(_load_grammar(), start="start", parser="lalr")


class _BuildAST(Transformer):
	@v_args(inline=True)
	def print_stmt(self, print_token, string_token):  # type: ignore[override]
		# string_token is a Token('STRING', '"..."')
		# Strip quotes using python literal rules of ESCAPED_STRING: remove the surrounding quotes
		text = str(string_token)
		if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
			text = text[1:-1]
		return PrintStatement(value=text)

	@v_args(inline=True)
	def num_stmt(self, num_token):  # type: ignore[override]
		return ExprStatement(expr=NumberLiteral(value=int(str(num_token))))

	@v_args(inline=True)
	def mul_stmt(self, left_num, right_num):  # type: ignore[override]
		left = NumberLiteral(value=int(str(left_num)))
		right = NumberLiteral(value=int(str(right_num)))
		return ExprStatement(expr=Multiply(left=left, right=right))

	@v_args(inline=True)
	def div_stmt(self, left_num, right_num):  # type: ignore[override]
		left = NumberLiteral(value=int(str(left_num)))
		right = NumberLiteral(value=int(str(right_num)))
		return ExprStatement(expr=Divide(left=left, right=right))

	@v_args(inline=True)
	def interest_stmt(self, interest_token, string_token):  # type: ignore[override]
		# string_token is a Token('STRING', '"..."')
		# Strip quotes using python literal rules of ESCAPED_STRING: remove the surrounding quotes
		text = str(string_token)
		if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
			text = text[1:-1]
		return ExprStatement(expr=ExpressInterest(name=text))

	def start(self, stmts):  # type: ignore[override]
		if isinstance(stmts, list):
			return stmts
		else:
			return [stmts]


def parse(source: str) -> Program:
	tree = _PARSER.parse(source)
	program: Program = _BuildAST().transform(tree)  
	return program
