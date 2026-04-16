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
	name_is_var: bool = False  # True のとき name は変数名（実行時に env から解決する）

@dataclass
class FunctionCall:
	name: str
	args: List["Expr"]

Expr = Union[StringLiteral, NumberLiteral, Variable, ExpressInterest, FunctionCall]

@dataclass
class ExprStatement:
	expr: Expr


Statement = Union[PrintStatement, Assignment, ExprStatement]
Program = List[Statement]