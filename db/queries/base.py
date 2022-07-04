from collections import namedtuple

from sqlalchemy import select, join, Column as SAColumn, Table as SATable

from django.utils.functional import cached_property

from db.columns.base import MathesarColumn
from db.records.operations import select as records_select

class DBQuery:
    def __init__(
        self,
        base_table,
        initial_columns,
        transformations=None,
        name=None
    ):
        assert isinstance(base_table, SATable)
        self.base_table = base_table
        for initial_col in initial_columns:
            assert isinstance(initial_col, InitialColumn)
        self.initial_columns = initial_columns
        self.transformations = transformations
        self.name = name

    # mirrors a method in db.records.operations.select
    def get_records(self, **kwargs):
        return records_select.get_records(table=self.sa_relation, **kwargs)

    # mirrors a method in db.records.operations.select
    def get_count(self, **kwargs):
        return records_select.get_count(table=self.sa_relation, **kwargs)

    @cached_property
    def sa_output_columns(self):
        """
        Sequence of SQLAlchemy columns representing the output columns of the relation described
        by this query.
        """
        regular_sa_columns = self.sa_relation.columns
        enriched_sa_columns = tuple(MathesarColumn.from_column(col) for col in regular_sa_columns)
        return enriched_sa_columns

    @cached_property
    def sa_relation(self):
        """
        A query describes a relation. This property is the result of parsing a query into a
        relation.
        """
        initial_relation = _get_initial_relation(self)
        transformed = _apply_transformations(initial_relation, self.transformations)
        return transformed


class InitialColumn:
    def __init__(
        self,
        alias,
        column,
        jp_path=None,
    ):
        assert isinstance(alias, str) and alias.strip() != ""
        self.alias = alias
        if jp_path is not None:
            for jp in jp_path:
                assert isinstance(jp, JoinParams)
        self.jp_path = jp_path
        assert isinstance(column, SAColumn)
        self.column = column

    @property
    def is_base_column(self):
        return self.jp_path is None


class JoinParams(
    namedtuple(
        'JoinParams',
        [
            'left_column',
            'right_column',
        ]
    )
):
    """
    Describes parameters for a join. Namely, the table and column pairs on both sides of the join.
    """
    def flip(self):
        return JoinParams(
            left_column=self.right_column,
            right_column=self.left_column,
        )

    @property
    def left_table(self):
        return self.left_column.table

    @property
    def right_table(self):
        return self.right_column.table


def _apply_transformations(initial_relation, transformations):
    return initial_relation


def _get_initial_relation(query):
    nested_join = None
    sa_columns_to_select = []
    for initial_column in query.initial_columns:
        nested_join, sa_column_to_select = _process_initial_column(
            initial_column=initial_column,
            nested_join=nested_join,
        )
        sa_columns_to_select.append(sa_column_to_select)

    if nested_join is not None:
        select_target = nested_join
    else:
        select_target = query.base_table

    stmt = select(*sa_columns_to_select).select_from(select_target)
    return stmt.cte()


def _process_initial_column(initial_column, nested_join):
    if initial_column.is_base_column:
        col_to_select = initial_column.column
    else:
        nested_join, col_to_select = _nest_a_join(
            initial_column=initial_column,
            nested_join=nested_join,
        )
    # Give an alias/label to this column, since that's how it will be referenced in transforms.
    aliased_col_to_select = col_to_select.label(initial_column.alias)
    return nested_join, aliased_col_to_select


def _nest_a_join(nested_join, initial_column):
    jp_path = initial_column.jp_path
    target_sa_column = initial_column.column
    rightmost_table_alias = None
    for i, jp in enumerate(reversed(jp_path)):
        is_last_jp = i == 0
        if is_last_jp:
            rightmost_table_alias = jp.right_table.alias()
            right_table = rightmost_table_alias
            right_column_reference = (
                # If we give the right table an alias, we have to use that alias everywhere.
                _access_column_on_aliased_relation(
                    rightmost_table_alias,
                    jp.right_column,
                )
            )
        else:
            right_table = nested_join
            right_column_reference = jp.right_column

        left_column_reference = jp.left_column
        nested_join = join(
            jp.left_table, right_table,
            left_column_reference == right_column_reference
        )
    rightmost_table_target_column_reference = (
        _access_column_on_aliased_relation(
            rightmost_table_alias,
            target_sa_column,
        )
    )
    return nested_join, rightmost_table_target_column_reference


def _access_column_on_aliased_relation(aliased_relation, sa_column):
    column_name = sa_column.name
    return getattr(aliased_relation.c, column_name)
