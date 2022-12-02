from datetime import timedelta

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_gg_account_budget_purchase = fields.Boolean(default=False, string="Purchase")

