# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    budget_lines = fields.One2many('gg.crossovered.budget.lines', 'analytic_account_id', 'Lignes budgétaires')
