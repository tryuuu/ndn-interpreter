from __future__ import annotations

from dataclasses import dataclass
from typing import List, Union


@dataclass
class PrintStatement:
	expr: "Expr"

@dataclass
class Assignment:
	name: str
	expr: "Expr"

@dataclass
class StringLiteral:
	value: str

@dataclass
class NumberLiteral:
	value: int

@dataclass
class Variable:
	name: str

@dataclass
class ExpressInterest:
	name: str

@dataclass
class Multiply:
	left: "Expr"
	right: "Expr"

@dataclass
class Divide:
	left: "Expr"
	right: "Expr"

Expr = Union[StringLiteral, NumberLiteral, Variable, ExpressInterest, Multiply, Divide]

@dataclass
class ExprStatement:
	expr: Expr


Statement = Union[PrintStatement, Assignment, ExprStatement]
Program = List[Statement]