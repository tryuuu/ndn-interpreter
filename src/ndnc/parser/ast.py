from __future__ import annotations

from dataclasses import dataclass
from typing import List, Union


@dataclass
class PrintStatement:
	value: str

@dataclass
class NumberLiteral:
	value: int

@dataclass
class Multiply:
	left: "Expr"
	right: "Expr"

@dataclass
class Divide:
	left: "Expr"
	right: "Expr"

Expr = Union[NumberLiteral, Multiply, Divide]

@dataclass
class ExprStatement:
	expr: Expr


Statement = Union[PrintStatement, ExprStatement]
Program = List[Statement]