from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError


ALLOWED_COLUMNS = {
    "id",
    "customer_name",
    "email",
    "category",
    "priority",
    "status",
    "created_at",
}
ALLOWED_AGGREGATES = (exp.Avg, exp.Count, exp.Max, exp.Min, exp.Sum)
NON_FUNCTION_EXPRESSIONS = (exp.And, exp.Not, exp.Or)


class QueryPolicyError(ValueError):
    """Raised when a query does not satisfy the support-data policy."""


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    aggregate: bool


def _reject(condition: bool, message: str) -> None:
    if condition:
        raise QueryPolicyError(message)


def validate_support_query(query: str) -> ValidatedQuery:
    """Parse and validate the deliberately narrow support_requests SQL policy."""
    _reject(not query or not query.strip(), "A query is required.")
    try:
        statements = parse(query, read="postgres")
    except ParseError as exc:
        raise QueryPolicyError("The query is not valid PostgreSQL SELECT syntax.") from exc

    _reject(len(statements) != 1, "Exactly one SQL statement is allowed.")
    statement = statements[0]
    _reject(not isinstance(statement, exp.Select), "Only SELECT statements are allowed.")
    _reject(len(list(statement.find_all(exp.Select))) != 1, "Subqueries are not allowed.")
    _reject(statement.args.get("with_") is not None, "Common table expressions are not allowed.")
    _reject(any(statement.find_all(exp.SetOperation)), "Set operations are not allowed.")
    _reject(bool(statement.args.get("joins")), "Joins are not allowed.")
    _reject(statement.args.get("into") is not None, "SELECT INTO is not allowed.")
    _reject(bool(statement.args.get("locks")), "Row-locking clauses are not allowed.")
    _reject(any(statement.find_all(exp.TableSample)), "Table sampling is not allowed.")
    _reject(any(statement.find_all(exp.Window)), "Window functions are not allowed.")

    tables = list(statement.find_all(exp.Table))
    _reject(len(tables) != 1, "Exactly one table is allowed.")
    table = tables[0]
    _reject(table.name.lower() != "support_requests", "Only support_requests may be queried.")
    _reject(bool(table.catalog), "Catalog-qualified tables are not allowed.")
    _reject(bool(table.db) and table.db.lower() != "public", "Only the public schema is allowed.")
    _reject(any(identifier.args.get("quoted") for identifier in table.find_all(exp.Identifier)), "Quoted table identifiers are not allowed.")

    alias = (table.alias or "").lower()
    allowed_qualifiers = {"support_requests"}
    if alias:
        allowed_qualifiers.add(alias)

    _reject(any(statement.find_all(exp.Star)), "Wildcard column selection is not allowed.")
    columns = list(statement.find_all(exp.Column))
    _reject(not columns, "At least one explicit support_requests column is required.")
    for column in columns:
        _reject(column.name.lower() not in ALLOWED_COLUMNS, "The query references an unapproved column.")
        _reject(bool(column.table) and column.table.lower() not in allowed_qualifiers, "The query uses an invalid column qualifier.")
        _reject(any(identifier.args.get("quoted") for identifier in column.find_all(exp.Identifier)), "Quoted column identifiers are not allowed.")

    functions = [
        function
        for function in statement.find_all(exp.Func)
        if not isinstance(function, NON_FUNCTION_EXPRESSIONS)
    ]
    _reject(any(not isinstance(function, ALLOWED_AGGREGATES) for function in functions), "Only approved aggregate functions are allowed.")
    aggregate = bool(functions)

    limit = statement.args.get("limit")
    if not aggregate:
        _reject(limit is None, "Non-aggregate queries require LIMIT 50 or less.")
    if limit is not None:
        value = limit.expression
        _reject(not isinstance(value, exp.Literal) or not value.is_int, "LIMIT must be an integer literal.")
        limit_value = int(value.this)
        _reject(limit_value < 1 or limit_value > 50, "LIMIT must be between 1 and 50.")

    return ValidatedQuery(sql=statement.sql(dialect="postgres"), aggregate=aggregate)
