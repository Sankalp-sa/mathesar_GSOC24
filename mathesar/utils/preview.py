import re

from db.constraints.utils import ConstraintType
from mathesar.models.base import Column, Constraint


def add_preview_columns(preview_info, referent_table_settings):
    for referent_table_setting in referent_table_settings:
        preview_template = referent_table_setting.preview_settings.template
        preview_columns_extraction_regex = r'\{(.*?)\}'
        preview_data_column_ids = re.findall(preview_columns_extraction_regex, preview_template)
        preview_data_columns = Column.objects.filter(id__in=preview_data_column_ids)
        preview_info[referent_table_setting.table_id]['preview_columns'] = preview_data_columns
        preview_info[referent_table_setting.table_id]['table'] = referent_table_setting.table
    return preview_info


def get_constrained_columns_by_referent_table(fk_previews, fk_constraints, previous_path=[], exising_columns=[]):
    preview_info = {}
    preview_columns = exising_columns
    for fk_constraint in fk_constraints:
        constrained_column = fk_constraint.columns[0]
        # For now only single column foreign key is used.
        referent_column = fk_constraint.referent_columns[0]
        referent_table = referent_column.table
        referent_table_settings = referent_column.table.settings
        preview_template = referent_table_settings.preview_settings.template
        preview_columns_extraction_regex = r'\{(.*?)\}'
        preview_data_column_ids = re.findall(preview_columns_extraction_regex, preview_template)
        preview_data_columns = Column.objects.filter(id__in=preview_data_column_ids)
        current_path = previous_path + [[constrained_column.id, referent_column.id]]
        referent_preview_info, referent_preview_columns = get_preview_info(fk_previews, referent_table.id, preview_data_columns, current_path, exising_columns)
        preview_columns = preview_columns + referent_preview_columns
        for column_key, column_value in referent_preview_info.items():
            preview_template = preview_template.replace(f'{{{column_key}}}', f'{column_value["template"]}')
        path_prefix = "___".join([f"{path[0]}__{path[1]}" for path in current_path])
        for preview_data_column_id in preview_data_column_ids:
            if preview_data_column_id not in referent_preview_info:
                column_alias_name = f'{path_prefix}__col__{preview_data_column_id}'
                preview_template = preview_template.replace(f'{{{preview_data_column_id}}}', f'{{{column_alias_name}}}')
                initial_column = {'id': preview_data_column_id, "alias": column_alias_name, "jp_path": current_path}
                preview_columns.append(initial_column)
        preview_info[constrained_column.id] = {"template": preview_template, 'path': current_path}
    return preview_info, preview_columns


def get_preview_info(fk_previews, referrer_table_pk, restrict_columns=None, path=[], existing_columns=[]):
    table_constraints = Constraint.objects.filter(table_id=referrer_table_pk)
    fk_constraints = [
        table_constraint
        for table_constraint in table_constraints
        if table_constraint.type == ConstraintType.FOREIGN_KEY.value
    ]
    if fk_previews == 'auto':
        fk_constraints = filter(
            _filter_preview_enabled_columns,
            fk_constraints
        )
    if restrict_columns:
        fk_constraints = filter(
            _get_filter_restricted_columns_fn(restrict_columns),
            fk_constraints
        )

    preview_info, columns = get_constrained_columns_by_referent_table(
        fk_previews,
        fk_constraints,
        path,
        existing_columns
    )
    return preview_info, columns


def _filter_preview_enabled_columns(fk_constraint):
    constrained_column = fk_constraint.columns[0]
    return constrained_column.display_options['show_fk_preview']


def _get_filter_restricted_columns_fn(restricted_columns):
    def _filter_restricted_columns(fk_constraint):
        constrained_column = fk_constraint.columns[0]
        return constrained_column in restricted_columns

    return _filter_restricted_columns
