# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http:# mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#


from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import re
from collections import Mapping
from copy import copy

from mo_dots import Data, split_field, join_field, concat_field
from mo_logs.strings import quote
from mo_math.randoms import Random
from mo_times import Date, Duration

from pyLibrary.meta import DataClass
from pyLibrary.sql.sqlite import quote_table

UID = "__id__"  # will not be quoted
ORDER = "__order__"
PARENT = "__parent__"
COLUMN = "__column"

ALL_TYPES = "bns"



def unique_name():
    return Random.string(20)


def column_key(k, v):
    if v == None:
        return None
    elif isinstance(v, bool):
        return k, "boolean"
    elif isinstance(v, basestring):
        return k, "string"
    elif isinstance(v, list):
        return k, None
    elif isinstance(v, Mapping):
        return k, "object"
    elif isinstance(v, Date):
        return k, "number"
    else:
        return k, "number"


def get_type(v):
    if v == None:
        return None
    elif isinstance(v, bool):
        return "boolean"
    elif isinstance(v, basestring):
        return "string"
    elif isinstance(v, Mapping):
        return "object"
    elif isinstance(v, (int, float, Date)):
        return "number"
    elif isinstance(v, list):
        return "nested"
    return None


def get_document_value(document, column):
    """
    RETURN DOCUMENT VALUE IF MATCHES THE column (name, type)

    :param document: THE DOCUMENT
    :param column: A (name, type) PAIR
    :return: VALUE, IF IT IS THE SAME NAME AND TYPE
    """
    v = document.get(split_field(column.name)[0], None)
    return get_if_type(v, column.type)


def get_if_type(value, type):
    if is_type(value, type):
        if type == "object":
            return "."
        if isinstance(value, Date):
            return value.unix
        return value
    return None


def is_type(value, type):
    if value == None:
        return False
    elif isinstance(value, basestring) and type == "string":
        return value
    elif isinstance(value, list):
        return False
    elif isinstance(value, Mapping) and type == "object":
        return True
    elif isinstance(value, (int, float, Date)) and type == "number":
        return True
    return False


def typed_column(name, type_):
    if type_ == "nested":
        type_ = "object"
    return concat_field(name, "$" + type_)


def untyped_column(column_name):
    """
    :param column_name:  DATABASE COLUMN NAME
    :return: (NAME, TYPE) PAIR
    """
    if "$" in column_name:
        path = split_field(column_name)
        return join_field(path[:-1]), path[-1][1:]
    else:
        return column_name, None


def _make_column_name(number):
    return COLUMN + unicode(number)


sql_aggs = {
    "avg": "AVG",
    "average": "AVG",
    "count": "COUNT",
    "first": "FIRST_VALUE",
    "last": "LAST_VALUE",
    "max": "MAX",
    "maximum": "MAX",
    "median": "MEDIAN",
    "min": "MIN",
    "minimum": "MIN",
    "sum": "SUM"
}

sql_types = {
    "string": "TEXT",
    "integer": "INTEGER",
    "number": "REAL",
    "boolean": "TINYINT",
    "object": "TEXT",
    "nested": "TEXT"
}

STATS = {
    "count": "COUNT({{value}})",
    "std": "SQRT((1-1.0/COUNT({{value}}))*VARIANCE({{value}}))",
    "min": "MIN({{value}})",
    "max": "MAX({{value}})",
    "sum": "SUM({{value}})",
    "median": "MEDIAN({{value}})",
    "sos": "SUM({{value}}*{{value}})",
    "var": "(1-1.0/COUNT({{value}}))*VARIANCE({{value}})",
    "avg": "AVG({{value}})"
}

quoted_UID = quote_table(UID)
quoted_ORDER = quote_table(ORDER)
quoted_PARENT = quote_table(PARENT)


def sql_text_array_to_set(column):
    def _convert(row):
        text = row[column]
        return set(eval('[' + text.replace("''", "\'") + ']'))

    return _convert


def get_column(column):
    """
    :param column: The column you want extracted
    :return: a function that can pull the given column out of sql resultset
    """

    def _get(row):
        return row[column]

    return _get


def set_column(row, col, child, value):
    """
    EXECUTE `row[col][child]=value` KNOWING THAT row[col] MIGHT BE None
    :param row:
    :param col:
    :param child:
    :param value:
    :return:
    """
    if child == ".":
        row[col] = value
    else:
        column = row[col]

        if column is None:
            column = row[col] = {}
        Data(column)[child] = value


def copy_cols(cols, nest_to_alias):
    """
    MAKE ALIAS FOR EACH COLUMN
    :param cols:
    :param nest_to_alias:  map from nesting level to subquery alias
    :return:
    """
    output = set()
    for c in cols:
        c = copy(c)
        c.es_index = nest_to_alias[c.nested_path[0]]
        output.add(c)
    return output


ColumnMapping = DataClass(
    "ColumnMapping",
    [
        {               # EDGES ARE AUTOMATICALLY INCLUDED IN THE OUTPUT, USE THIS TO INDICATE EDGES SO WE DO NOT DOUBLE-PRINT
            "name":"is_edge",
            "default": False
        },
        {               # TRACK NUMBER OF TABLE COLUMNS THIS column REPRESENTS
            "name":"num_push_columns",
            "nulls": True
        },
        "push_name",    # NAME OF THE PROPERTY (USED BY LIST FORMAT ONLY)
        "push_child",   # PATH INTO COLUMN WHERE VALUE IS STORED ("." MEANS COLUMN HOLDS PRIMITIVE VALUE)
        "push_column",  # THE COLUMN NUMBER
        "push_column_name",  # THE COLUMN NAME FOR TABLES AND CUBES (WITH NO ESCAPING DOTS, NOT IN LEAF FORM)
        "pull",         # A FUNCTION THAT WILL RETURN A VALUE
        {               # A LIST OF MULTI-SQL REQUIRED TO GET THE VALUE FROM THE DATABASE
            "name": "sql",
            "type": list
        },
        "type",         # THE NAME OF THE JSON DATA TYPE EXPECTED
        {               # A LIST OF PATHS EACH INDICATING AN ARRAY
            "name": "nested_path",
            "type": list,
            "default": ["."]
        }
    ],
    constraint={"and": [
        {"in": {"type": ["null", "boolean", "number", "string", "object"]}},
        {"gte": [{"length": "nested_path"}, 1]}
    ]}
)
