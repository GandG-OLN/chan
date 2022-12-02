# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ApprovalCategory(models.Model):
    _inherit = 'approval.category'

    approval_type = fields.Selection(selection_add=[
        ('account_move_overrun_budget', 'Dépassement budgetaire (Montant réalisé)'),
    ])
