# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Budgets
# ---------------------------------------------------------
class ResUsers(models.Model):
    _inherit = 'res.users'

    allowed_budget_ids = fields.Many2many('gg.crossovered.budget', 'gg_budget_allowed_user_rel', 'user_id', 'budget_id',
                                          groups="base.admin", string='Allowed budget')
