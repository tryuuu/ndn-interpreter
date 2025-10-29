from __future__ import annotations

from pathlib import Path
from typing import List

from lark import Lark, Transformer, v_args

from .ast import PrintStatement, Program


def _load_grammar() -> str:
	grammar_path = Path(__file__).with_name("grammar.lark")
	return grammar_path.read_text(encoding="utf-8")


_PARSER = Lark(_load_grammar(), start="start", parser="lalr")


@v_args(inline=True)
class _BuildAST(Transformer):
	def print_stmt(self, s):  # type: ignore[override]
		# s is a Token('STRING', '"..."')
		# Strip quotes using python literal rules of ESCAPED_STRING: remove the surrounding quotes
		text = str(s)
		if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
			text = text[1:-1]
		return PrintStatement(value=text)

	def start(self, *stmts):  # type: ignore[override]
		return list(stmts)


def parse(source: str) -> Program:
	tree = _PARSER.parse(source)
	program: List[PrintStatement] = _BuildAST().transform(tree)  # type: ignore[assignment]
	return program


