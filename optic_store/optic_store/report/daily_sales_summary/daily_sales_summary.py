# Copyright (c) 2013,     9t9it and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from functools import partial, reduce
from toolz import compose, pluck, valmap, groupby, merge, get, concatv

from optic_store.utils import pick


def execute(filters=None):
    columns = _get_columns()
    keys = compose(list, partial(pluck, "fieldname"))(columns)
    clauses, values = _get_filters(filters)
    data = _get_data(clauses, values, keys)
    return columns, data


def _get_columns():
    def make_column(key, label, type="Currency", options=None, width=120):
        return {
            "label": _(label),
            "fieldname": key,
            "fieldtype": type,
            "options": options,
            "width": width,
        }

    columns = [
        make_column(
            "sales_invoice", "Sales Invoice", type="Link", options="Sales Invoice"
        ),
        make_column("posting_time", "Time", type="Time", width=90),
        make_column("customer", "Customer", type="Link", options="Customer"),
        make_column("customer_name", "Customer Name", type="Data", width=150),
        make_column("net_total", "Net Total"),
        make_column("tax_total", "Tax Total"),
        make_column("grand_total", "Grand Total"),
    ]
    mops = pluck("name", frappe.get_all("Mode of Payment"))
    return columns + map(lambda x: make_column(x, x), mops)


def _get_filters(filters):
    branches = (
        compose(
            partial(filter, lambda x: x),
            partial(map, lambda x: x.strip()),
            lambda x: x.split(","),
        )(filters.branch)
        if filters.branch
        else None
    )
    clauses = concatv(
        ["s.docstatus = 1", "s.posting_date = %(posting_date)s"],
        ["s.os_branch IN %(branches)s"] if branches else [],
    )
    values = merge(
        pick(["posting_date"], filters), {"branches": branches} if branches else {}
    )
    return " AND ".join(clauses), values


def _get_data(clauses, values, keys):
    items = frappe.db.sql(
        """
            SELECT
                s.name AS sales_invoice,
                s.posting_time AS posting_time,
                s.customer AS customer,
                s.customer_name AS customer_name,
                s.base_net_total AS net_total,
                s.base_total_taxes_and_charges AS tax_total,
                s.base_grand_total AS grand_total
            FROM `tabSales Invoice` AS s WHERE {clauses}
        """.format(
            clauses=clauses
        ),
        values=values,
        as_dict=1,
        debug=1,
    )
    payments = frappe.db.sql(
        """
            SELECT
                p.parent AS sales_invoice,
                p.mode_of_payment AS mode_of_payment,
                p.base_amount AS amount
            FROM `tabSales Invoice` as s
            LEFT JOIN `tabSales Invoice Payment` as p ON p.parent = s.name
            WHERE {clauses}
        """.format(
            clauses=clauses
        ),
        values=values,
        as_dict=1,
    )

    make_row = compose(
        partial(valmap, lambda x: x or None),
        partial(pick, keys),
        _set_payments(payments),
    )

    return map(make_row, items)


def _set_payments(payments):
    def mop_map(item):
        return reduce(
            lambda a, x: merge(a, {x.get("mode_of_payment"): x.get("amount")}), item, {}
        )

    payments_grouped = compose(
        partial(valmap, mop_map), partial(groupby, "sales_invoice")
    )(payments)

    def fn(row):
        return merge(row, get(row.get("sales_invoice"), payments_grouped, {}))

    return fn
