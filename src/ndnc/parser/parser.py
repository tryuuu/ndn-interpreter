from __future__ import annotations

from pathlib import Path
from typing import List

from lark import Lark, Transformer, v_args

from .ast import PrintStatement, Program


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

	def start(self, stmts):  # type: ignore[override]
		# stmts is a list of PrintStatement objects
		# Ensure we always return a list
		if isinstance(stmts, list):
			return stmts
		else:
			# If there's only one statement, wrap it in a list
			return [stmts]


def parse(source: str) -> Program:
	tree = _PARSER.parse(source)
	program: List[PrintStatement] = _BuildAST().transform(tree)  # type: ignore[assignment]
	return program


